from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    complexity_score: float
    complexity_bucket: int
    chosen_tier: str
    chosen_provider: str
    chosen_model: str
    policy_id: str
    policy_version: str
    routing_reason: str


def complexity_score(
    prompt: Mapping[str, Any], feature: str, context: Mapping[str, Any] | None = None
) -> float:
    payload = dict(prompt or {})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    token_estimate = max(1, len(canonical) // 4)
    token_component = min(0.45, (min(token_estimate, 2000) / 2000.0) * 0.45)

    messages = payload.get("messages")
    message_count = len(messages) if isinstance(messages, list) else 0
    message_component = min(0.18, (min(message_count, 8) / 8.0) * 0.18)

    structured_markers = (
        "json_schema",
        "response_schema",
        "structured_output",
        "output_format",
        "schema",
    )
    structured_component = (
        0.2 if any(marker in payload for marker in structured_markers) else 0.0
    )

    text_blob = " ".join(
        str(payload.get(k, ""))
        for k in ("input", "text", "instruction", "task", "query")
    )
    hard_reasoning_markers = (
        "step-by-step",
        "prove",
        "counterfactual",
        "reconcile",
        "multi-step",
        "attribution",
    )
    reasoning_component = (
        0.12
        if any(marker in text_blob.lower() for marker in hard_reasoning_markers)
        else 0.0
    )

    context = context or {}
    context_size = int(
        context.get("context_items", payload.get("context_items", 0)) or 0
    )
    context_component = min(0.18, (min(max(context_size, 0), 40) / 40.0) * 0.18)

    feature_component = 0.0
    if feature.endswith("investigation"):
        feature_component = 0.06
    elif feature.endswith("budget_optimization"):
        feature_component = 0.04

    score = (
        0.03
        + token_component
        + message_component
        + structured_component
        + reasoning_component
        + context_component
        + feature_component
    )
    return max(0.0, min(1.0, round(score, 6)))


def bucket(score: float) -> int:
    clamped = max(0.0, min(1.0, float(score)))
    return max(1, min(10, int(math.ceil(clamped * 10.0))))


def _candidate_policy_paths(raw_path: str) -> list[Path]:
    raw = Path(raw_path)
    candidates = [raw]
    if not raw.is_absolute():
        if str(raw).startswith("backend/"):
            candidates.append(Path(str(raw)[len("backend/") :]))
        else:
            candidates.append(Path("backend") / raw)
        candidates.append(Path(__file__).resolve().parent / "policies" / raw.name)
    return candidates


def _load_policy(policy_path: str) -> dict[str, Any]:
    for candidate in _candidate_policy_paths(policy_path):
        if candidate.exists() and candidate.is_file():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(
                    f"complexity router policy must be a JSON object: {candidate}"
                )
            return payload
    raise ValueError(f"complexity router policy file not found: {policy_path}")


def _resolve_tier_for_bucket(bucket_value: int, policy: Mapping[str, Any]) -> str:
    bands = policy.get("bucket_tiers")
    if not isinstance(bands, list) or not bands:
        raise ValueError("complexity router policy missing bucket_tiers")
    for band in bands:
        if not isinstance(band, Mapping):
            continue
        low = int(band.get("min_bucket", 0))
        high = int(band.get("max_bucket", 0))
        if low <= bucket_value <= high:
            tier = str(band.get("tier", "")).strip()
            if not tier:
                raise ValueError("bucket tier mapping contains empty tier")
            return tier
    raise ValueError(f"no bucket tier mapping for bucket={bucket_value}")


def _apply_budget_pressure_downgrade(
    *,
    tier: str,
    policy: Mapping[str, Any],
    budget_state: Mapping[str, Any],
) -> tuple[str, str]:
    downgrade = policy.get("budget_downgrade")
    if not isinstance(downgrade, Mapping) or not bool(downgrade.get("enabled", False)):
        return tier, "bucket_policy"

    cap = int(budget_state.get("cap_cents", 0) or 0)
    spent = int(budget_state.get("spent_cents", 0) or 0)
    reserved = int(budget_state.get("reserved_cents", 0) or 0)
    if cap <= 0:
        return tier, "bucket_policy"

    utilization = (spent + reserved) / float(cap)
    pressure_threshold = float(downgrade.get("pressure_threshold", 0.80))
    critical_threshold = float(downgrade.get("critical_threshold", 0.95))
    order = [
        str(item)
        for item in downgrade.get("downgrade_order", ["premium", "standard", "cheap"])
    ]
    if tier not in order:
        return tier, "bucket_policy"

    tier_index = order.index(tier)
    if utilization >= critical_threshold and tier_index < len(order) - 1:
        return order[-1], f"budget_pressure_critical:{utilization:.3f}"
    if utilization >= pressure_threshold and tier_index < len(order) - 1:
        return order[tier_index + 1], f"budget_pressure:{utilization:.3f}"
    return tier, "bucket_policy"


def route_request(
    *,
    prompt: Mapping[str, Any],
    feature: str,
    context: Mapping[str, Any] | None,
    policy_path: str,
) -> RoutingDecision:
    policy = _load_policy(policy_path)
    policy_id = str(policy.get("policy_id", "")).strip()
    policy_version = str(policy.get("policy_version", "")).strip()
    if not policy_id or not policy_version:
        raise ValueError(
            "complexity router policy requires non-empty policy_id and policy_version"
        )

    score = complexity_score(prompt=prompt, feature=feature, context=context)
    bucket_value = bucket(score)

    base_tier = _resolve_tier_for_bucket(bucket_value, policy)
    budget_state = (context or {}).get("budget_state", {})
    if not isinstance(budget_state, Mapping):
        budget_state = {}
    resolved_tier, reason = _apply_budget_pressure_downgrade(
        tier=base_tier,
        policy=policy,
        budget_state=budget_state,
    )

    tiers = policy.get("tiers")
    if not isinstance(tiers, Mapping) or resolved_tier not in tiers:
        raise ValueError(
            f"complexity router policy missing tier definition for '{resolved_tier}'"
        )
    tier_def = tiers[resolved_tier]
    if not isinstance(tier_def, Mapping):
        raise ValueError(f"tier definition for '{resolved_tier}' must be an object")

    provider = str(tier_def.get("provider", "")).strip()
    model = str(tier_def.get("model", "")).strip()
    if not provider or not model:
        raise ValueError(
            f"tier '{resolved_tier}' must define non-empty provider and model"
        )

    return RoutingDecision(
        complexity_score=score,
        complexity_bucket=bucket_value,
        chosen_tier=resolved_tier,
        chosen_provider=provider,
        chosen_model=model,
        policy_id=policy_id,
        policy_version=policy_version,
        routing_reason=reason,
    )

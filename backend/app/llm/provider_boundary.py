"""
Single LLM provider choke-point (B0.7-P3).

Provider calls, budget reservation/settlement, breaker, timeout, cache, and
distillation persistence are enforced here in one ordered path.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import aisuite
except ModuleNotFoundError:
    aisuite = None

from app.core.config import settings
from app.db.session import set_tenant_guc_async, set_user_guc_async
from app.llm.complexity_router import RoutingDecision, route_request
from app.llm.output_validation import (
    OutputValidationResult,
    ProviderOutputValidationSpec,
    validate_provider_output_text,
)
from app.models.llm import (
    LLMBreakerState,
    LLMBudgetReservation,
    LLMHourlyShutoffState,
    LLMApiCall,
    LLMMonthlyCost,
    LLMSemanticCache,
)
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.llm_validation_failures import (
    LLMValidationFailureService,
    ValidationFailureSinkWriteOutcome,
)

NUMERIC_REJECTION_CACHE_STATE = "numeric_authority_rejected"
NUMERIC_REJECTION_CACHE_SUPPRESS_SECONDS = 900
REQUEST_LOCAL_MAX_ATTEMPTS = 3
B17_EXPLANATION_ENDPOINT = "app.api.attribution.explanation_fastpath"


def _month_start_utc(occurred_at: datetime) -> date:
    at = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)
    at = at.astimezone(timezone.utc)
    return date(at.year, at.month, 1)


def _hour_start_utc(occurred_at: datetime) -> datetime:
    at = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)
    at = at.astimezone(timezone.utc)
    return at.replace(minute=0, second=0, microsecond=0)


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _validation_context_fingerprint(
    validation_context: Mapping[str, Any] | None,
) -> str:
    if not isinstance(validation_context, Mapping):
        return ""
    deterministic_truth = validation_context.get("deterministic_truth")
    truth_mapping = (
        deterministic_truth if isinstance(deterministic_truth, Mapping) else {}
    )

    normalized_bindings: list[dict[str, Any]] = []
    raw_bindings = validation_context.get("numeric_claim_bindings")
    if isinstance(raw_bindings, list):
        for entry in raw_bindings:
            if not isinstance(entry, Mapping):
                continue
            claim_path = entry.get("claim_path")
            truth_path = entry.get("truth_path")
            if not isinstance(claim_path, str) or not claim_path.strip():
                continue
            if not isinstance(truth_path, str) or not truth_path.strip():
                continue
            normalized_bindings.append(
                {
                    "claim_path": claim_path.strip(),
                    "truth_path": truth_path.strip(),
                    "tolerance_ratio": entry.get("tolerance_ratio"),
                }
            )
    if not normalized_bindings:
        raw_claim_paths = validation_context.get("numeric_claim_paths")
        if isinstance(raw_claim_paths, list):
            for claim_path in raw_claim_paths:
                if isinstance(claim_path, str) and claim_path.strip():
                    normalized = claim_path.strip()
                    normalized_bindings.append(
                        {
                            "claim_path": normalized,
                            "truth_path": normalized,
                            "tolerance_ratio": None,
                        }
                    )

    truth_snapshot: dict[str, Any] = {}
    for binding in normalized_bindings:
        path = str(binding["truth_path"])
        truth_snapshot[path] = _mapping_path_value(truth_mapping, path)

    seed = {
        "truth_snapshot": truth_snapshot,
        "numeric_claim_bindings": normalized_bindings,
        "numeric_tolerance_ratio": validation_context.get("numeric_tolerance_ratio"),
    }
    return hashlib.sha256(_json(seed).encode("utf-8")).hexdigest()


def _cache_key(
    prompt: Mapping[str, Any],
    endpoint: str,
    model_name: str,
) -> str:
    cache_identity = prompt.get("cache_identity")
    if isinstance(cache_identity, Mapping):
        seed: dict[str, Any] = {"cache_identity": dict(cache_identity)}
    else:
        seed = dict(prompt)
    seed.pop("cache_watermark", None)
    seed.pop("cache_enabled", None)
    seed.pop("reject_provider_reentry_on_stale", None)
    return hashlib.sha256(
        f"{endpoint}|{model_name}|{_json(seed)}".encode("utf-8")
    ).hexdigest()


def _prompt_fingerprint(prompt: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json(prompt).encode("utf-8")).hexdigest()


def _watermark(prompt: Mapping[str, Any]) -> int:
    raw = prompt.get("cache_watermark", 0)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _truth_snapshot_from_prompt(prompt: Mapping[str, Any]) -> dict[str, Any]:
    raw = prompt.get("truth_snapshot")
    if not isinstance(raw, Mapping):
        return {}
    return dict(raw)


def _stale_replay_rejection_enabled(endpoint: str, prompt: Mapping[str, Any]) -> bool:
    prewarm_context = prompt.get("prewarm_context")
    if (
        isinstance(prewarm_context, Mapping)
        and bool(prewarm_context.get("allow_stale_refresh", False))
    ):
        return False
    if endpoint == B17_EXPLANATION_ENDPOINT:
        return True
    return bool(prompt.get("reject_provider_reentry_on_stale", False))


def _parse_iso8601_utc(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _mapping_path_value(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for segment in path.split("."):
        if not segment:
            return None
        if not isinstance(current, Mapping):
            return None
        if segment not in current:
            return None
        current = current[segment]
    return current


@dataclass(frozen=True, slots=True)
class ProviderBoundaryResult:
    provider: str
    model: str
    output_text: str
    reasoning_trace: Mapping[str, Any] | None
    usage: Mapping[str, int]
    status: str
    was_cached: bool
    request_id: str
    correlation_id: str
    api_call_id: UUID
    block_reason: str | None = None
    failure_reason: str | None = None
    response_metadata: Mapping[str, Any] | None = None
    validation_code: str | None = None
    validation_stage: str | None = None
    validated_output: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CacheReplayProbeResult:
    state: Literal["miss", "hit", "stale_mismatch"]
    row: LLMSemanticCache | None = None
    row_watermark: int | None = None


class SkeldirLLMProvider:
    boundary_id = "b07_p3_aisuite_chokepoint"
    breaker_key = "llm-provider"
    _validation_failure_service = LLMValidationFailureService()

    @staticmethod
    def _validation_failure_sink_metadata(
        *,
        attempted: bool,
        degraded_reason: str | None,
    ) -> dict[str, Any]:
        if not attempted:
            return {"validation_failure_sink_status": "not_attempted"}
        if degraded_reason is not None:
            return {
                "validation_failure_sink_status": "degraded",
                "validation_failure_sink_degraded_reason": degraded_reason,
            }
        return {"validation_failure_sink_status": "recorded"}

    async def _db_now(self, session: AsyncSession) -> datetime:
        now = (await session.execute(text("SELECT now()"))).scalar_one()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _request_local_attempt_budget(
        validation_spec: ProviderOutputValidationSpec | None,
    ) -> int:
        requested = (
            int(validation_spec.max_attempts)
            if validation_spec is not None
            else REQUEST_LOCAL_MAX_ATTEMPTS
        )
        bounded = max(1, min(REQUEST_LOCAL_MAX_ATTEMPTS, requested))
        return bounded

    @staticmethod
    def _build_validation_correction_payload(
        *,
        validation: OutputValidationResult,
        attempt: int,
        max_attempts: int,
        validation_spec: ProviderOutputValidationSpec | None,
    ) -> dict[str, Any]:
        instructions = [
            "Return a strict JSON object that satisfies the expected schema.",
            "Do not restate or copy prior invalid output.",
            "If numeric authority claims exist, align every claim to deterministic truth within tolerance.",
        ]
        payload: dict[str, Any] = {
            "correction_type": "validation_regeneration",
            "attempt": int(attempt),
            "next_attempt": int(attempt + 1),
            "max_attempts": int(max_attempts),
            "validation_code": str(validation.code),
            "validation_stage": str(validation.stage),
            "schema_key": str(validation.schema_key or "unknown"),
            "text_field": (
                str(validation_spec.text_field)
                if validation_spec is not None
                else "output_text"
            ),
            "error_detail": str(validation.error_detail or validation.code),
            "normalization_source": str(validation.normalization_source or "unknown"),
            "instructions": instructions,
        }
        if validation.numeric_tolerance_ratio is not None:
            payload["numeric_tolerance_ratio"] = float(
                validation.numeric_tolerance_ratio
            )
        if int(validation.numeric_mismatch_count) > 0:
            payload["numeric_mismatch_count"] = int(validation.numeric_mismatch_count)
        return payload

    @staticmethod
    def _prompt_for_attempt(
        *,
        base_prompt: Mapping[str, Any],
        attempt: int,
        max_attempts: int,
        correction_payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        attempt_prompt = dict(base_prompt)
        attempt_prompt["request_local_attempt"] = int(attempt)
        attempt_prompt["request_local_attempt_budget"] = int(max_attempts)
        if correction_payload is None:
            attempt_prompt.pop("validation_correction_payload", None)
            attempt_prompt.pop("validation_regeneration_active", None)
            return attempt_prompt

        attempt_prompt["validation_regeneration_active"] = True
        attempt_prompt["validation_correction_payload"] = dict(correction_payload)
        messages: list[dict[str, Any]] = []
        raw_messages = base_prompt.get("messages")
        if isinstance(raw_messages, list):
            for entry in raw_messages:
                if not isinstance(entry, Mapping):
                    continue
                normalized = dict(entry)
                role = normalized.get("role")
                if not isinstance(role, str) or not role.strip():
                    normalized["role"] = "user"
                content = normalized.get("content")
                if content is None:
                    normalized["content"] = ""
                elif not isinstance(content, (str, list, dict)):
                    normalized["content"] = str(content)
                messages.append(normalized)

        if not messages:
            user_text = (
                base_prompt.get("input")
                or base_prompt.get("text")
                or _json(base_prompt)
            )
            messages = [{"role": "user", "content": str(user_text)}]

        correction_text = "Validation regeneration payload (JSON): " + json.dumps(
            dict(correction_payload),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        messages.append({"role": "system", "content": correction_text})
        attempt_prompt["messages"] = messages
        return attempt_prompt

    async def complete(
        self,
        *,
        model: LLMTaskPayload,
        session: AsyncSession,
        endpoint: str,
        force_failure: bool = False,
        validation_spec: ProviderOutputValidationSpec | None = None,
        validation_context: Mapping[str, Any] | None = None,
        routing_tier_override: str | None = None,
        timeout_ms_override: int | None = None,
    ) -> ProviderBoundaryResult:
        await self._ensure_rls_context(session, model.tenant_id, model.user_id)

        request_id = str(model.request_id or model.correlation_id or "")
        correlation_id = str(model.correlation_id or request_id or "")
        prompt = dict(model.prompt or {})
        prewarm_context = (
            dict(prompt.get("prewarm_context"))
            if isinstance(prompt.get("prewarm_context"), Mapping)
            else {}
        )

        def _inject_prewarm_metadata(payload: dict[str, Any]) -> None:
            if not prewarm_context:
                return
            payload["prewarm_assisted"] = True
            for key in (
                "prewarm_origin",
                "prewarm_strategy",
                "prewarm_trigger_event",
                "prewarm_trigger_identity",
                "prewarm_truth_watermark",
                "prewarm_target_entity_type",
            ):
                if key in prewarm_context:
                    payload[key] = prewarm_context[key]

        budget_state = await self._current_budget_state(
            session=session,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
        )
        routing = route_request(
            prompt=prompt,
            feature=endpoint,
            context={"budget_state": budget_state},
            policy_path=settings.LLM_COMPLEXITY_POLICY_PATH,
            forced_tier=routing_tier_override,
        )
        requested_model = f"{routing.chosen_provider}:{routing.chosen_model}"
        validation_context_fingerprint = _validation_context_fingerprint(
            validation_context
        )
        key = _cache_key(
            prompt,
            endpoint,
            requested_model,
        )
        prompt_fingerprint = _prompt_fingerprint(prompt)
        watermark = _watermark(prompt)
        truth_snapshot = _truth_snapshot_from_prompt(prompt)
        stale_replay_rejection_enabled = _stale_replay_rejection_enabled(
            endpoint, prompt
        )
        reservation = max(0, int(model.max_cost_cents))

        api_call_id, created_at, claimed = await self._claim(
            session=session,
            model=model,
            endpoint=endpoint,
            request_id=request_id,
            correlation_id=correlation_id,
            requested_model=requested_model,
            reservation=reservation,
            cache_key=key,
            prompt_fingerprint=prompt_fingerprint,
            cache_watermark=watermark,
            routing=routing,
        )
        if not claimed:
            return await self._load_existing(
                session=session,
                api_call_id=api_call_id,
                request_id=request_id,
                correlation_id=correlation_id,
                validation_spec=validation_spec,
                validation_context=validation_context,
            )

        # Emergency stop-path: block before reservation/cache/provider call while keeping
        # an auditable llm_api_calls denial row for incident forensics.
        if settings.LLM_PROVIDER_KILL_SWITCH or bool(prompt.get("kill_switch", False)):
            await self._finalize_blocked(session, api_call_id, "provider_kill_switch")
            await self._write_call_audit(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                requested_model=requested_model,
                resolved_model=requested_model,
                estimated_cost_cents=reservation,
                decision="BLOCK",
                reason="provider_kill_switch",
                input_tokens=0,
                output_tokens=0,
                prompt_fingerprint=prompt_fingerprint,
            )
            await session.commit()
            return self._blocked_result(
                api_call_id,
                request_id,
                correlation_id,
                requested_model,
                "provider_kill_switch",
            )

        month = _month_start_utc(created_at)
        now = await self._db_now(session)
        shutoff_reason = await self._hourly_block_reason(
            session=session,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            now=now,
        )
        if shutoff_reason:
            await self._release(
                session,
                model.tenant_id,
                model.user_id,
                endpoint,
                request_id,
                month,
                reservation,
            )
            await self._finalize_blocked(session, api_call_id, shutoff_reason)
            await self._write_call_audit(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                requested_model=requested_model,
                resolved_model=requested_model,
                estimated_cost_cents=reservation,
                decision="BLOCK",
                reason=shutoff_reason,
                input_tokens=0,
                output_tokens=0,
                prompt_fingerprint=prompt_fingerprint,
            )
            await session.commit()
            return self._blocked_result(
                api_call_id, request_id, correlation_id, requested_model, shutoff_reason
            )

        reserved_ok = await self._reserve(
            session=session,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            endpoint=endpoint,
            request_id=request_id,
            month=month,
            reservation=reservation,
            cap_cents=max(0, int(settings.LLM_MONTHLY_CAP_CENTS)),
        )
        if not reserved_ok:
            await self._finalize_blocked(session, api_call_id, "monthly_cap_exceeded")
            await self._write_call_audit(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                requested_model=requested_model,
                resolved_model=requested_model,
                estimated_cost_cents=reservation,
                decision="BLOCK",
                reason="monthly_cap_exceeded",
                input_tokens=0,
                output_tokens=0,
                prompt_fingerprint=prompt_fingerprint,
            )
            await session.commit()
            return self._blocked_result(
                api_call_id,
                request_id,
                correlation_id,
                requested_model,
                "monthly_cap_exceeded",
            )

        cache_enabled = bool(prompt.get("cache_enabled", True))
        cache_replay_state = "cold_miss_provider_allowed"
        cache_validation_failed = False
        validation_failure_sink_attempted = False
        validation_failure_sink_degraded_reason: str | None = None
        if cache_enabled:
            cache_probe = await self._cache_probe(
                session, model.tenant_id, model.user_id, endpoint, key, watermark
            )
            if cache_probe.state == "stale_mismatch":
                if stale_replay_rejection_enabled:
                    await self._release(
                        session,
                        model.tenant_id,
                        model.user_id,
                        endpoint,
                        request_id,
                        month,
                        reservation,
                    )
                    stale_metadata: dict[str, Any] = {
                        "boundary_id": self.boundary_id,
                        "cache_replay_state": "stale_replay_rejected_provider_blocked",
                        "cache_current_watermark": int(watermark),
                        "cache_row_watermark": int(cache_probe.row_watermark or 0),
                        "provider_reentry_blocked": True,
                        "stale_replay_reason": "authoritative_watermark_mismatch",
                    }
                    _inject_prewarm_metadata(stale_metadata)
                    if truth_snapshot:
                        stale_metadata["truth_snapshot"] = dict(truth_snapshot)
                    await self._finalize_blocked(
                        session,
                        api_call_id,
                        "stale_replay_rejected",
                        response_metadata=stale_metadata,
                    )
                    await self._write_call_audit(
                        session=session,
                        tenant_id=model.tenant_id,
                        user_id=model.user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        requested_model=requested_model,
                        resolved_model=requested_model,
                        estimated_cost_cents=0,
                        decision="BLOCK",
                        reason="stale_replay_rejected",
                        input_tokens=0,
                        output_tokens=0,
                        prompt_fingerprint=prompt_fingerprint,
                    )
                    await session.commit()
                    return ProviderBoundaryResult(
                        provider="cache",
                        model=requested_model,
                        output_text="",
                        reasoning_trace={},
                        usage={
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "cost_cents": 0,
                            "latency_ms": 0,
                        },
                        status="blocked",
                        was_cached=False,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        api_call_id=api_call_id,
                        block_reason="stale_replay_rejected",
                        failure_reason="stale_replay_rejected",
                        response_metadata=stale_metadata,
                        validation_code="stale_replay_rejected",
                        validation_stage="cache",
                    )
                cache_replay_state = "stale_replay_bypassed_provider_allowed"
            if cache_probe.state == "hit" and cache_probe.row is not None:
                hit = cache_probe.row
                cache_replay_state = "cache_hit_truth_match"
                if self._is_active_numeric_rejection_marker(
                    row=hit,
                    now=now,
                    validation_context_fingerprint=validation_context_fingerprint,
                ):
                    await self._mark_cache_hit(session, hit)
                    await self._release(
                        session,
                        model.tenant_id,
                        model.user_id,
                        endpoint,
                        request_id,
                        month,
                        reservation,
                    )
                    usage = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost_cents": 0,
                        "latency_ms": 0,
                    }
                    cached_metadata = dict(hit.response_metadata_ref or {})
                    cached_metadata["boundary_id"] = self.boundary_id
                    cached_metadata["validation_code"] = "numeric_mismatch"
                    cached_metadata["validation_stage"] = "cache"
                    cached_metadata["cache_replay_state"] = cache_replay_state
                    cached_metadata["provider_reentry_blocked"] = False
                    _inject_prewarm_metadata(cached_metadata)
                    if truth_snapshot:
                        cached_metadata["truth_snapshot"] = dict(truth_snapshot)
                    await self._finalize_failed(
                        session,
                        api_call_id,
                        "validation_numeric_mismatch",
                        response_metadata=cached_metadata,
                    )
                    await self._write_call_audit(
                        session=session,
                        tenant_id=model.tenant_id,
                        user_id=model.user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        requested_model=requested_model,
                        resolved_model=str(hit.model),
                        estimated_cost_cents=0,
                        decision="ALLOW",
                        reason="cache_numeric_rejection_marker",
                        input_tokens=0,
                        output_tokens=0,
                        prompt_fingerprint=prompt_fingerprint,
                    )
                    await session.commit()
                    return ProviderBoundaryResult(
                        provider=str(hit.provider),
                        model=str(hit.model),
                        output_text="",
                        reasoning_trace=hit.reasoning_trace_ref,
                        usage=usage,
                        status="failed",
                        was_cached=True,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        api_call_id=api_call_id,
                        failure_reason="validation_numeric_mismatch",
                        response_metadata=cached_metadata,
                        validation_code="numeric_mismatch",
                        validation_stage="cache",
                    )

                cache_validation = self._validate_output_text(
                    raw_output_text=str(hit.response_text),
                    validation_spec=validation_spec,
                    stage="cache",
                    validation_context=validation_context,
                )
                if cache_validation.ok:
                    await self._mark_cache_hit(session, hit)
                    await self._release(
                        session,
                        model.tenant_id,
                        model.user_id,
                        endpoint,
                        request_id,
                        month,
                        reservation,
                    )
                    usage = {
                        "input_tokens": int(hit.input_tokens),
                        "output_tokens": int(hit.output_tokens),
                        "cost_cents": 0,
                        "latency_ms": 0,
                    }
                    cached_metadata = dict(hit.response_metadata_ref or {})
                    cached_metadata["boundary_id"] = self.boundary_id
                    cached_metadata["validation_code"] = cache_validation.code
                    cached_metadata["validation_stage"] = cache_validation.stage
                    cached_metadata["validation_schema_key"] = (
                        cache_validation.schema_key
                    )
                    cached_metadata["normalization_source"] = (
                        cache_validation.normalization_source
                    )
                    cached_metadata["validation_context_fingerprint"] = (
                        validation_context_fingerprint
                    )
                    cached_metadata["cache_replay_state"] = cache_replay_state
                    cached_metadata["provider_reentry_blocked"] = False
                    _inject_prewarm_metadata(cached_metadata)
                    if truth_snapshot:
                        cached_metadata["truth_snapshot"] = dict(truth_snapshot)
                    await self._finalize_success(
                        session=session,
                        api_call_id=api_call_id,
                        provider=str(hit.provider),
                        model_name=str(hit.model),
                        output_text=cache_validation.normalized_output_text,
                        usage=usage,
                        was_cached=True,
                        response_metadata=cached_metadata,
                        reasoning_trace=hit.reasoning_trace_ref or {},
                        reservation=reservation,
                        settled=0,
                        breaker_state="closed",
                    )
                    await self._write_call_audit(
                        session=session,
                        tenant_id=model.tenant_id,
                        user_id=model.user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        requested_model=requested_model,
                        resolved_model=str(hit.model),
                        estimated_cost_cents=0,
                        decision="ALLOW",
                        reason="cache_hit",
                        input_tokens=int(hit.input_tokens),
                        output_tokens=int(hit.output_tokens),
                        prompt_fingerprint=prompt_fingerprint,
                    )
                    await session.commit()
                    return ProviderBoundaryResult(
                        provider=str(hit.provider),
                        model=str(hit.model),
                        output_text=cache_validation.normalized_output_text,
                        reasoning_trace=hit.reasoning_trace_ref,
                        usage=usage,
                        status="success",
                        was_cached=True,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        api_call_id=api_call_id,
                        response_metadata=cached_metadata,
                        validation_code=cache_validation.code,
                        validation_stage=cache_validation.stage,
                        validated_output=cache_validation.normalized_payload,
                    )

                cache_validation_failed = True
                sink_outcome = await self._record_validation_failure(
                    session=session,
                    tenant_id=model.tenant_id,
                    endpoint=endpoint,
                    validation_error=f"cache_{cache_validation.code}",
                    request_id=request_id,
                    correlation_id=correlation_id,
                    request_payload={
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                        "endpoint": endpoint,
                        "validation_schema_key": cache_validation.schema_key,
                        "stage": "cache",
                        "validation_context": dict(validation_context or {}),
                    },
                    response_payload={
                        "provider": str(hit.provider),
                        "model": str(hit.model),
                        "output_text": str(hit.response_text),
                        "validation_error": cache_validation.error_detail,
                    },
                )
                validation_failure_sink_attempted = True
                if (
                    sink_outcome.is_degraded
                    and validation_failure_sink_degraded_reason is None
                ):
                    validation_failure_sink_degraded_reason = (
                        sink_outcome.degraded_reason
                    )
                if cache_validation.code == "numeric_mismatch":
                    await self._cache_write_numeric_rejection_marker(
                        session=session,
                        tenant_id=model.tenant_id,
                        user_id=model.user_id,
                        endpoint=endpoint,
                        key=key,
                        watermark=watermark,
                        provider=str(hit.provider),
                        model_name=str(hit.model),
                        validation_context_fingerprint=validation_context_fingerprint,
                        validation_error=cache_validation.error_detail
                        or "cache_numeric_mismatch",
                        truth_snapshot=truth_snapshot,
                    )
                    await self._mark_cache_hit(session, hit)
                    await self._release(
                        session,
                        model.tenant_id,
                        model.user_id,
                        endpoint,
                        request_id,
                        month,
                        reservation,
                    )
                    usage = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost_cents": 0,
                        "latency_ms": 0,
                    }
                    cached_metadata = dict(hit.response_metadata_ref or {})
                    cached_metadata["boundary_id"] = self.boundary_id
                    cached_metadata["validation_code"] = "numeric_mismatch"
                    cached_metadata["validation_stage"] = "cache"
                    cached_metadata["validation_schema_key"] = (
                        cache_validation.schema_key
                    )
                    cached_metadata["normalization_source"] = (
                        cache_validation.normalization_source
                    )
                    cached_metadata["validation_context_fingerprint"] = (
                        validation_context_fingerprint
                    )
                    cached_metadata["cache_replay_state"] = cache_replay_state
                    cached_metadata["provider_reentry_blocked"] = False
                    if truth_snapshot:
                        cached_metadata["truth_snapshot"] = dict(truth_snapshot)
                    cached_metadata.update(
                        self._validation_failure_sink_metadata(
                            attempted=validation_failure_sink_attempted,
                            degraded_reason=validation_failure_sink_degraded_reason,
                        )
                    )
                    await self._finalize_failed(
                        session,
                        api_call_id,
                        "validation_numeric_mismatch",
                        response_metadata=cached_metadata,
                    )
                    await self._write_call_audit(
                        session=session,
                        tenant_id=model.tenant_id,
                        user_id=model.user_id,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        requested_model=requested_model,
                        resolved_model=str(hit.model),
                        estimated_cost_cents=0,
                        decision="ALLOW",
                        reason="cache_numeric_mismatch_degraded",
                        input_tokens=0,
                        output_tokens=0,
                        prompt_fingerprint=prompt_fingerprint,
                    )
                    await session.commit()
                    return ProviderBoundaryResult(
                        provider=str(hit.provider),
                        model=str(hit.model),
                        output_text="",
                        reasoning_trace=hit.reasoning_trace_ref,
                        usage=usage,
                        status="failed",
                        was_cached=True,
                        request_id=request_id,
                        correlation_id=correlation_id,
                        api_call_id=api_call_id,
                        failure_reason="validation_numeric_mismatch",
                        response_metadata=cached_metadata,
                        validation_code="numeric_mismatch",
                        validation_stage="cache",
                    )
                await self._invalidate_cache_row(session, hit)

        if await self._breaker_open(session, model.tenant_id, model.user_id, now):
            await self._release(
                session,
                model.tenant_id,
                model.user_id,
                endpoint,
                request_id,
                month,
                reservation,
            )
            await self._finalize_blocked(session, api_call_id, "breaker_open")
            await self._write_call_audit(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                requested_model=requested_model,
                resolved_model=requested_model,
                estimated_cost_cents=reservation,
                decision="BLOCK",
                reason="breaker_open",
                input_tokens=0,
                output_tokens=0,
                prompt_fingerprint=prompt_fingerprint,
            )
            await session.commit()
            return self._blocked_result(
                api_call_id, request_id, correlation_id, requested_model, "breaker_open"
            )

        # Reservation and pre-call guards are committed before the network call so
        # no transaction is held open while waiting on provider latency.
        await session.commit()

        effective_timeout_ms = (
            int(timeout_ms_override)
            if timeout_ms_override is not None
            else int(settings.LLM_PROVIDER_TIMEOUT_MS)
        )
        timeout_s = max(0.001, effective_timeout_ms / 1000.0)
        max_validation_attempts = self._request_local_attempt_budget(validation_spec)
        total_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_cents": 0,
            "latency_ms": 0,
        }
        attempts_executed = 0
        correction_payload: dict[str, Any] | None = None
        last_payload: Mapping[str, Any] | None = None
        last_validation: OutputValidationResult | None = None
        successful_payload: Mapping[str, Any] | None = None
        successful_validation: OutputValidationResult | None = None
        try:
            for attempt in range(1, max_validation_attempts + 1):
                attempts_executed = attempt
                attempt_prompt = self._prompt_for_attempt(
                    base_prompt=prompt,
                    attempt=attempt,
                    max_attempts=max_validation_attempts,
                    correction_payload=correction_payload,
                )
                started = time.perf_counter()
                payload = await asyncio.wait_for(
                    self._provider_call(
                        requested_model=requested_model,
                        prompt=attempt_prompt,
                        reservation=reservation,
                    ),
                    timeout=timeout_s,
                )
                if force_failure:
                    raise RuntimeError("forced_failure_after_provider_call")

                usage = dict(payload.get("usage", {}))
                usage.setdefault("input_tokens", 0)
                usage.setdefault("output_tokens", 0)
                usage.setdefault("cost_cents", 0)
                usage["latency_ms"] = max(
                    1, int((time.perf_counter() - started) * 1000)
                )
                total_usage["input_tokens"] += max(0, int(usage.get("input_tokens", 0)))
                total_usage["output_tokens"] += max(
                    0, int(usage.get("output_tokens", 0))
                )
                total_usage["cost_cents"] += max(0, int(usage.get("cost_cents", 0)))
                total_usage["latency_ms"] += max(0, int(usage.get("latency_ms", 0)))

                last_payload = payload
                validation = self._validate_output_text(
                    raw_output_text=str(payload.get("output_text", "")),
                    validation_spec=validation_spec,
                    stage="provider",
                    validation_context=validation_context,
                )
                last_validation = validation
                if validation.ok:
                    normalized_payload = dict(payload)
                    normalized_payload["output_text"] = (
                        validation.normalized_output_text
                    )
                    successful_payload = normalized_payload
                    successful_validation = validation
                    break

                sink_outcome = await self._record_validation_failure(
                    session=session,
                    tenant_id=model.tenant_id,
                    endpoint=endpoint,
                    validation_error=validation.code,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    request_payload={
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                        "endpoint": endpoint,
                        "attempt": attempt,
                        "max_attempts": max_validation_attempts,
                        "request_local_attempt_budget": max_validation_attempts,
                        "validation_schema_key": validation.schema_key,
                        "validation_context": dict(validation_context or {}),
                        "validation_correction_payload": (
                            dict(correction_payload)
                            if correction_payload is not None
                            else None
                        ),
                    },
                    response_payload={
                        "provider": str(payload.get("provider", "unknown")),
                        "model": str(payload.get("model", requested_model)),
                        "output_text": str(payload.get("output_text", "")),
                        "validation_error": validation.error_detail,
                    },
                )
                validation_failure_sink_attempted = True
                if (
                    sink_outcome.is_degraded
                    and validation_failure_sink_degraded_reason is None
                ):
                    validation_failure_sink_degraded_reason = (
                        sink_outcome.degraded_reason
                    )
                if attempt < max_validation_attempts:
                    correction_payload = self._build_validation_correction_payload(
                        validation=validation,
                        attempt=attempt,
                        max_attempts=max_validation_attempts,
                        validation_spec=validation_spec,
                    )

            if successful_payload is None:
                failed_at = await self._db_now(session)
                validation_reason = "validation_failed"
                if last_validation is not None:
                    validation_reason = (
                        "validation_normalization_failed"
                        if last_validation.code == "normalization_failed"
                        else (
                            "validation_schema_failed"
                            if last_validation.code == "schema_failed"
                            else "validation_numeric_mismatch"
                        )
                    )
                if cache_enabled and validation_reason == "validation_numeric_mismatch":
                    await self._cache_write_numeric_rejection_marker(
                        session=session,
                        tenant_id=model.tenant_id,
                        user_id=model.user_id,
                        endpoint=endpoint,
                        key=key,
                        watermark=watermark,
                        provider=str(
                            (last_payload or {}).get("provider") or "validation"
                        ),
                        model_name=str(
                            (last_payload or {}).get("model") or requested_model
                        ),
                        validation_context_fingerprint=validation_context_fingerprint,
                        validation_error=(
                            last_validation.error_detail
                            if last_validation is not None
                            else "numeric_mismatch"
                        ),
                        truth_snapshot=truth_snapshot,
                    )
                await self._ensure_rls_context(session, model.tenant_id, model.user_id)
                settled = min(max(0, int(total_usage["cost_cents"])), reservation)
                await self._settle(
                    session,
                    model.tenant_id,
                    model.user_id,
                    endpoint,
                    request_id,
                    month,
                    reservation,
                    settled,
                )
                await self._breaker_success(session, model.tenant_id, model.user_id)
                settled_at = await self._db_now(session)
                await self._hourly_record(
                    session, model.tenant_id, model.user_id, settled_at, settled
                )
                await self._monthly_cost_record(
                    session,
                    model.tenant_id,
                    model.user_id,
                    str((last_payload or {}).get("model") or requested_model),
                    settled,
                    created_at,
                )
                await self._apply_breaker_failure_accounting(
                    session=session,
                    tenant_id=model.tenant_id,
                    user_id=model.user_id,
                    failed_at=failed_at,
                    failure_reason=validation_reason,
                )
                failed_metadata = {
                    "raw_output_text": str(
                        (last_payload or {}).get("output_text") or ""
                    ),
                    "validation_error": (
                        last_validation.error_detail
                        if last_validation is not None
                        else None
                    ),
                    "validation_attempts": attempts_executed,
                    "validation_attempt_budget": max_validation_attempts,
                    "validation_regeneration_active": attempts_executed > 1,
                    "validation_correction_payload": (
                        correction_payload if correction_payload is not None else None
                    ),
                    "validation_policy": (
                        "b1.6-p3-numeric-authority-v1"
                        if validation_reason == "validation_numeric_mismatch"
                        else None
                    ),
                    "cache_replay_state": cache_replay_state,
                    "provider_reentry_blocked": False,
                }
                _inject_prewarm_metadata(failed_metadata)
                if truth_snapshot:
                    failed_metadata["truth_snapshot"] = dict(truth_snapshot)
                failed_metadata.update(
                    self._validation_failure_sink_metadata(
                        attempted=validation_failure_sink_attempted,
                        degraded_reason=validation_failure_sink_degraded_reason,
                    )
                )
                await self._finalize_failed(
                    session,
                    api_call_id,
                    validation_reason,
                    response_metadata=failed_metadata,
                )
                await self._write_call_audit(
                    session=session,
                    tenant_id=model.tenant_id,
                    user_id=model.user_id,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    requested_model=requested_model,
                    resolved_model=str(
                        (last_payload or {}).get("model") or requested_model
                    ),
                    estimated_cost_cents=settled,
                    decision="ALLOW",
                    reason=validation_reason,
                    input_tokens=int(total_usage.get("input_tokens", 0)),
                    output_tokens=int(total_usage.get("output_tokens", 0)),
                    prompt_fingerprint=prompt_fingerprint,
                )
                await session.commit()
                return ProviderBoundaryResult(
                    provider=str((last_payload or {}).get("provider") or "validation"),
                    model=str((last_payload or {}).get("model") or requested_model),
                    output_text="",
                    reasoning_trace=None,
                    usage=total_usage,
                    status="failed",
                    was_cached=False,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    api_call_id=api_call_id,
                    failure_reason=validation_reason,
                    response_metadata=failed_metadata,
                    validation_code=validation_reason.removeprefix("validation_"),
                    validation_stage="provider",
                )

            settled = min(max(0, int(total_usage["cost_cents"])), reservation)
            settled_at = await self._db_now(session)
            await self._ensure_rls_context(session, model.tenant_id, model.user_id)
            await self._settle(
                session,
                model.tenant_id,
                model.user_id,
                endpoint,
                request_id,
                month,
                reservation,
                settled,
            )
            await self._breaker_success(session, model.tenant_id, model.user_id)
            await self._hourly_record(
                session, model.tenant_id, model.user_id, settled_at, settled
            )
            await self._monthly_cost_record(
                session,
                model.tenant_id,
                model.user_id,
                str(successful_payload["model"]),
                settled,
                created_at,
            )
            metadata = dict(successful_payload.get("response_metadata", {}))
            metadata["boundary_id"] = self.boundary_id
            metadata["validation_code"] = (
                successful_validation.code if successful_validation else "success"
            )
            metadata["validation_stage"] = (
                successful_validation.stage if successful_validation else "provider"
            )
            metadata["validation_schema_key"] = (
                successful_validation.schema_key if successful_validation else None
            )
            metadata["normalization_source"] = (
                successful_validation.normalization_source
                if successful_validation
                else None
            )
            metadata["validation_context_fingerprint"] = validation_context_fingerprint
            metadata["validation_attempts"] = attempts_executed
            metadata["validation_attempt_budget"] = max_validation_attempts
            metadata["validation_regeneration_active"] = attempts_executed > 1
            metadata["validation_correction_payload"] = (
                correction_payload if correction_payload is not None else None
            )
            metadata["cache_invalidated"] = cache_validation_failed
            metadata["cache_replay_state"] = cache_replay_state
            metadata["provider_reentry_blocked"] = False
            _inject_prewarm_metadata(metadata)
            if truth_snapshot:
                metadata["truth_snapshot"] = dict(truth_snapshot)
            metadata.update(
                self._validation_failure_sink_metadata(
                    attempted=validation_failure_sink_attempted,
                    degraded_reason=validation_failure_sink_degraded_reason,
                )
            )
            if cache_enabled:
                cache_payload = dict(successful_payload)
                cache_payload["response_metadata"] = metadata
                await self._cache_write(
                    session,
                    model.tenant_id,
                    model.user_id,
                    endpoint,
                    key,
                    watermark,
                    cache_payload,
                    total_usage,
                )
            await self._finalize_success(
                session=session,
                api_call_id=api_call_id,
                provider=str(successful_payload["provider"]),
                model_name=str(successful_payload["model"]),
                output_text=str(successful_payload["output_text"]),
                usage=total_usage,
                was_cached=False,
                response_metadata=metadata,
                reasoning_trace=successful_payload.get("reasoning_trace") or {},
                reservation=reservation,
                settled=settled,
                breaker_state="closed",
            )
            await self._write_call_audit(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                requested_model=requested_model,
                resolved_model=str(successful_payload["model"]),
                estimated_cost_cents=settled,
                decision="ALLOW",
                reason="success",
                input_tokens=int(total_usage.get("input_tokens", 0)),
                output_tokens=int(total_usage.get("output_tokens", 0)),
                prompt_fingerprint=prompt_fingerprint,
            )
            await session.commit()
            return ProviderBoundaryResult(
                provider=str(successful_payload["provider"]),
                model=str(successful_payload["model"]),
                output_text=str(successful_payload["output_text"]),
                reasoning_trace=successful_payload.get("reasoning_trace"),
                usage=total_usage,
                status="success",
                was_cached=False,
                request_id=request_id,
                correlation_id=correlation_id,
                api_call_id=api_call_id,
                response_metadata=metadata,
                validation_code=(
                    successful_validation.code if successful_validation else "success"
                ),
                validation_stage=(
                    successful_validation.stage if successful_validation else "provider"
                ),
                validated_output=(
                    successful_validation.normalized_payload
                    if successful_validation is not None
                    else None
                ),
            )
        except TimeoutError:
            failed_at = await self._db_now(session)
            failure_reason = "provider_timeout"
            timeout_metadata: dict[str, Any] = {
                "cache_replay_state": cache_replay_state,
                "provider_reentry_blocked": False,
            }
            _inject_prewarm_metadata(timeout_metadata)
            if truth_snapshot:
                timeout_metadata["truth_snapshot"] = dict(truth_snapshot)
            await self._ensure_rls_context(session, model.tenant_id, model.user_id)
            await self._release(
                session,
                model.tenant_id,
                model.user_id,
                endpoint,
                request_id,
                month,
                reservation,
            )
            await self._apply_breaker_failure_accounting(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                failed_at=failed_at,
                failure_reason=failure_reason,
            )
            await self._finalize_failed(
                session,
                api_call_id,
                failure_reason,
                response_metadata=timeout_metadata,
            )
            await self._write_call_audit(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                requested_model=requested_model,
                resolved_model=requested_model,
                estimated_cost_cents=0,
                decision="ALLOW",
                reason=failure_reason,
                input_tokens=0,
                output_tokens=0,
                prompt_fingerprint=prompt_fingerprint,
            )
            await session.commit()
            return ProviderBoundaryResult(
                provider="timeout",
                model=requested_model,
                output_text="",
                reasoning_trace=None,
                usage={
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_cents": 0,
                    "latency_ms": int(timeout_s * 1000),
                },
                status="failed",
                was_cached=False,
                request_id=request_id,
                correlation_id=correlation_id,
                api_call_id=api_call_id,
                failure_reason=failure_reason,
                response_metadata=timeout_metadata,
            )
        except Exception as exc:
            failed_at = await self._db_now(session)
            failure_reason = f"provider_error:{type(exc).__name__}"
            error_metadata: dict[str, Any] = {
                "cache_replay_state": cache_replay_state,
                "provider_reentry_blocked": False,
            }
            _inject_prewarm_metadata(error_metadata)
            if truth_snapshot:
                error_metadata["truth_snapshot"] = dict(truth_snapshot)
            await self._ensure_rls_context(session, model.tenant_id, model.user_id)
            await self._release(
                session,
                model.tenant_id,
                model.user_id,
                endpoint,
                request_id,
                month,
                reservation,
            )
            await self._apply_breaker_failure_accounting(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                failed_at=failed_at,
                failure_reason=failure_reason,
            )
            await self._finalize_failed(
                session,
                api_call_id,
                failure_reason,
                response_metadata=error_metadata,
            )
            await self._write_call_audit(
                session=session,
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                requested_model=requested_model,
                resolved_model=requested_model,
                estimated_cost_cents=0,
                decision="ALLOW",
                reason=failure_reason,
                input_tokens=0,
                output_tokens=0,
                prompt_fingerprint=prompt_fingerprint,
            )
            await session.commit()
            return ProviderBoundaryResult(
                provider="error",
                model=requested_model,
                output_text="",
                reasoning_trace=None,
                usage={
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_cents": 0,
                    "latency_ms": 0,
                },
                status="failed",
                was_cached=False,
                request_id=request_id,
                correlation_id=correlation_id,
                api_call_id=api_call_id,
                failure_reason=failure_reason,
                response_metadata=error_metadata,
            )

    async def _write_call_audit(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        request_id: str,
        correlation_id: str,
        requested_model: str,
        resolved_model: str,
        estimated_cost_cents: int,
        decision: str,
        reason: str,
        input_tokens: int,
        output_tokens: int,
        prompt_fingerprint: str,
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO llm_call_audit (
                    tenant_id,
                    user_id,
                    request_id,
                    correlation_id,
                    requested_model,
                    resolved_model,
                    estimated_cost_cents,
                    cap_cents,
                    decision,
                    reason,
                    input_tokens,
                    output_tokens,
                    prompt_fingerprint
                ) VALUES (
                    :tenant_id,
                    :user_id,
                    :request_id,
                    :correlation_id,
                    :requested_model,
                    :resolved_model,
                    :estimated_cost_cents,
                    :cap_cents,
                    :decision,
                    :reason,
                    :input_tokens,
                    :output_tokens,
                    :prompt_fingerprint
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "requested_model": requested_model,
                "resolved_model": resolved_model,
                "estimated_cost_cents": max(0, int(estimated_cost_cents)),
                "cap_cents": max(0, int(settings.LLM_MONTHLY_CAP_CENTS)),
                "decision": decision,
                "reason": reason,
                "input_tokens": max(0, int(input_tokens)),
                "output_tokens": max(0, int(output_tokens)),
                "prompt_fingerprint": prompt_fingerprint,
            },
        )

    async def _current_budget_state(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Mapping[str, int]:
        now = await self._db_now(session)
        month = _month_start_utc(now)
        row = (
            await session.execute(
                text(
                    """
                    SELECT cap_cents, spent_cents, reserved_cents
                    FROM llm_monthly_budget_state
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND month = :month
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "user_id": user_id, "month": month},
            )
        ).first()
        if row is None:
            return {
                "cap_cents": max(0, int(settings.LLM_MONTHLY_CAP_CENTS)),
                "spent_cents": 0,
                "reserved_cents": 0,
            }
        return {
            "cap_cents": int(row[0] or 0),
            "spent_cents": int(row[1] or 0),
            "reserved_cents": int(row[2] or 0),
        }

    async def _ensure_rls_context(
        self, session: AsyncSession, tenant_id: UUID, user_id: UUID
    ) -> None:
        await set_tenant_guc_async(session, tenant_id, local=False)
        await set_user_guc_async(session, user_id, local=False)

    def _blocked_result(
        self,
        api_call_id: UUID,
        request_id: str,
        correlation_id: str,
        model_name: str,
        reason: str,
    ) -> ProviderBoundaryResult:
        return ProviderBoundaryResult(
            provider="blocked",
            model=model_name,
            output_text="",
            reasoning_trace=None,
            usage={
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_cents": 0,
                "latency_ms": 0,
            },
            status="blocked",
            was_cached=False,
            request_id=request_id,
            correlation_id=correlation_id,
            api_call_id=api_call_id,
            block_reason=reason,
        )

    def _validate_output_text(
        self,
        *,
        raw_output_text: str,
        validation_spec: ProviderOutputValidationSpec | None,
        stage: str,
        validation_context: Mapping[str, Any] | None = None,
    ) -> OutputValidationResult:
        return validate_provider_output_text(
            raw_output_text=raw_output_text,
            validation_spec=validation_spec,
            stage=stage,
            validation_context=validation_context,
        )

    async def _record_validation_failure(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        endpoint: str,
        validation_error: str,
        request_id: str,
        correlation_id: str,
        request_payload: Mapping[str, Any],
        response_payload: Mapping[str, Any] | None,
    ) -> ValidationFailureSinkWriteOutcome:
        payload = dict(request_payload)
        payload.setdefault("request_id", request_id)
        payload.setdefault("correlation_id", correlation_id)
        return await self._validation_failure_service.record_failure_best_effort(
            session,
            tenant_id=tenant_id,
            endpoint=endpoint,
            validation_error=validation_error,
            request_payload=payload,
            response_payload=dict(response_payload or {}),
        )

    def _is_active_numeric_rejection_marker(
        self,
        *,
        row: LLMSemanticCache,
        now: datetime,
        validation_context_fingerprint: str,
    ) -> bool:
        metadata = dict(row.response_metadata_ref or {})
        if metadata.get("cache_numeric_state") != NUMERIC_REJECTION_CACHE_STATE:
            return False
        marker_fingerprint = str(metadata.get("validation_context_fingerprint") or "")
        if (
            validation_context_fingerprint
            and marker_fingerprint
            and marker_fingerprint != validation_context_fingerprint
        ):
            return False
        expires_at = _parse_iso8601_utc(
            str(metadata.get("cache_numeric_reject_until") or "")
        )
        if expires_at is None:
            return False
        return now < expires_at

    async def _cache_write_numeric_rejection_marker(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        key: str,
        watermark: int,
        provider: str,
        model_name: str,
        validation_context_fingerprint: str,
        validation_error: str,
        truth_snapshot: Mapping[str, Any] | None = None,
    ) -> None:
        now = await self._db_now(session)
        reject_until = now + timedelta(seconds=NUMERIC_REJECTION_CACHE_SUPPRESS_SECONDS)
        metadata = {
            "cache_invalidated": True,
            "cache_numeric_state": NUMERIC_REJECTION_CACHE_STATE,
            "cache_numeric_reject_until": reject_until.isoformat().replace(
                "+00:00", "Z"
            ),
            "cache_numeric_reject_reason": str(validation_error or "numeric_mismatch"),
            "validation_context_fingerprint": validation_context_fingerprint,
        }
        if isinstance(truth_snapshot, Mapping) and truth_snapshot:
            metadata["truth_snapshot"] = dict(truth_snapshot)
        stmt = (
            insert(LLMSemanticCache)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=endpoint,
                cache_key=key,
                watermark=watermark,
                provider=provider,
                model=model_name,
                response_text="",
                response_metadata_ref=metadata,
                reasoning_trace_ref={},
                input_tokens=0,
                output_tokens=0,
                cost_cents=0,
                hit_count=0,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "user_id", "endpoint", "cache_key"],
                set_={
                    "watermark": watermark,
                    "provider": provider,
                    "model": model_name,
                    "response_text": "",
                    "response_metadata_ref": metadata,
                    "reasoning_trace_ref": {},
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_cents": 0,
                    "updated_at": now,
                },
            )
        )
        await session.execute(stmt)

    async def _invalidate_cache_row(
        self, session: AsyncSession, row: LLMSemanticCache
    ) -> None:
        row.watermark = int(row.watermark) + 1
        row.response_text = ""
        metadata = dict(row.response_metadata_ref or {})
        metadata["cache_invalidated"] = True
        row.response_metadata_ref = metadata
        row.reasoning_trace_ref = {}
        row.updated_at = await self._db_now(session)
        await session.flush()

    async def _mark_cache_hit(
        self, session: AsyncSession, row: LLMSemanticCache
    ) -> None:
        row.hit_count = int(row.hit_count) + 1
        row.updated_at = await self._db_now(session)

    async def _claim(
        self,
        *,
        session: AsyncSession,
        model: LLMTaskPayload,
        endpoint: str,
        request_id: str,
        correlation_id: str,
        requested_model: str,
        reservation: int,
        cache_key: str,
        prompt_fingerprint: str,
        cache_watermark: int,
        routing: RoutingDecision,
    ) -> tuple[UUID, datetime, bool]:
        stmt = (
            insert(LLMApiCall)
            .values(
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                endpoint=endpoint,
                request_id=request_id,
                provider="pending",
                model=requested_model,
                input_tokens=0,
                output_tokens=0,
                cost_cents=0,
                latency_ms=0,
                was_cached=False,
                distillation_eligible=False,
                status="pending",
                breaker_state="closed",
                provider_attempted=False,
                budget_reservation_cents=reservation,
                budget_settled_cents=0,
                cache_key=cache_key,
                prompt_fingerprint=prompt_fingerprint,
                cache_watermark=cache_watermark,
                complexity_score=float(routing.complexity_score),
                complexity_bucket=int(routing.complexity_bucket),
                chosen_tier=routing.chosen_tier,
                chosen_provider=routing.chosen_provider,
                chosen_model=routing.chosen_model,
                policy_id=routing.policy_id,
                policy_version=routing.policy_version,
                routing_reason=routing.routing_reason,
                request_metadata_ref={
                    "correlation_id": correlation_id,
                    "boundary_id": self.boundary_id,
                },
            )
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "request_id", "endpoint"]
            )
            .returning(LLMApiCall.id, LLMApiCall.created_at)
        )
        row = (await session.execute(stmt)).first()
        if row is not None:
            return row[0], row[1], True
        existing = (
            await session.execute(
                select(LLMApiCall.id, LLMApiCall.created_at).where(
                    LLMApiCall.tenant_id == model.tenant_id,
                    LLMApiCall.request_id == request_id,
                    LLMApiCall.endpoint == endpoint,
                )
            )
        ).first()
        if existing is None:
            raise RuntimeError(
                "idempotency guard failed to locate existing llm_api_calls row"
            )
        return existing[0], existing[1], False

    async def _load_existing(
        self,
        *,
        session: AsyncSession,
        api_call_id: UUID,
        request_id: str,
        correlation_id: str,
        validation_spec: ProviderOutputValidationSpec | None = None,
        validation_context: Mapping[str, Any] | None = None,
    ) -> ProviderBoundaryResult:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row after idempotency replay")
        output_text = (row.response_metadata_ref or {}).get("output_text", "")
        replay_validation = self._validate_output_text(
            raw_output_text=str(output_text),
            validation_spec=validation_spec,
            stage="replay",
            validation_context=validation_context,
        )
        if row.status == "success" and not replay_validation.ok:
            return ProviderBoundaryResult(
                provider=row.provider,
                model=row.model,
                output_text="",
                reasoning_trace=row.reasoning_trace_ref,
                usage={
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                    "cost_cents": int(row.cost_cents),
                    "latency_ms": int(row.latency_ms),
                },
                status="failed",
                was_cached=bool(row.was_cached),
                request_id=request_id,
                correlation_id=correlation_id,
                api_call_id=api_call_id,
                failure_reason=f"validation_replay_{replay_validation.code}",
                response_metadata=row.response_metadata_ref,
                validation_code=replay_validation.code,
                validation_stage=replay_validation.stage,
            )
        return ProviderBoundaryResult(
            provider=row.provider,
            model=row.model,
            output_text=(
                replay_validation.normalized_output_text
                if row.status == "success"
                else str(output_text or "")
            ),
            reasoning_trace=row.reasoning_trace_ref,
            usage={
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "cost_cents": int(row.cost_cents),
                "latency_ms": int(row.latency_ms),
            },
            status=row.status,
            was_cached=bool(row.was_cached),
            request_id=request_id,
            correlation_id=correlation_id,
            api_call_id=api_call_id,
            block_reason=row.block_reason,
            failure_reason=row.failure_reason,
            response_metadata=row.response_metadata_ref,
            validation_code=(
                replay_validation.code if row.status == "success" else None
            ),
            validation_stage=(
                replay_validation.stage if row.status == "success" else None
            ),
            validated_output=(
                replay_validation.normalized_payload
                if row.status == "success"
                else None
            ),
        )

    async def _hourly_block_reason(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> str | None:
        row = (
            (
                await session.execute(
                    select(LLMHourlyShutoffState)
                    .where(
                        LLMHourlyShutoffState.tenant_id == tenant_id,
                        LLMHourlyShutoffState.user_id == user_id,
                        LLMHourlyShutoffState.is_shutoff.is_(True),
                        LLMHourlyShutoffState.disabled_until.is_not(None),
                        LLMHourlyShutoffState.disabled_until > now,
                    )
                    .order_by(LLMHourlyShutoffState.disabled_until.desc())
                )
            )
            .scalars()
            .first()
        )
        return None if row is None else (row.reason or "hourly_shutoff_active")

    async def _reserve(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        request_id: str,
        month: date,
        reservation: int,
        cap_cents: int,
    ) -> bool:
        if reservation > cap_cents or reservation < 0:
            session.add(
                LLMBudgetReservation(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    endpoint=endpoint,
                    request_id=request_id,
                    month=month,
                    reserved_cents=max(0, reservation),
                    settled_cents=0,
                    state="blocked",
                )
            )
            return False
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO llm_monthly_budget_state (
                        tenant_id, user_id, month, cap_cents, spent_cents, reserved_cents, updated_at
                    ) VALUES (:tenant_id, :user_id, :month, :cap_cents, 0, :reservation, now())
                    ON CONFLICT (tenant_id, user_id, month)
                    DO UPDATE SET
                        cap_cents = EXCLUDED.cap_cents,
                        reserved_cents = llm_monthly_budget_state.reserved_cents + :reservation,
                        updated_at = now()
                    WHERE (
                        llm_monthly_budget_state.spent_cents
                        + llm_monthly_budget_state.reserved_cents
                        + :reservation
                    ) <= EXCLUDED.cap_cents
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "month": month,
                    "cap_cents": cap_cents,
                    "reservation": reservation,
                },
            )
        ).first()
        state = "reserved" if row is not None else "blocked"
        session.add(
            LLMBudgetReservation(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=endpoint,
                request_id=request_id,
                month=month,
                reserved_cents=max(0, reservation),
                settled_cents=0,
                state=state,
            )
        )
        return row is not None

    async def _release(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        request_id: str,
        month: date,
        reservation: int,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE llm_monthly_budget_state
                SET reserved_cents = GREATEST(0, reserved_cents - :reservation), updated_at = now()
                WHERE tenant_id = :tenant_id AND user_id = :user_id AND month = :month
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "month": month,
                "reservation": reservation,
            },
        )
        await session.execute(
            text(
                """
                UPDATE llm_budget_reservations
                SET state = 'released', settled_cents = 0, updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND endpoint = :endpoint
                  AND request_id = :request_id
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "endpoint": endpoint,
                "request_id": request_id,
            },
        )

    async def _settle(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        request_id: str,
        month: date,
        reservation: int,
        settled: int,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE llm_monthly_budget_state
                SET
                    reserved_cents = GREATEST(0, reserved_cents - :reservation),
                    spent_cents = spent_cents + :settled,
                    updated_at = now()
                WHERE tenant_id = :tenant_id AND user_id = :user_id AND month = :month
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "month": month,
                "reservation": reservation,
                "settled": settled,
            },
        )

    @staticmethod
    def _is_breaker_eligible_failure(failure_reason: str) -> bool:
        """
        Breaker policy lock for B1.6-P1.

        Only provider/transport failures are breaker-accountable.
        Semantic validation failures (e.g., ``validation_*``) are request-local and
        must not open the global provider breaker.
        """
        return failure_reason == "provider_timeout" or failure_reason.startswith(
            "provider_error:"
        )

    async def _apply_breaker_failure_accounting(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        failed_at: datetime,
        failure_reason: str,
    ) -> None:
        if not self._is_breaker_eligible_failure(failure_reason):
            return
        await self._breaker_failure(session, tenant_id, user_id, failed_at)

    async def _breaker_open(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> bool:
        row = (
            (
                await session.execute(
                    select(LLMBreakerState).where(
                        LLMBreakerState.tenant_id == tenant_id,
                        LLMBreakerState.user_id == user_id,
                        LLMBreakerState.breaker_key == self.breaker_key,
                    )
                )
            )
            .scalars()
            .first()
        )
        if row is None or row.state != "open":
            return False
        opened = row.opened_at or row.updated_at
        if opened is None:
            return True
        cooldown = opened + timedelta(
            seconds=max(1, int(settings.LLM_BREAKER_OPEN_SECONDS))
        )
        if now < cooldown:
            return True
        row.state = "half_open"
        row.updated_at = now
        return False

    async def _breaker_success(
        self, session: AsyncSession, tenant_id: UUID, user_id: UUID
    ) -> None:
        now = await self._db_now(session)
        row = (
            (
                await session.execute(
                    select(LLMBreakerState).where(
                        LLMBreakerState.tenant_id == tenant_id,
                        LLMBreakerState.user_id == user_id,
                        LLMBreakerState.breaker_key == self.breaker_key,
                    )
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            session.add(
                LLMBreakerState(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    breaker_key=self.breaker_key,
                    state="closed",
                    failure_count=0,
                    opened_at=None,
                    last_trip_at=None,
                    updated_at=now,
                )
            )
            return
        row.state = "closed"
        row.failure_count = 0
        row.opened_at = None
        row.updated_at = now

    async def _breaker_failure(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> None:
        threshold = max(1, int(settings.LLM_BREAKER_FAILURE_THRESHOLD))
        row = (
            (
                await session.execute(
                    select(LLMBreakerState).where(
                        LLMBreakerState.tenant_id == tenant_id,
                        LLMBreakerState.user_id == user_id,
                        LLMBreakerState.breaker_key == self.breaker_key,
                    )
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            state = "open" if threshold <= 1 else "closed"
            session.add(
                LLMBreakerState(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    breaker_key=self.breaker_key,
                    state=state,
                    failure_count=1,
                    opened_at=now if state == "open" else None,
                    last_trip_at=now if state == "open" else None,
                    updated_at=now,
                )
            )
            return
        row.failure_count = int(row.failure_count or 0) + 1
        if row.failure_count >= threshold:
            row.state = "open"
            row.opened_at = now
            row.last_trip_at = now
        else:
            row.state = "closed"
        row.updated_at = now

    async def _cache_probe(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        key: str,
        watermark: int,
    ) -> CacheReplayProbeResult:
        row = (
            (
                await session.execute(
                    select(LLMSemanticCache).where(
                        LLMSemanticCache.tenant_id == tenant_id,
                        LLMSemanticCache.user_id == user_id,
                        LLMSemanticCache.endpoint == endpoint,
                        LLMSemanticCache.cache_key == key,
                    )
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            return CacheReplayProbeResult(state="miss")
        row_watermark = int(row.watermark)
        if row_watermark != int(watermark):
            return CacheReplayProbeResult(
                state="stale_mismatch",
                row=row,
                row_watermark=row_watermark,
            )
        return CacheReplayProbeResult(state="hit", row=row, row_watermark=row_watermark)

    async def _cache_write(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        key: str,
        watermark: int,
        payload: Mapping[str, Any],
        usage: Mapping[str, int],
    ) -> None:
        now = await self._db_now(session)
        stmt = (
            insert(LLMSemanticCache)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=endpoint,
                cache_key=key,
                watermark=watermark,
                provider=str(payload["provider"]),
                model=str(payload["model"]),
                response_text=str(payload["output_text"]),
                response_metadata_ref=payload.get("response_metadata"),
                reasoning_trace_ref=payload.get("reasoning_trace"),
                input_tokens=max(0, int(usage.get("input_tokens", 0))),
                output_tokens=max(0, int(usage.get("output_tokens", 0))),
                cost_cents=max(0, int(usage.get("cost_cents", 0))),
                hit_count=0,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "user_id", "endpoint", "cache_key"],
                set_={
                    "watermark": watermark,
                    "provider": str(payload["provider"]),
                    "model": str(payload["model"]),
                    "response_text": str(payload["output_text"]),
                    "response_metadata_ref": payload.get("response_metadata"),
                    "reasoning_trace_ref": payload.get("reasoning_trace"),
                    "input_tokens": max(0, int(usage.get("input_tokens", 0))),
                    "output_tokens": max(0, int(usage.get("output_tokens", 0))),
                    "cost_cents": max(0, int(usage.get("cost_cents", 0))),
                    "updated_at": now,
                },
            )
        )
        await session.execute(stmt)

    async def _provider_call(
        self,
        *,
        requested_model: str,
        prompt: Mapping[str, Any],
        reservation: int,
    ) -> Mapping[str, Any]:
        if settings.LLM_PROVIDER_ENABLED:
            return await self._call_aisuite(
                requested_model=requested_model, prompt=prompt
            )
        return await self._call_stub(
            requested_model=requested_model, prompt=prompt, reservation=reservation
        )

    async def _call_stub(
        self,
        *,
        requested_model: str,
        prompt: Mapping[str, Any],
        reservation: int,
    ) -> Mapping[str, Any]:
        if bool(prompt.get("raise_error", False)):
            raise RuntimeError("stub_provider_error")
        delay_ms = int(prompt.get("simulated_delay_ms", 0) or 0)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        canonical = _json(prompt)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        in_tokens = max(1, len(canonical) // 4)
        out_tokens = max(1, in_tokens // 2)
        requested_cost = int(prompt.get("simulated_cost_cents", 1) or 0)
        cost_cents = min(max(0, requested_cost), reservation)
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": str(prompt.get("simulated_output_text") or f"stub:{digest}"),
            "reasoning_trace": {"trace_type": "stub", "digest": digest},
            "response_metadata": {"source": "stub"},
            "usage": {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "cost_cents": cost_cents,
            },
        }

    async def _call_aisuite(
        self, *, requested_model: str, prompt: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        def _invoke_sync() -> Any:
            if aisuite is None:
                raise RuntimeError("aisuite_not_installed")
            client = aisuite.Client()
            messages = prompt.get("messages")
            if not isinstance(messages, list):
                user_text = prompt.get("input") or prompt.get("text") or _json(prompt)
                messages = [{"role": "user", "content": str(user_text)}]
            return client.chat.completions.create(
                model=requested_model, messages=messages
            )

        raw = await asyncio.to_thread(_invoke_sync)
        return self._normalize_aisuite(raw=raw, requested_model=requested_model)

    def _normalize_aisuite(
        self, *, raw: Any, requested_model: str
    ) -> Mapping[str, Any]:
        if isinstance(raw, Mapping):
            usage = raw.get("usage") or {}
            return {
                "provider": str(
                    raw.get("provider") or requested_model.split(":", 1)[0]
                ),
                "model": str(raw.get("model") or requested_model),
                "output_text": str(raw.get("output_text") or raw.get("text") or ""),
                "reasoning_trace": raw.get("reasoning_trace"),
                "response_metadata": raw.get("response_metadata") or {},
                "usage": {
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                    "cost_cents": int(usage.get("cost_cents", 0) or 0),
                },
            }
        provider = (
            requested_model.split(":", 1)[0] if ":" in requested_model else "aisuite"
        )
        model_name = str(getattr(raw, "model", requested_model))
        usage_obj = getattr(raw, "usage", None)
        usage = {
            "input_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
            "cost_cents": 0,
        }
        text_out = ""
        reasoning = None
        choices = getattr(raw, "choices", None)
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                text_out = str(getattr(msg, "content", "") or "")
                reasoning = getattr(msg, "reasoning", None)
        return {
            "provider": provider,
            "model": model_name,
            "output_text": text_out,
            "reasoning_trace": reasoning,
            "response_metadata": {"normalized_from": "aisuite"},
            "usage": usage,
        }

    async def _hourly_record(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
        settled: int,
    ) -> None:
        hour_start = _hour_start_utc(now)
        threshold = max(0, int(settings.LLM_HOURLY_SHUTOFF_CENTS))
        row = (
            (
                await session.execute(
                    select(LLMHourlyShutoffState).where(
                        LLMHourlyShutoffState.tenant_id == tenant_id,
                        LLMHourlyShutoffState.user_id == user_id,
                        LLMHourlyShutoffState.hour_start == hour_start,
                    )
                )
            )
            .scalars()
            .first()
        )
        if row is None:
            row = LLMHourlyShutoffState(
                tenant_id=tenant_id,
                user_id=user_id,
                hour_start=hour_start,
                threshold_cents=threshold,
                total_cost_cents=max(0, settled),
                total_calls=1,
                is_shutoff=False,
                reason=None,
                disabled_until=None,
            )
            session.add(row)
        else:
            row.threshold_cents = threshold
            row.total_cost_cents = int(row.total_cost_cents) + max(0, settled)
            row.total_calls = int(row.total_calls) + 1
            row.updated_at = now
        if threshold > 0 and row.total_cost_cents >= threshold:
            row.is_shutoff = True
            row.reason = "hourly_threshold_exceeded"
            row.disabled_until = hour_start + timedelta(hours=1)
            row.updated_at = now

    async def _monthly_cost_record(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        model_name: str,
        cost_cents: int,
        occurred_at: datetime,
    ) -> None:
        month = _month_start_utc(occurred_at)
        stmt = (
            insert(LLMMonthlyCost)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                month=month,
                total_cost_cents=max(0, cost_cents),
                total_calls=1,
                model_breakdown={
                    model_name: {"calls": 1, "cost_cents": max(0, cost_cents)}
                },
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "user_id", "month"],
                set_={
                    "total_cost_cents": LLMMonthlyCost.total_cost_cents
                    + max(0, cost_cents),
                    "total_calls": LLMMonthlyCost.total_calls + 1,
                    "model_breakdown": LLMMonthlyCost.model_breakdown,
                },
            )
        )
        await session.execute(stmt)

    async def _finalize_success(
        self,
        *,
        session: AsyncSession,
        api_call_id: UUID,
        provider: str,
        model_name: str,
        output_text: str,
        usage: Mapping[str, int],
        was_cached: bool,
        response_metadata: Mapping[str, Any],
        reasoning_trace: Mapping[str, Any],
        reservation: int,
        settled: int,
        breaker_state: str,
    ) -> None:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row on success finalize")
        metadata = dict(response_metadata)
        metadata["output_text"] = output_text
        row.provider = provider
        row.model = model_name
        row.input_tokens = max(0, int(usage.get("input_tokens", 0)))
        row.output_tokens = max(0, int(usage.get("output_tokens", 0)))
        row.cost_cents = max(0, int(usage.get("cost_cents", 0)))
        row.latency_ms = max(0, int(usage.get("latency_ms", 0)))
        row.was_cached = bool(was_cached)
        row.status = "success"
        row.provider_attempted = not was_cached
        row.breaker_state = breaker_state
        row.budget_reservation_cents = max(0, reservation)
        row.budget_settled_cents = max(0, settled)
        row.response_metadata_ref = metadata
        row.reasoning_trace_ref = dict(reasoning_trace or {})
        row.distillation_eligible = False
        row.block_reason = None
        row.failure_reason = None

    async def _finalize_blocked(
        self,
        session: AsyncSession,
        api_call_id: UUID,
        reason: str,
        response_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row on blocked finalize")
        row.status = "blocked"
        row.block_reason = reason
        row.failure_reason = None
        row.provider_attempted = False
        row.breaker_state = "open" if reason == "breaker_open" else "closed"
        metadata = dict(response_metadata or {})
        metadata.setdefault("output_text", "")
        row.response_metadata_ref = metadata
        row.reasoning_trace_ref = {}
        row.distillation_eligible = False

    async def _finalize_failed(
        self,
        session: AsyncSession,
        api_call_id: UUID,
        reason: str,
        response_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row on failed finalize")
        row.status = "failed"
        row.failure_reason = reason
        row.block_reason = None
        row.provider_attempted = True
        metadata = dict(response_metadata or {})
        metadata.setdefault("output_text", "")
        row.response_metadata_ref = metadata
        row.reasoning_trace_ref = {}
        row.distillation_eligible = False


def get_llm_provider_boundary() -> SkeldirLLMProvider:
    return SkeldirLLMProvider()

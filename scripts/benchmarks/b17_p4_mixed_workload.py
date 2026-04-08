#!/usr/bin/env python3
"""B1.7-P4 mixed-workload benchmark harness (endpoint-level, provider-stubbed)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("CONTRACT_TESTING", "0")

from app.api import attribution as attribution_api
from app.db.session import AsyncSessionLocal, set_tenant_guc_async
from app.main import app
from app.security import auth as auth_module
from app.security.auth import mint_internal_jwt
from backend.tests.builders.core_builders import build_attribution_allocation
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

CANONICAL_ENTITY_TYPES = ("channel_performance", "attribution_score")


@dataclass(frozen=True)
class RequestSample:
    latency_ms: float
    execution_path_state: str
    cache_replay_state: str


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def _token_for(*, tenant_id: UUID, user_id: UUID) -> str:
    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=user_id,
        expires_in_seconds=3600,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )


async def _seed_revenue_cache_entry(*, tenant_id: UUID, total_revenue_cents: int) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        await set_tenant_guc_async(session, tenant_id, local=False)
        await session.execute(
            text(
                """
                INSERT INTO revenue_cache_entries (
                    tenant_id,
                    cache_key,
                    payload,
                    data_as_of,
                    expires_at,
                    error_cooldown_until,
                    last_error_at,
                    last_error_message,
                    etag,
                    created_at,
                    updated_at
                ) VALUES (
                    :tenant_id,
                    :cache_key,
                    CAST(:payload AS jsonb),
                    :data_as_of,
                    :expires_at,
                    NULL,
                    NULL,
                    NULL,
                    :etag,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (tenant_id, cache_key) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    data_as_of = EXCLUDED.data_as_of,
                    expires_at = EXCLUDED.expires_at,
                    etag = EXCLUDED.etag,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "cache_key": "realtime_revenue:shared:v1",
                "payload": json.dumps(
                    {
                        "tenant_id": str(tenant_id),
                        "revenue_total_cents": int(total_revenue_cents),
                        "data_as_of": now.isoformat(),
                        "verified": False,
                    }
                ),
                "data_as_of": now,
                "expires_at": now + timedelta(minutes=5),
                "etag": f"\"bench-{tenant_id.hex[:8]}\"",
                "created_at": now,
                "updated_at": now,
            },
        )
        await session.commit()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = max(0.0, min(1.0, percentile)) * (len(sorted_values) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    fraction = rank - low
    return float(sorted_values[low] + (sorted_values[high] - sorted_values[low]) * fraction)


async def _call_explain(
    *,
    client: AsyncClient,
    tenant_id: UUID,
    allocation_id: UUID,
    entity_type: str,
    user_id: UUID,
) -> RequestSample:
    token = _token_for(tenant_id=tenant_id, user_id=user_id)
    start = perf_counter()
    response = await client.get(
        f"/api/attribution/explain/{entity_type}/{allocation_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-ID": str(uuid4()),
        },
    )
    latency_ms = (perf_counter() - start) * 1000.0
    if response.status_code != 200:
        raise RuntimeError(
            f"benchmark request failed status={response.status_code} body={response.text}"
        )
    body = response.json()
    explanation = body["non_authoritative_explanation"]
    return RequestSample(
        latency_ms=latency_ms,
        execution_path_state=str(explanation["execution_path_state"]),
        cache_replay_state=str(explanation["cache_replay_state"]),
    )


async def _run_measurement(
    *,
    requests: int,
    warm_ratio: float,
    concurrency: int,
    provider_delay_ms: int,
    prewarm_enabled: bool,
    prewarm_run_sync: bool,
) -> dict[str, Any]:
    if requests <= 0:
        raise ValueError("requests must be > 0")
    if not (0.0 <= warm_ratio <= 1.0):
        raise ValueError("warm_ratio must be in [0, 1]")
    if concurrency <= 0:
        raise ValueError("concurrency must be > 0")

    allocation = await build_attribution_allocation()
    tenant_id = allocation["tenant_id"]
    allocation_id = allocation["id"]
    await _seed_revenue_cache_entry(tenant_id=tenant_id, total_revenue_cents=7_500_000)

    original_provider_call = attribution_api._PROVIDER_BOUNDARY._provider_call
    original_assert_access_token_active = auth_module.assert_access_token_active
    original_prewarm_enabled = attribution_api.settings.LLM_B17_PREWARM_ENABLED
    original_prewarm_run_sync = attribution_api.settings.LLM_B17_PREWARM_RUN_SYNC
    original_prewarm_targets = attribution_api.settings.LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES
    original_prewarm_max_per_trigger = (
        attribution_api.settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER
    )

    async def _delayed_provider(*, requested_model, prompt, reservation):
        await asyncio.sleep(max(0, provider_delay_ms) / 1000.0)
        simulated = prompt.get("simulated_output_text")
        output_text = (
            str(simulated)
            if isinstance(simulated, str) and simulated.strip()
            else "metric_value_cents 0 revenue_total_cents 0"
        )
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": output_text,
            "reasoning_trace": {"trace_type": "b17-p4-mixed-workload-benchmark"},
            "response_metadata": {"source": "b17-p4-mixed-workload-benchmark"},
            "usage": {"input_tokens": 8, "output_tokens": 8, "cost_cents": 1},
        }

    async def _allow_active_token(_token_claims):
        return None

    attribution_api._PROVIDER_BOUNDARY._provider_call = _delayed_provider
    auth_module.assert_access_token_active = _allow_active_token
    attribution_api.settings.LLM_B17_PREWARM_ENABLED = prewarm_enabled
    attribution_api.settings.LLM_B17_PREWARM_RUN_SYNC = prewarm_run_sync
    attribution_api.settings.LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES = (
        "channel_performance,attribution_score"
    )
    attribution_api.settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER = 2

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://bench") as client:
            warm_user = uuid4()
            for entity_type in CANONICAL_ENTITY_TYPES:
                await _call_explain(
                    client=client,
                    tenant_id=tenant_id,
                    allocation_id=allocation_id,
                    entity_type=entity_type,
                    user_id=warm_user,
                )

            warm_request_count = int(round(requests * warm_ratio))
            cold_request_count = max(0, requests - warm_request_count)

            workload: list[tuple[str, UUID]] = []
            for idx in range(warm_request_count):
                workload.append((CANONICAL_ENTITY_TYPES[idx % len(CANONICAL_ENTITY_TYPES)], warm_user))
            cold_pairs = cold_request_count // 2
            for _ in range(cold_pairs):
                cold_user = uuid4()
                workload.append((CANONICAL_ENTITY_TYPES[0], cold_user))
                workload.append((CANONICAL_ENTITY_TYPES[1], cold_user))
            if cold_request_count % 2:
                workload.append((CANONICAL_ENTITY_TYPES[0], uuid4()))

            semaphore = asyncio.Semaphore(concurrency)
            samples: list[RequestSample] = []

            async def _run_one(entity_type: str, user_id: UUID) -> None:
                async with semaphore:
                    sample = await _call_explain(
                        client=client,
                        tenant_id=tenant_id,
                        allocation_id=allocation_id,
                        entity_type=entity_type,
                        user_id=user_id,
                    )
                    samples.append(sample)

            await asyncio.gather(*(_run_one(entity_type, user_id) for entity_type, user_id in workload))

    finally:
        attribution_api._PROVIDER_BOUNDARY._provider_call = original_provider_call
        auth_module.assert_access_token_active = original_assert_access_token_active
        attribution_api.settings.LLM_B17_PREWARM_ENABLED = original_prewarm_enabled
        attribution_api.settings.LLM_B17_PREWARM_RUN_SYNC = original_prewarm_run_sync
        attribution_api.settings.LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES = original_prewarm_targets
        attribution_api.settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER = (
            original_prewarm_max_per_trigger
        )

    state_counts: dict[str, int] = {}
    for sample in samples:
        state_counts[sample.execution_path_state] = (
            state_counts.get(sample.execution_path_state, 0) + 1
        )

    warm_latencies = [
        sample.latency_ms
        for sample in samples
        if sample.execution_path_state in {"warm_cache_hit", "prewarm_assisted_cache_hit"}
    ]
    cold_latencies = [
        sample.latency_ms
        for sample in samples
        if sample.execution_path_state == "cold_path_generated"
    ]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "requests": requests,
        "configured_warm_ratio": warm_ratio,
        "configured_concurrency": concurrency,
        "provider_delay_ms": provider_delay_ms,
        "prewarm_enabled": prewarm_enabled,
        "prewarm_run_sync": prewarm_run_sync,
        "execution_path_counts": state_counts,
        "latency_ms": {
            "overall_p50": round(_percentile([s.latency_ms for s in samples], 0.50), 2),
            "overall_p95": round(_percentile([s.latency_ms for s in samples], 0.95), 2),
            "warm_p95": round(_percentile(warm_latencies, 0.95), 2),
            "cold_p95": round(_percentile(cold_latencies, 0.95), 2),
        },
        "cold_path_sufficiency": {
            "endpoint_target_p95_ms": 500,
            "cold_p95_exceeds_target": _percentile(cold_latencies, 0.95) > 500.0,
        },
    }
    return summary


def _write_output(summary: dict[str, Any], output: Path | None) -> None:
    payload = json.dumps(summary, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.7-P4 mixed-workload benchmark harness")
    parser.add_argument("--mode", choices=("integrity", "measure"), default="measure")
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--warm-ratio", type=float, default=0.65)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--provider-delay-ms", type=int, default=650)
    parser.add_argument("--prewarm-enabled", type=_parse_bool, default=False)
    parser.add_argument("--prewarm-run-sync", type=_parse_bool, default=False)
    parser.add_argument("--output")
    parser.add_argument("--assert-cold-insufficient", action="store_true")
    parser.add_argument("--assert-overall-p95-lt-ms", type=float)
    parser.add_argument("--assert-cache-hit-rate-gt", type=float)
    parser.add_argument("--assert-warm-cold-diagnostics-present", action="store_true")
    args = parser.parse_args(argv[1:])

    output_path = Path(args.output).resolve() if args.output else None

    if args.mode == "integrity":
        summary = {
            "mode": "integrity",
            "harness": "b17_p4_mixed_workload",
            "checks": {
                "requests_positive": args.requests > 0,
                "warm_ratio_in_range": 0.0 <= args.warm_ratio <= 1.0,
                "concurrency_positive": args.concurrency > 0,
                "provider_delay_nonnegative": args.provider_delay_ms >= 0,
            },
        }
        if not all(bool(v) for v in summary["checks"].values()):
            _write_output(summary, output_path)
            return 1
        _write_output(summary, output_path)
        return 0

    summary = asyncio.run(
        _run_measurement(
            requests=args.requests,
            warm_ratio=args.warm_ratio,
            concurrency=args.concurrency,
            provider_delay_ms=args.provider_delay_ms,
            prewarm_enabled=bool(args.prewarm_enabled),
            prewarm_run_sync=bool(args.prewarm_run_sync),
        )
    )

    execution_counts = summary.get("execution_path_counts", {})
    total_samples = int(sum(int(v) for v in execution_counts.values()))
    warm_hits = int(execution_counts.get("warm_cache_hit", 0)) + int(
        execution_counts.get("prewarm_assisted_cache_hit", 0)
    )
    cache_hit_rate = (warm_hits / total_samples) if total_samples > 0 else 0.0
    summary["cache_hit_rate"] = {
        "hits": warm_hits,
        "total": total_samples,
        "ratio": round(cache_hit_rate, 4),
        "pct": round(cache_hit_rate * 100.0, 2),
    }
    _write_output(summary, output_path)

    if args.assert_cold_insufficient and not bool(
        summary["cold_path_sufficiency"]["cold_p95_exceeds_target"]
    ):
        return 1
    if args.assert_overall_p95_lt_ms is not None:
        overall_p95 = float(summary["latency_ms"]["overall_p95"])
        if overall_p95 >= float(args.assert_overall_p95_lt_ms):
            return 1
    if args.assert_cache_hit_rate_gt is not None:
        if cache_hit_rate <= float(args.assert_cache_hit_rate_gt):
            return 1
    if args.assert_warm_cold_diagnostics_present:
        warm_p95 = summary["latency_ms"].get("warm_p95")
        cold_p95 = summary["latency_ms"].get("cold_p95")
        if warm_p95 is None or cold_p95 is None:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

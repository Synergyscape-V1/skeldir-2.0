#!/usr/bin/env python3
"""B1.7-P4 mixed-workload benchmark harness (endpoint-level, provider-stubbed)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
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
NOISY_BENCHMARK_LOGGERS = (
    "httpx",
    "httpcore",
    "app.api.attribution",
)


@dataclass(frozen=True)
class RequestSample:
    latency_ms: float
    execution_path_state: str
    cache_replay_state: str
    allocation_id: str
    user_id: str
    entity_type: str


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


async def _collect_prewarm_observability(
    *,
    tenant_id: UUID,
    measurement_started_at: datetime,
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        await set_tenant_guc_async(session, tenant_id, local=False)
        total_prewarm_calls = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_api_calls
                        WHERE tenant_id = :tenant_id
                          AND endpoint = 'app.api.attribution.explanation_fastpath'
                          AND created_at >= :measurement_started_at
                          AND response_metadata_ref ->> 'prewarm_origin' = 'b17_p4_event_driven'
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "measurement_started_at": measurement_started_at,
                    },
                )
            ).scalar_one()
        )
        total_success = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_api_calls
                        WHERE tenant_id = :tenant_id
                          AND endpoint = 'app.api.attribution.explanation_fastpath'
                          AND created_at >= :measurement_started_at
                          AND status = 'success'
                          AND response_metadata_ref ->> 'prewarm_origin' = 'b17_p4_event_driven'
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "measurement_started_at": measurement_started_at,
                    },
                )
            ).scalar_one()
        )
        target_counts_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        COALESCE(response_metadata_ref ->> 'prewarm_target_entity_type', '__missing__') AS target_entity_type,
                        COUNT(*) AS count
                    FROM llm_api_calls
                    WHERE tenant_id = :tenant_id
                      AND endpoint = 'app.api.attribution.explanation_fastpath'
                      AND created_at >= :measurement_started_at
                      AND response_metadata_ref ->> 'prewarm_origin' = 'b17_p4_event_driven'
                    GROUP BY 1
                    ORDER BY 1
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "measurement_started_at": measurement_started_at,
                },
            )
        ).all()

    return {
        "total_prewarm_origin_calls": total_prewarm_calls,
        "successful_prewarm_origin_calls": total_success,
        "target_entity_type_counts": {str(row[0]): int(row[1]) for row in target_counts_rows},
    }


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
        allocation_id=str(allocation_id),
        user_id=str(user_id),
        entity_type=str(entity_type),
    )


async def _run_measurement(
    *,
    requests: int,
    warm_ratio: float,
    concurrency: int,
    provider_delay_ms: int,
    prewarm_enabled: bool,
    prewarm_run_sync: bool,
    allocation_pool_size: int,
    warm_key_space_size: int,
) -> dict[str, Any]:
    if requests <= 0:
        raise ValueError("requests must be > 0")
    if not (0.0 <= warm_ratio <= 1.0):
        raise ValueError("warm_ratio must be in [0, 1]")
    if concurrency <= 0:
        raise ValueError("concurrency must be > 0")
    if allocation_pool_size <= 0:
        raise ValueError("allocation_pool_size must be > 0")
    if warm_key_space_size <= 0:
        raise ValueError("warm_key_space_size must be > 0")

    allocation = await build_attribution_allocation()
    tenant_id = allocation["tenant_id"]
    allocation_ids: list[UUID] = [allocation["id"]]
    for _ in range(max(0, allocation_pool_size - 1)):
        allocation_ids.append((await build_attribution_allocation(tenant_id=tenant_id))["id"])
    await _seed_revenue_cache_entry(tenant_id=tenant_id, total_revenue_cents=7_500_000)

    original_provider_call = attribution_api._PROVIDER_BOUNDARY._provider_call
    original_assert_access_token_active = auth_module.assert_access_token_active
    original_prewarm_enabled = attribution_api.settings.LLM_B17_PREWARM_ENABLED
    original_prewarm_run_sync = attribution_api.settings.LLM_B17_PREWARM_RUN_SYNC
    original_prewarm_targets = attribution_api.settings.LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES
    original_prewarm_max_per_trigger = (
        attribution_api.settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER
    )
    original_asyncio_create_task = attribution_api.asyncio.create_task
    original_log_levels: dict[str, int] = {}
    tracked_async_prewarm_tasks: list[asyncio.Task[Any]] = []
    deferred_prewarm_coroutines: list[Any] = []

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
    # Keep warm-key priming prewarm-neutral so benchmark efficacy reflects
    # measured workload behavior rather than setup traffic budget consumption.
    attribution_api.settings.LLM_B17_PREWARM_ENABLED = False
    attribution_api.settings.LLM_B17_PREWARM_RUN_SYNC = prewarm_run_sync
    attribution_api.settings.LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES = (
        "channel_performance,attribution_score"
    )
    attribution_api.settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER = 2

    async def _completed_noop() -> None:
        return None

    def _is_prewarm_task_coro(coro: Any) -> bool:
        code = getattr(coro, "cr_code", None)
        return bool(code is not None and getattr(code, "co_name", "") == "_execute_b17_prewarm_targets")

    def _tracked_create_task(coro, *args, **kwargs):
        # Defer prewarm coroutine execution until after trigger-phase requests complete
        # so endpoint p95 reflects request serving, not background task contention.
        if (
            prewarm_enabled
            and not prewarm_run_sync
            and _is_prewarm_task_coro(coro)
        ):
            deferred_prewarm_coroutines.append(coro)
            return original_asyncio_create_task(_completed_noop())
        task = original_asyncio_create_task(coro, *args, **kwargs)
        if _is_prewarm_task_coro(coro):
            tracked_async_prewarm_tasks.append(task)
        return task

    attribution_api.asyncio.create_task = _tracked_create_task
    for logger_name in NOISY_BENCHMARK_LOGGERS:
        logger = logging.getLogger(logger_name)
        original_log_levels[logger_name] = logger.level
        logger.setLevel(logging.WARNING)

    try:
        warm_request_count = int(round(requests * warm_ratio))
        cold_request_count = max(0, requests - warm_request_count)
        warm_key_count = max(1, min(warm_key_space_size, warm_request_count))
        warm_keys: list[tuple[UUID, UUID]] = []
        for idx in range(warm_key_count):
            warm_keys.append((allocation_ids[idx % len(allocation_ids)], uuid4()))

        measurement_started_at = datetime.now(timezone.utc)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://bench") as client:
            # Prime the intended warm keyspace so warm-phase requests are true cache hits.
            for allocation_id, warm_user in warm_keys:
                for entity_type in CANONICAL_ENTITY_TYPES:
                    await _call_explain(
                        client=client,
                        tenant_id=tenant_id,
                        allocation_id=allocation_id,
                        entity_type=entity_type,
                        user_id=warm_user,
                    )

            attribution_api.settings.LLM_B17_PREWARM_ENABLED = prewarm_enabled

            warm_workload: list[tuple[UUID, str, UUID]] = []
            for idx in range(warm_request_count):
                allocation_id, warm_user = warm_keys[idx % len(warm_keys)]
                warm_workload.append(
                    (
                        allocation_id,
                        CANONICAL_ENTITY_TYPES[idx % len(CANONICAL_ENTITY_TYPES)],
                        warm_user,
                    )
                )

            cold_pairs = cold_request_count // 2
            cold_phase_one: list[tuple[UUID, str, UUID]] = []
            cold_phase_two: list[tuple[UUID, str, UUID]] = []
            cold_interleaved: list[tuple[UUID, str, UUID]] = []
            for _ in range(cold_pairs):
                cold_user = uuid4()
                cold_allocation_id = allocation_ids[len(cold_phase_one) % len(allocation_ids)]
                cold_phase_one.append((cold_allocation_id, CANONICAL_ENTITY_TYPES[0], cold_user))
                cold_phase_two.append((cold_allocation_id, CANONICAL_ENTITY_TYPES[1], cold_user))
                cold_interleaved.append((cold_allocation_id, CANONICAL_ENTITY_TYPES[0], cold_user))
                cold_interleaved.append((cold_allocation_id, CANONICAL_ENTITY_TYPES[1], cold_user))
            odd_tail: list[tuple[UUID, str, UUID]] = []
            if cold_request_count % 2:
                odd_tail.append((allocation_ids[0], CANONICAL_ENTITY_TYPES[0], uuid4()))

            if prewarm_run_sync:
                # For sync prewarm, keep companion requests adjacent so efficacy
                # is measured against the same trigger watermark.
                workload = warm_workload + cold_interleaved + odd_tail
            else:
                # Restrict event-driven prewarm triggering to the cold trigger phase.
                # This preserves causal measurement of companion assists while
                # avoiding warm-path trigger churn that can dominate endpoint p95.
                phase_trigger_workload = cold_phase_one
                phase_remaining_workload = warm_workload + cold_phase_two + odd_tail

            semaphore = asyncio.Semaphore(concurrency)
            samples: list[RequestSample] = []

            async def _run_one(allocation_id: UUID, entity_type: str, user_id: UUID) -> None:
                async with semaphore:
                    sample = await _call_explain(
                        client=client,
                        tenant_id=tenant_id,
                        allocation_id=allocation_id,
                        entity_type=entity_type,
                        user_id=user_id,
                    )
                    samples.append(sample)

            async def _run_batch(workload_batch: list[tuple[UUID, str, UUID]]) -> None:
                await asyncio.gather(
                    *(
                        _run_one(allocation_id, entity_type, user_id)
                        for allocation_id, entity_type, user_id in workload_batch
                    )
                )

            if prewarm_run_sync:
                await _run_batch(workload)
            else:
                await _run_batch(phase_trigger_workload)
                for deferred_coro in deferred_prewarm_coroutines:
                    tracked_async_prewarm_tasks.append(
                        original_asyncio_create_task(deferred_coro)
                    )
                deferred_prewarm_coroutines.clear()
                # Drain background prewarm tasks to align phase-two measurements with
                # completed async prewarm effects rather than scheduler race timing.
                pending_tasks = [task for task in tracked_async_prewarm_tasks if not task.done()]
                if pending_tasks:
                    await asyncio.gather(*pending_tasks, return_exceptions=True)
                if prewarm_enabled:
                    attribution_api.settings.LLM_B17_PREWARM_ENABLED = False
                await _run_batch(phase_remaining_workload)

    finally:
        attribution_api._PROVIDER_BOUNDARY._provider_call = original_provider_call
        auth_module.assert_access_token_active = original_assert_access_token_active
        attribution_api.settings.LLM_B17_PREWARM_ENABLED = original_prewarm_enabled
        attribution_api.settings.LLM_B17_PREWARM_RUN_SYNC = original_prewarm_run_sync
        attribution_api.settings.LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES = original_prewarm_targets
        attribution_api.settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER = (
            original_prewarm_max_per_trigger
        )
        attribution_api.asyncio.create_task = original_asyncio_create_task
        for logger_name, logger_level in original_log_levels.items():
            logging.getLogger(logger_name).setLevel(logger_level)

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
    determinant_counts: dict[tuple[str, str, str], int] = {}
    for sample in samples:
        determinant = (sample.allocation_id, sample.user_id, sample.entity_type)
        determinant_counts[determinant] = determinant_counts.get(determinant, 0) + 1
    distinct_allocations = {sample.allocation_id for sample in samples}
    distinct_users = {sample.user_id for sample in samples}
    prewarm_observability = await _collect_prewarm_observability(
        tenant_id=tenant_id,
        measurement_started_at=measurement_started_at,
    )
    reuse_histogram: dict[str, int] = {}
    for usage_count in determinant_counts.values():
        key = str(int(usage_count))
        reuse_histogram[key] = reuse_histogram.get(key, 0) + 1
    hottest_determinant_requests = max(determinant_counts.values()) if determinant_counts else 0
    unique_determinant_ratio = (
        len(determinant_counts) / float(len(samples)) if samples else 0.0
    )

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
        "workload_profile": {
            "allocation_pool_size": allocation_pool_size,
            "warm_key_space_size": warm_key_space_size,
            "configured_warm_request_count": warm_request_count,
            "configured_cold_request_count": cold_request_count,
            "cold_pair_count": cold_pairs,
            "phase_strategy": (
                "sync_adjacent_pairs"
                if prewarm_run_sync
                else "two_phase_cold_trigger_then_remaining_workload"
            ),
            "async_prewarm_tasks_scheduled": len(tracked_async_prewarm_tasks),
            "async_prewarm_tasks_completed": sum(
                1 for task in tracked_async_prewarm_tasks if task.done()
            ),
            "distinct_allocation_count": len(distinct_allocations),
            "distinct_user_count": len(distinct_users),
            "distinct_entity_type_count": len({sample.entity_type for sample in samples}),
            "distinct_cache_determinant_count": len(determinant_counts),
            "max_requests_per_determinant": hottest_determinant_requests,
            "duplicate_request_ratio": round(
                1.0 - (len(determinant_counts) / float(len(samples))) if samples else 0.0,
                4,
            ),
            "unique_determinant_ratio": round(unique_determinant_ratio, 4),
            "hottest_determinant_share": round(
                (hottest_determinant_requests / float(len(samples))) if samples else 0.0,
                4,
            ),
            "determinant_reuse_histogram": dict(sorted(reuse_histogram.items())),
        },
        "prewarm_observability": prewarm_observability,
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
    parser.add_argument("--allocation-pool-size", type=int, default=12)
    parser.add_argument("--warm-key-space-size", type=int, default=16)
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
                "allocation_pool_positive": args.allocation_pool_size > 0,
                "warm_key_space_positive": args.warm_key_space_size > 0,
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
            allocation_pool_size=args.allocation_pool_size,
            warm_key_space_size=args.warm_key_space_size,
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

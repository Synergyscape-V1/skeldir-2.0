"""
Bayesian worker tasks with explicit bounded-compute contracts.

Phase 5 contract:
- Production defaults are explicit: soft=270s, hard=300s.
- Deterministic fallback is emitted on soft timeout before hard kill.
- A health probe task is provided to prove worker liveness after timeout events.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from app.celery_app import celery_app
from app.core.config import settings
from app.core.secrets import get_database_url

logger = logging.getLogger(__name__)

# Static production contract. Runtime env may lower limits for non-vacuous CI probes.
PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S = 270
PRODUCTION_BAYESIAN_TIME_LIMIT_S = 300

_TASK_SOFT_LIMIT_S = int(settings.BAYESIAN_TASK_SOFT_TIME_LIMIT_S)
_TASK_HARD_LIMIT_S = int(settings.BAYESIAN_TASK_TIME_LIMIT_S)

if _TASK_HARD_LIMIT_S <= _TASK_SOFT_LIMIT_S:
    raise RuntimeError("BAYESIAN_TASK_TIME_LIMIT_S must be greater than BAYESIAN_TASK_SOFT_TIME_LIMIT_S")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_probe_event(event: dict) -> None:
    path = os.getenv("BAYESIAN_PROBE_LOG_PATH")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception:
        logger.warning("bayesian_probe_log_write_failed", extra={"path": path})


def _as_uuid(raw: str | UUID) -> UUID:
    if isinstance(raw, UUID):
        return raw
    return UUID(str(raw))


def _runtime_sync_database_url() -> str:
    raw_url = get_database_url()
    parsed = make_url(raw_url)
    query = dict(parsed.query)
    query.pop("channel_binding", None)
    parsed = parsed.set(query=query)
    driver = parsed.drivername
    if driver.startswith("postgresql+"):
        driver = "postgresql"
    parsed = parsed.set(drivername=driver)
    dsn_parts = [f"{driver}://"]
    if parsed.username:
        dsn_parts.append(parsed.username)
        if parsed.password:
            dsn_parts.append(":")
            dsn_parts.append(parsed.password)
        dsn_parts.append("@")
    dsn_parts.append(parsed.host or "localhost")
    if parsed.port:
        dsn_parts.append(f":{parsed.port}")
    if parsed.database:
        dsn_parts.append(f"/{parsed.database}")
    return "".join(dsn_parts)


def _exercise_cpu(*, seed: int, cycles: int) -> int:
    value = int(seed) & 0xFFFFFFFF
    for idx in range(max(1, int(cycles))):
        value = ((value << 5) - value + ((idx * 17) + 13)) & 0xFFFFFFFF
    return value


def _build_fallback_payload(*, task_id: str, tenant_id: UUID, correlation_id: UUID, elapsed_ms: int) -> dict:
    return {
        "status": "fallback",
        "reason": "bayesian_soft_time_limit_exceeded",
        "task_id": task_id,
        "tenant_id": str(tenant_id),
        "correlation_id": str(correlation_id),
        "elapsed_ms": elapsed_ms,
        "fallback_model": "deterministic_last_touch",
        "fallback_lookback_days": 30,
        "fallback_triggered": True,
    }


def _emit_fallback_event(*, task_id: str, tenant_id: UUID, correlation_id: UUID, elapsed_ms: int) -> dict:
    fallback_payload = _build_fallback_payload(
        task_id=task_id,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        elapsed_ms=elapsed_ms,
    )
    logger.warning(
        "bayesian_soft_timeout_fallback",
        extra={
            "event_type": "bayesian.compute",
            "tenant_id": str(tenant_id),
            "correlation_id": str(correlation_id),
            "task_id": task_id,
            "fallback_model": "deterministic_last_touch",
        },
    )
    _append_probe_event(
        {
            "event": "bayesian_soft_timeout_fallback",
            "timestamp": _utc_now(),
            **fallback_payload,
        }
    )
    return fallback_payload


@celery_app.task(
    bind=True,
    name="app.tasks.bayesian.run_mcmc_inference",
    routing_key="bayesian.task",
    soft_time_limit=_TASK_SOFT_LIMIT_S,
    time_limit=_TASK_HARD_LIMIT_S,
    acks_late=True,
    max_retries=0,
)
def run_mcmc_inference(
    self,
    *,
    tenant_id: str,
    correlation_id: str,
    run_seconds: int = 900,
    continue_after_soft_timeout: bool = False,
) -> dict:
    """
    Simulate a long Bayesian/MCMC workload with deterministic timeout fallback behavior.
    """
    tenant = _as_uuid(tenant_id)
    correlation = _as_uuid(correlation_id)
    task_id = str(self.request.id)
    started_at = time.monotonic()

    logger.info(
        "bayesian_run_started",
        extra={
            "event_type": "bayesian.compute",
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "task_id": task_id,
            "run_seconds": int(run_seconds),
            "soft_time_limit_s": _TASK_SOFT_LIMIT_S,
            "time_limit_s": _TASK_HARD_LIMIT_S,
        },
    )
    _append_probe_event(
        {
            "event": "bayesian_run_started",
            "timestamp": _utc_now(),
            "task_id": task_id,
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "soft_time_limit_s": _TASK_SOFT_LIMIT_S,
            "time_limit_s": _TASK_HARD_LIMIT_S,
        }
    )

    try:
        deadline = time.monotonic() + max(1, int(run_seconds))
        soft_deadline = started_at + float(_TASK_SOFT_LIMIT_S)
        while time.monotonic() < deadline:
            if time.monotonic() >= soft_deadline:
                # Deterministic fallback guardrail in case soft-timeout signaling is delayed.
                elapsed_ms = int((time.monotonic() - started_at) * 1000)
                fallback_payload = _emit_fallback_event(
                    task_id=task_id,
                    tenant_id=tenant,
                    correlation_id=correlation,
                    elapsed_ms=elapsed_ms,
                )
                if continue_after_soft_timeout:
                    # Keep consuming CPU slot until hard limit kills this worker process.
                    while True:
                        time.sleep(0.2)
                return fallback_payload
            time.sleep(0.2)
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        return {
            "status": "completed",
            "task_id": task_id,
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "elapsed_ms": elapsed_ms,
            "fallback_triggered": False,
        }
    except SoftTimeLimitExceeded:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        fallback_payload = _emit_fallback_event(
            task_id=task_id,
            tenant_id=tenant,
            correlation_id=correlation,
            elapsed_ms=elapsed_ms,
        )
        if continue_after_soft_timeout:
            # Keep consuming CPU slot until hard limit kills this worker process.
            while True:
                time.sleep(0.2)
        return fallback_payload


@celery_app.task(
    bind=True,
    name="app.tasks.bayesian.execute_fit_intent",
    routing_key="bayesian.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=True,
    max_retries=0,
)
def execute_fit_intent(self, *, fit_id: str) -> dict:
    """P3 worker stub: fit_id-only, duplicate-delivery-safe, no compute."""

    fit_uuid = _as_uuid(fit_id)
    payload = {
        "status": "accepted",
        "task_id": str(self.request.id),
        "fit_id": str(fit_uuid),
        "p3_scope": "planning_claim_dispatch_only",
        "compute_started": False,
    }
    _append_probe_event({"event": "bayesian_fit_intent_accepted", **payload})
    return payload


@celery_app.task(
    bind=True,
    name="app.tasks.bayesian.run_resource_contention",
    routing_key="bayesian.task",
    soft_time_limit=120,
    time_limit=150,
    acks_late=True,
    max_retries=0,
)
def run_resource_contention(
    self,
    *,
    tenant_id: str,
    correlation_id: str,
    run_seconds: int = 8,
    cpu_cycles_per_iteration: int = 40000,
    db_round_trips_per_iteration: int = 4,
) -> dict:
    """
    Consume CPU and Postgres throughput to emulate Bayesian contention physics.
    """
    tenant = _as_uuid(tenant_id)
    correlation = _as_uuid(correlation_id)
    task_id = str(self.request.id)
    duration_s = max(1, int(run_seconds))
    cpu_cycles = max(1000, int(cpu_cycles_per_iteration))
    db_round_trips = max(1, int(db_round_trips_per_iteration))

    logger.info(
        "bayesian_resource_contention_started",
        extra={
            "event_type": "bayesian.compute",
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "task_id": task_id,
            "run_seconds": duration_s,
            "cpu_cycles_per_iteration": cpu_cycles,
            "db_round_trips_per_iteration": db_round_trips,
        },
    )
    _append_probe_event(
        {
            "event": "bayesian_resource_contention_started",
            "timestamp": _utc_now(),
            "task_id": task_id,
            "tenant_id": str(tenant),
            "correlation_id": str(correlation),
            "run_seconds": duration_s,
            "cpu_cycles_per_iteration": cpu_cycles,
            "db_round_trips_per_iteration": db_round_trips,
        }
    )

    started_at = time.monotonic()
    iterations = 0
    db_queries = 0
    cpu_accumulator = 0
    runtime_sync_url = _runtime_sync_database_url()
    db_engine = create_engine(
        runtime_sync_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        with db_engine.begin() as conn:
            while (time.monotonic() - started_at) < duration_s:
                cpu_accumulator = _exercise_cpu(seed=cpu_accumulator, cycles=cpu_cycles)
                for _ in range(db_round_trips):
                    conn.execute(
                        text(
                            """
                            SELECT COALESCE(SUM(revenue_cents), 0) AS tenant_revenue_cents
                            FROM attribution_events
                            WHERE tenant_id = :tenant_id
                            """
                        ),
                        {"tenant_id": str(tenant)},
                    ).scalar_one()
                    db_queries += 1
                iterations += 1
    finally:
        db_engine.dispose()

    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    payload = {
        "status": "completed",
        "task_id": task_id,
        "tenant_id": str(tenant),
        "correlation_id": str(correlation),
        "elapsed_ms": elapsed_ms,
        "iterations": iterations,
        "db_queries": db_queries,
        "cpu_accumulator": cpu_accumulator,
    }
    _append_probe_event(
        {
            "event": "bayesian_resource_contention_completed",
            "timestamp": _utc_now(),
            **payload,
        }
    )
    return payload


@celery_app.task(
    bind=True,
    name="app.tasks.bayesian.health_probe",
    routing_key="bayesian.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=False,
    max_retries=0,
)
def health_probe(self, *, tenant_id: str, correlation_id: str) -> dict:
    tenant = _as_uuid(tenant_id)
    correlation = _as_uuid(correlation_id)
    payload = {
        "status": "ok",
        "task_id": str(self.request.id),
        "tenant_id": str(tenant),
        "correlation_id": str(correlation),
        "timestamp_utc": _utc_now(),
    }
    _append_probe_event({"event": "bayesian_health_probe_ok", **payload})
    return payload

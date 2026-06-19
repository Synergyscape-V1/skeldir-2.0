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
from sqlalchemy import text

from app.bayesian.db_engine import (
    create_bayesian_worker_engine,
    runtime_sync_database_url,
)
from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    BayesianDispatchClaim,
    BayesianDispatchLease,
    BayesianWorkerClaimAuthority,
    claim_fit_dispatch_sync,
    mark_dispatch_running_sync,
)
from app.bayesian.fit_execution import execute_fit_intent_sync
from app.bayesian.runtime_state import mark_fit_timeout_sync
from app.bayesian.tenant_context import bind_transaction_local_tenant
from app.bayesian.worker_boot_probe import (
    assert_bayesian_worker_boot_topology_proven,
    current_bayesian_worker_claim_authority,
    ensure_bayesian_worker_boot_probe_signal_registered,
)
from app.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

# Static production contract. Runtime env may lower limits for non-vacuous CI probes.
PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S = 270
PRODUCTION_BAYESIAN_TIME_LIMIT_S = 300
FEATURE_AUTHORITY_BUILD_TASK_NAME = "app.tasks.bayesian.build_feature_authority"
FEATURE_AUTHORITY_DISPATCH_TASK_NAME = (
    "app.tasks.bayesian.dispatch_feature_authority_build"
)
FEATURE_AUTHORITY_DISPATCH_RETRY_BACKOFF_S = 30
FEATURE_AUTHORITY_MAX_DISPATCH_ATTEMPTS = 5

_TASK_SOFT_LIMIT_S = int(settings.BAYESIAN_TASK_SOFT_TIME_LIMIT_S)
_TASK_HARD_LIMIT_S = int(settings.BAYESIAN_TASK_TIME_LIMIT_S)

if _TASK_HARD_LIMIT_S <= _TASK_SOFT_LIMIT_S:
    raise RuntimeError(
        "BAYESIAN_TASK_TIME_LIMIT_S must be greater than BAYESIAN_TASK_SOFT_TIME_LIMIT_S"
    )


_BAYESIAN_TASK_REGISTRATION_FALSE_VALUES = {"0", "false", "no", "off"}
_BAYESIAN_TASK_REGISTRATION_TRUE_VALUES = {"1", "true", "yes", "on"}
_BAYESIAN_WORKER_ROLE_ENV = "SKELDIR_CELERY_WORKER_ROLE"
_BAYESIAN_WORKER_ROLE_BAYESIAN = "bayesian"
_BAYESIAN_WORKER_ROLE_NON_BAYESIAN = "non_bayesian"
REQUIRED_BAYESIAN_TASK_NAMES = frozenset(
    {
        "app.tasks.bayesian.run_mcmc_inference",
        "app.tasks.bayesian.execute_fit_intent",
        FEATURE_AUTHORITY_DISPATCH_TASK_NAME,
        FEATURE_AUTHORITY_BUILD_TASK_NAME,
        "app.tasks.bayesian.run_resource_contention",
        "app.tasks.bayesian.health_probe",
    }
)


def _explicit_bayesian_task_registration_value() -> bool | None:
    explicit = os.getenv("SKELDIR_CELERY_INCLUDE_BAYESIAN_TASKS")
    if explicit is None:
        return None
    normalized = explicit.strip().lower()
    if normalized in _BAYESIAN_TASK_REGISTRATION_FALSE_VALUES:
        return False
    if normalized in _BAYESIAN_TASK_REGISTRATION_TRUE_VALUES:
        return True
    raise RuntimeError("bayesian_task_registration_flag_invalid")


def _bayesian_tasks_registered_for_process() -> bool:
    """
    Return whether this process registers executable Bayesian task entries.

    Database topology declarations are intentionally not inputs. A process is
    Bayesian-capable only when the worker role or task-registration flag says it
    is allowed to execute Bayesian tasks; the physical DB proof happens later at
    worker-generation boot and cannot be asserted by environment alone.
    """

    explicit = _explicit_bayesian_task_registration_value()
    role = os.getenv(_BAYESIAN_WORKER_ROLE_ENV, "").strip().lower()
    if role == _BAYESIAN_WORKER_ROLE_BAYESIAN:
        if explicit is False:
            raise RuntimeError("bayesian_worker_role_registration_contradiction")
        return True
    if role == _BAYESIAN_WORKER_ROLE_NON_BAYESIAN:
        if explicit is True:
            raise RuntimeError("non_bayesian_worker_role_registration_contradiction")
        return False
    if role:
        raise RuntimeError("bayesian_worker_role_unknown")
    return bool(explicit)


_BAYESIAN_TASKS_REGISTERED = _bayesian_tasks_registered_for_process()

if _BAYESIAN_TASKS_REGISTERED:
    ensure_bayesian_worker_boot_probe_signal_registered()


def _bayesian_task(*task_args, **task_kwargs):
    if _BAYESIAN_TASKS_REGISTERED:
        return celery_app.task(*task_args, **task_kwargs)

    def _return_plain_function(func):
        return func

    return _return_plain_function


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


def _set_tenant_context(conn, tenant_id: UUID) -> None:
    bind_transaction_local_tenant(conn, tenant_id=tenant_id)


def _exercise_cpu(*, seed: int, cycles: int) -> int:
    value = int(seed) & 0xFFFFFFFF
    for idx in range(max(1, int(cycles))):
        value = ((value << 5) - value + ((idx * 17) + 13)) & 0xFFFFFFFF
    return value


def _build_fallback_payload(
    *, task_id: str, tenant_id: UUID, correlation_id: UUID, elapsed_ms: int
) -> dict:
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


def _persist_fit_timeout_if_requested(
    *,
    tenant_id: UUID,
    fit_id: UUID | None,
    runtime_seconds: int,
    dispatch_claim: BayesianDispatchClaim | None = None,
    worker_authority: BayesianWorkerClaimAuthority | None = None,
) -> bool:
    if fit_id is None:
        return False
    engine = create_bayesian_worker_engine()
    try:
        with engine.begin() as conn:
            if dispatch_claim is not None and worker_authority is not None:
                lease = claim_fit_dispatch_sync(
                    conn,
                    claim=dispatch_claim,
                    worker_authority=worker_authority,
                    lease_seconds=300,
                )
                if not isinstance(lease, BayesianDispatchLease):
                    return False
                mark_dispatch_running_sync(conn, lease=lease)
            return mark_fit_timeout_sync(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                runtime_seconds=runtime_seconds,
            )
    finally:
        engine.dispose()


def _emit_fallback_event(
    *,
    task_id: str,
    tenant_id: UUID,
    correlation_id: UUID,
    elapsed_ms: int,
    fit_id: UUID | None = None,
    dispatch_claim: BayesianDispatchClaim | None = None,
    worker_authority: BayesianWorkerClaimAuthority | None = None,
) -> dict:
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
    fallback_payload["durable_timeout_written"] = _persist_fit_timeout_if_requested(
        tenant_id=tenant_id,
        fit_id=fit_id,
        runtime_seconds=max(0, elapsed_ms // 1000),
        dispatch_claim=dispatch_claim,
        worker_authority=worker_authority,
    )
    return fallback_payload


@_bayesian_task(
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
    fit_id: str | None = None,
    run_seconds: int = 900,
    continue_after_soft_timeout: bool = False,
) -> dict:
    """
    Simulate a long Bayesian/MCMC workload with deterministic timeout fallback behavior.
    """
    assert_bayesian_worker_boot_topology_proven()
    tenant = _as_uuid(tenant_id)
    correlation = _as_uuid(correlation_id)
    fit_uuid = _as_uuid(fit_id) if fit_id else None
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
                    fit_id=fit_uuid,
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
            fit_id=fit_uuid,
        )
        if continue_after_soft_timeout:
            # Keep consuming CPU slot until hard limit kills this worker process.
            while True:
                time.sleep(0.2)
        return fallback_payload


@_bayesian_task(
    bind=True,
    name="app.tasks.bayesian.execute_fit_intent",
    routing_key="bayesian.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=True,
    max_retries=0,
)
def execute_fit_intent(
    self,
    *,
    dispatch_id: str,
    fit_id: str,
    task_name: str,
    attempt_id: str,
    payload_hash: str,
    recovery_generation: str = "0",
) -> dict:
    """Execute one Bayesian fit only after DB validates dispatch authority."""

    assert_bayesian_worker_boot_topology_proven()
    if task_name != BAYESIAN_FIT_EXECUTION_TASK:
        raise RuntimeError("bayesian_dispatch_task_name_mismatch")
    claim = BayesianDispatchClaim(
        dispatch_id=_as_uuid(dispatch_id),
        fit_id=_as_uuid(fit_id),
        task_name=task_name,
        attempt_id=_as_uuid(attempt_id),
        payload_hash=payload_hash,
        recovery_generation=int(recovery_generation),
    )
    worker_authority = current_bayesian_worker_claim_authority()
    task_id = str(self.request.id)
    engine = create_bayesian_worker_engine()
    try:
        payload = execute_fit_intent_sync(
            engine=engine,
            fit_id=claim.fit_id,
            task_id=task_id,
            dispatch_claim=claim,
            worker_authority=worker_authority,
        )
    finally:
        engine.dispose()
    payload.setdefault(
        "compute_started", payload.get("status") == "sampled_unvalidated"
    )
    _append_probe_event({"event": "bayesian_fit_intent_executed", **payload})
    return payload


@_bayesian_task(
    bind=True,
    name=FEATURE_AUTHORITY_DISPATCH_TASK_NAME,
    routing_key="bayesian.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=True,
    max_retries=0,
)
def dispatch_feature_authority_build(
    self, *, tenant_id: str, dispatch_key: str
) -> dict:
    """Causally dispatch one committed feature-authority build outbox row."""

    assert_bayesian_worker_boot_topology_proven()
    tenant = _as_uuid(tenant_id)
    task_id = str(self.request.id)
    engine = create_bayesian_worker_engine()
    row = None
    try:
        with engine.begin() as conn:
            _set_tenant_context(conn, tenant)
            row = (
                conn.execute(
                    text(
                        """
                        WITH due AS (
                            SELECT tenant_id, id
                            FROM public.b24_feature_authority_build_outbox
                            WHERE tenant_id = :tenant_id
                              AND dispatch_key = :dispatch_key
                              AND status IN ('pending', 'failed_retryable', 'stale_recovered')
                              AND next_attempt_at <= now()
                            ORDER BY next_attempt_at ASC, id ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                        )
                        UPDATE public.b24_feature_authority_build_outbox outbox
                        SET status = 'dispatching',
                            dispatching_started_at = now(),
                            last_attempt_at = now(),
                            attempt_count = attempt_count + 1,
                            updated_at = now()
                        FROM due
                        WHERE outbox.tenant_id = due.tenant_id
                          AND outbox.id = due.id
                        RETURNING
                            outbox.id,
                            outbox.tenant_id,
                            outbox.model_type,
                            outbox.model_version,
                            outbox.source_window_start,
                            outbox.source_window_end,
                            outbox.source_snapshot_hash,
                            outbox.attempt_count,
                            outbox.max_attempts
                        """
                    ),
                    {"tenant_id": str(tenant), "dispatch_key": dispatch_key},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return {
                "status": "not_dispatchable",
                "task_id": task_id,
                "tenant_id": str(tenant),
                "dispatch_key": dispatch_key,
            }
        try:
            celery_app.send_task(
                FEATURE_AUTHORITY_BUILD_TASK_NAME,
                kwargs={
                    "tenant_id": str(row["tenant_id"]),
                    "model_type": str(row["model_type"]),
                    "model_version": str(row["model_version"]),
                    "source_window_start": row["source_window_start"].isoformat(),
                    "source_window_end": row["source_window_end"].isoformat(),
                    "source_snapshot_hash": str(row["source_snapshot_hash"]),
                },
                queue="bayesian",
                routing_key="bayesian.task",
            )
        except Exception as exc:
            dead_letter = int(row["attempt_count"]) >= int(row["max_attempts"])
            with engine.begin() as conn:
                _set_tenant_context(conn, tenant)
                conn.execute(
                    text(
                        """
                        UPDATE public.b24_feature_authority_build_outbox
                        SET status = :status,
                            next_attempt_at = CASE
                                WHEN :dead_letter THEN next_attempt_at
                                ELSE now() + (:retry_delay_seconds * interval '1 second')
                            END,
                            dead_lettered_at = CASE
                                WHEN :dead_letter THEN now()
                                ELSE dead_lettered_at
                            END,
                            last_error = :error,
                            updated_at = now()
                        WHERE tenant_id = :tenant_id
                          AND id = :outbox_id
                        """
                    ),
                    {
                        "tenant_id": str(tenant),
                        "outbox_id": str(row["id"]),
                        "status": (
                            "dead_lettered" if dead_letter else "failed_retryable"
                        ),
                        "dead_letter": dead_letter,
                        "retry_delay_seconds": FEATURE_AUTHORITY_DISPATCH_RETRY_BACKOFF_S,
                        "error": str(exc)[:2048],
                    },
                )
            return {
                "status": "dispatch_failed",
                "task_id": task_id,
                "tenant_id": str(tenant),
                "dispatch_key": dispatch_key,
            }
        with engine.begin() as conn:
            _set_tenant_context(conn, tenant)
            conn.execute(
                text(
                    """
                    UPDATE public.b24_feature_authority_build_outbox
                    SET status = 'dispatched',
                        dispatched_at = now(),
                        last_error = NULL,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :outbox_id
                    """
                ),
                {"tenant_id": str(tenant), "outbox_id": str(row["id"])},
            )
        return {
            "status": "dispatched",
            "task_id": task_id,
            "tenant_id": str(tenant),
            "dispatch_key": dispatch_key,
        }
    finally:
        engine.dispose()


@_bayesian_task(
    bind=True,
    name=FEATURE_AUTHORITY_BUILD_TASK_NAME,
    routing_key="bayesian.task",
    soft_time_limit=60,
    time_limit=90,
    acks_late=True,
    max_retries=0,
)
def build_feature_authority(
    self,
    *,
    tenant_id: str,
    model_type: str,
    model_version: str,
    source_window_start: str,
    source_window_end: str,
    source_snapshot_hash: str,
) -> dict:
    """Reactivate the frozen candidate once snapshot-fresh authority exists."""

    assert_bayesian_worker_boot_topology_proven()
    tenant = _as_uuid(tenant_id)
    task_id = str(self.request.id)
    engine = create_bayesian_worker_engine()
    try:
        with engine.begin() as conn:
            _set_tenant_context(conn, tenant)
            authority = (
                conn.execute(
                    text(
                        """
                        SELECT freshness_status, policy_version
                        FROM public.b24_source_window_feature_authority
                        WHERE tenant_id = :tenant_id
                          AND model_type = :model_type
                          AND model_version = :model_version
                          AND source_window_start = :source_window_start
                          AND source_window_end = :source_window_end
                          AND source_snapshot_hash = :source_snapshot_hash
                        """
                    ),
                    {
                        "tenant_id": str(tenant),
                        "model_type": model_type,
                        "model_version": model_version,
                        "source_window_start": source_window_start,
                        "source_window_end": source_window_end,
                        "source_snapshot_hash": source_snapshot_hash,
                    },
                )
                .mappings()
                .one_or_none()
            )
            if authority is None or authority["freshness_status"] != "fresh":
                conn.execute(
                    text(
                        """
                        UPDATE public.b24_feature_authority_build_requests
                        SET status = 'authority_waiting',
                            retry_after_at = now() + interval '60 seconds',
                            updated_at = now()
                        WHERE tenant_id = :tenant_id
                          AND model_type = :model_type
                          AND model_version = :model_version
                          AND source_window_start = :source_window_start
                          AND source_window_end = :source_window_end
                          AND source_snapshot_hash = :source_snapshot_hash
                          AND status IN (
                              'authority_build_requested',
                              'authority_waiting',
                              'authority_retry_ready'
                          )
                        """
                    ),
                    {
                        "tenant_id": str(tenant),
                        "model_type": model_type,
                        "model_version": model_version,
                        "source_window_start": source_window_start,
                        "source_window_end": source_window_end,
                        "source_snapshot_hash": source_snapshot_hash,
                    },
                )
                return {
                    "status": "authority_waiting",
                    "task_id": task_id,
                    "tenant_id": str(tenant),
                    "source_snapshot_hash": source_snapshot_hash,
                }
            conn.execute(
                text(
                    """
                    WITH transitioned AS (
                        UPDATE public.b24_feature_authority_build_requests
                        SET status = 'authority_completed',
                            completed_at = now(),
                            retry_after_at = NULL,
                            terminal_reason = NULL,
                            terminal_at = NULL,
                            updated_at = now()
                        WHERE tenant_id = :tenant_id
                          AND model_type = :model_type
                          AND model_version = :model_version
                          AND source_window_start = :source_window_start
                          AND source_window_end = :source_window_end
                          AND source_snapshot_hash = :source_snapshot_hash
                          AND status IN (
                              'authority_build_requested',
                              'authority_waiting',
                              'authority_retry_ready'
                          )
                        RETURNING
                            tenant_id,
                            model_type,
                            model_version,
                            source_window_start,
                            source_window_end,
                            source_snapshot_hash
                    ),
                    reactivated_waiters AS (
                        UPDATE public.b24_dirty_events dirty
                        SET status = 'authority_retry_ready',
                            authority_reactivated_at = now(),
                            updated_at = now()
                        FROM transitioned ready
                        WHERE dirty.tenant_id = ready.tenant_id
                          AND dirty.model_type = ready.model_type
                          AND dirty.model_version = ready.model_version
                          AND dirty.source_window_start = ready.source_window_start
                          AND dirty.source_window_end = ready.source_window_end
                          AND dirty.source_snapshot_hash = ready.source_snapshot_hash
                          AND dirty.status = 'authority_waiting'
                    )
                    INSERT INTO public.b24_dirty_events (
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        source_snapshot_hash,
                        dirty_reason,
                        source_family,
                        source_event_id,
                        status,
                        observed_at,
                        created_at,
                        updated_at
                    )
                    SELECT
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        source_snapshot_hash,
                        'feature_authority_fresh',
                        'b24_feature_authority',
                        source_snapshot_hash,
                        'pending',
                        now(),
                        now(),
                        now()
                    FROM transitioned
                    """
                ),
                {
                    "tenant_id": str(tenant),
                    "model_type": model_type,
                    "model_version": model_version,
                    "source_window_start": source_window_start,
                    "source_window_end": source_window_end,
                    "source_snapshot_hash": source_snapshot_hash,
                },
            )
        return {
            "status": "authority_completed",
            "task_id": task_id,
            "tenant_id": str(tenant),
            "source_snapshot_hash": source_snapshot_hash,
        }
    finally:
        engine.dispose()


@_bayesian_task(
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
    assert_bayesian_worker_boot_topology_proven()
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
    runtime_sync_url = runtime_sync_database_url()
    db_engine = create_bayesian_worker_engine(runtime_sync_url)
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


@_bayesian_task(
    bind=True,
    name="app.tasks.bayesian.health_probe",
    routing_key="bayesian.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=False,
    max_retries=0,
)
def health_probe(self, *, tenant_id: str, correlation_id: str) -> dict:
    assert_bayesian_worker_boot_topology_proven()
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


if _BAYESIAN_TASKS_REGISTERED:
    missing_required_tasks = sorted(
        name for name in REQUIRED_BAYESIAN_TASK_NAMES if name not in celery_app.tasks
    )
    if missing_required_tasks:
        raise RuntimeError("bayesian_worker_required_task_registration_incomplete")

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
    DispatchClaimOutcome,
    claim_fit_dispatch_sync,
    create_recovery_wakeups_sync,
    fail_dispatch_recoverable_sync,
    mark_dispatch_running_sync,
)
from app.bayesian.dispatch_outbox import (
    publish_due_recovery_rows_sync,
)
from app.bayesian.fit_execution import execute_fit_intent_sync
from app.bayesian.fit_planner import (
    MAX_WAIT_SECONDS,
    QUIET_PERIOD_SECONDS,
    plan_due_dirty_events,
)
from app.bayesian.runtime_state import mark_fit_timeout_sync
from app.bayesian.tenant_context import bind_transaction_local_tenant
from app.bayesian.worker_boot_probe import (
    assert_bayesian_worker_boot_topology_proven,
    current_bayesian_worker_claim_authority,
    ensure_bayesian_worker_boot_probe_signal_registered,
)
from app.celery_app import celery_app
from app.core.config import settings
from app.bayesian.feature_cardinality import (
    produce_source_window_feature_authority,
)
from app.tasks.context import run_in_worker_loop

logger = logging.getLogger(__name__)

# Static production contract. Runtime env may lower limits for non-vacuous CI probes.
PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S = 270
PRODUCTION_BAYESIAN_TIME_LIMIT_S = 300
FEATURE_AUTHORITY_BUILD_TASK_NAME = "app.tasks.bayesian.build_feature_authority"
FEATURE_AUTHORITY_DISPATCH_TASK_NAME = (
    "app.tasks.bayesian.dispatch_feature_authority_build"
)
RECOVERY_RECONCILER_TASK_NAME = "app.tasks.bayesian.reconcile_fit_recovery_wakeups"
#: The initial publisher for a freshly claimed dispatch. Its absence is what
#: made the recovery reconciler above the only route a fit had to a worker.
FIT_PLANNER_TASK_NAME = "app.tasks.bayesian.plan_due_fit_intents"
RECOVERABLE_FAILURE_ACK_PROBE_TASK_NAME = (
    "app.tasks.bayesian.probe_recoverable_failure_ack"
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
_BAYESIAN_WORKER_ROLE_PUBLISHER = "bayesian_publisher"
_BAYESIAN_WORKER_ROLE_NON_BAYESIAN = "non_bayesian"
REQUIRED_BAYESIAN_TASK_NAMES = frozenset(
    {
        "app.tasks.bayesian.run_mcmc_inference",
        "app.tasks.bayesian.execute_fit_intent",
        RECOVERY_RECONCILER_TASK_NAME,
        FIT_PLANNER_TASK_NAME,
        RECOVERABLE_FAILURE_ACK_PROBE_TASK_NAME,
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
    if role == _BAYESIAN_WORKER_ROLE_PUBLISHER:
        if explicit is True:
            raise RuntimeError("publisher_worker_bayesian_registration_contradiction")
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


def _as_utc_datetime(raw: str | datetime) -> datetime:
    """Broker payloads carry timestamps as text; asyncpg will not coerce them.

    The sync paths in this module bind through psycopg2, which accepts an ISO
    string silently, so the window has always arrived here as text and nothing
    noticed. The producer binds through asyncpg, which does not, and would
    rather raise than guess.
    """

    if isinstance(raw, datetime):
        parsed = raw
    else:
        parsed = datetime.fromisoformat(str(raw))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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


def _worker_database_identity() -> str:
    """The database login this worker process actually holds.

    Read from the worker engine rather than from configuration, so the C8
    transport proof observes bootstrap identity instead of a rendered manifest.
    """

    engine = create_bayesian_worker_engine()
    try:
        with engine.connect() as conn:
            return str(conn.execute(text("SELECT current_user")).scalar_one())
    finally:
        engine.dispose()


def _due_planner_tenants(
    *, lease_owner: str, batch_size: int
) -> tuple[tuple[UUID, int], ...]:
    """Read a bounded tenant worklist through the worker-only DB seam."""

    engine = create_bayesian_worker_engine()
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT tenant_id, wakeup_revision FROM "
                    "public.b24_due_fit_planner_tenants("
                    ":lease_owner, :batch_size)"
                ),
                {
                    "lease_owner": lease_owner,
                    "batch_size": max(1, min(int(batch_size), 100)),
                },
            ).all()
        return tuple((UUID(str(row[0])), int(row[1])) for row in rows)
    finally:
        engine.dispose()


def _complete_planner_wakeup(
    *,
    tenant_id: UUID,
    lease_owner: str,
    wakeup_revision: int,
    succeeded: bool,
) -> str:
    """Dispose of one planning obligation from residual authority.

    The wakeup is never destroyed because a Python call returned without an
    exception. The database re-reads the tenant's remaining unplanned dirty
    state inside this transaction and decides: delete only when nothing is left,
    retain when eligible work remains after a bounded batch, defer when the only
    remaining work is still inside its debounce quiet period. Tenant context is
    bound first because that residual read is tenant truth under FORCE RLS.
    """

    engine = create_bayesian_worker_engine()
    try:
        with engine.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            disposition = conn.execute(
                text(
                    "SELECT public.b24_complete_fit_planner_wakeup("
                    ":tenant_id, :lease_owner, :revision, :succeeded, "
                    ":quiet_period_seconds, :max_wait_seconds)"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "lease_owner": lease_owner,
                    "revision": wakeup_revision,
                    "succeeded": succeeded,
                    "quiet_period_seconds": QUIET_PERIOD_SECONDS,
                    "max_wait_seconds": MAX_WAIT_SECONDS,
                },
            ).scalar_one()
        return str(disposition)
    finally:
        engine.dispose()


@_bayesian_task(
    bind=True,
    name=FIT_PLANNER_TASK_NAME,
    routing_key="bayesian.task",
    soft_time_limit=_TASK_SOFT_LIMIT_S,
    time_limit=_TASK_HARD_LIMIT_S,
    acks_late=True,
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=False,
)
def plan_due_fit_intents(
    self,
    *,
    tenant_batch_size: int = 25,
    candidate_limit: int = 25,
) -> dict[str, object]:
    """Turn naturally dirty source state into fit/outbox work.

    Candidate rows are leased with ``SKIP LOCKED`` and expired planner leases
    are reclaimable, so overlapping Beat deliveries and process restarts are
    safe. The selector is bounded and exposes tenant identifiers only to the
    dedicated worker database login.
    """

    assert_bayesian_worker_boot_topology_proven()
    lease_owner = f"celery:{self.request.id}"
    tenants = _due_planner_tenants(
        lease_owner=lease_owner, batch_size=tenant_batch_size
    )
    planned = 0
    dispatchable = 0
    reused = 0
    dispositions: dict[str, int] = {}
    failed_tenants = 0
    failure_classes: dict[str, int] = {}
    for tenant_id, wakeup_revision in tenants:
        succeeded = False
        try:
            intents = run_in_worker_loop(
                plan_due_dirty_events(
                    tenant_id=tenant_id,
                    planner_owner=lease_owner,
                    limit=max(1, min(int(candidate_limit), 100)),
                )
            )
            planned += len(intents)
            for intent in intents:
                if intent.claim is None:
                    continue
                if intent.claim.claimed_for_dispatch:
                    dispatchable += 1
                elif intent.claim.outcome.value == "reused":
                    reused += 1
            succeeded = True
        except Exception as exc:  # noqa: BLE001 - containment boundary, see below
            # One tenant's failure is not evidence about any other tenant.
            #
            # This batch was leased in a single call, so without this boundary an
            # exception here propagates out of the loop and every tenant queued
            # behind the failing one is never reached and never disposed. Their
            # wake-ups stay leased under an owner that has already gone away,
            # and they are unschedulable until the lease expires -- a tenant
            # whose only mistake was being later in an ordered list. Retrying the
            # task does not rescue them either: the retry leases a fresh batch
            # while the stranded rows remain held by the previous owner.
            #
            # Containment here rather than a wider try because the disposal in
            # ``finally`` must still run for this tenant. Its wake-up is released
            # by the same residual-authority logic that disposes a successful
            # one, so the work is conserved rather than dropped: the database
            # re-reads what remains unplanned and decides, and a failed pass
            # leaves the obligation immediately eligible again instead of
            # destroying it.
            #
            # ``Exception`` and not ``BaseException`` on purpose. A hard worker
            # time limit or a process signal is not a per-tenant fault and must
            # keep propagating.
            failed_tenants += 1
            failure_class = type(exc).__name__
            failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1
            logger.exception(
                "b24_fit_planner_tenant_failed",
                extra={
                    "tenant_id": str(tenant_id),
                    "lease_owner": lease_owner,
                    "failure_class": failure_class,
                },
            )
        finally:
            disposition = _complete_planner_wakeup(
                tenant_id=tenant_id,
                lease_owner=lease_owner,
                wakeup_revision=wakeup_revision,
                succeeded=succeeded,
            )
            dispositions[disposition] = dispositions.get(disposition, 0) + 1
    result = {
        "status": "completed",
        "tenant_count": len(tenants),
        "planned_count": planned,
        "dispatchable_count": dispatchable,
        "reused_count": reused,
        "wakeup_dispositions": dispositions,
        # Contained failures are reported, never hidden. A planner pass that
        # silently absorbed exceptions would trade one invisible defect for
        # another.
        "failed_tenant_count": failed_tenants,
        "failure_classes": failure_classes,
    }
    # C8: transport evidence. A probe emitted from inside the task body is what
    # distinguishes "Beat scheduled it" from "a Bayesian worker actually ran it
    # under the worker database identity". Nothing else in the chain can write
    # this record, so its presence is causal rather than circumstantial.
    _append_probe_event(
        {
            "event": "b24_fit_planner_beat_delivery",
            "task_id": str(self.request.id),
            "task_name": FIT_PLANNER_TASK_NAME,
            "delivery_info": str(getattr(self.request, "delivery_info", None)),
            "database_user": _worker_database_identity(),
            "observed_at": _utc_now(),
            **result,
        }
    )
    return result


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
    payload.setdefault("dispatch_id", str(claim.dispatch_id))
    payload.setdefault("fit_id", str(claim.fit_id))
    payload.setdefault("recovery_generation", int(claim.recovery_generation))
    _append_probe_event({"event": "bayesian_fit_intent_executed", **payload})
    return payload


@_bayesian_task(
    bind=True,
    name=RECOVERABLE_FAILURE_ACK_PROBE_TASK_NAME,
    routing_key="bayesian.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=True,
    max_retries=0,
)
def probe_recoverable_failure_ack(
    self,
    *,
    dispatch_id: str,
    fit_id: str,
    task_name: str,
    attempt_id: str,
    payload_hash: str,
    recovery_generation: str = "0",
    correlation_id: str,
) -> dict:
    """Physically acknowledge a recoverable failure through the Bayesian queue."""

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
        with engine.begin() as conn:
            lease = claim_fit_dispatch_sync(
                conn,
                claim=claim,
                worker_authority=worker_authority,
            )
            if not isinstance(lease, BayesianDispatchLease):
                payload = {
                    "status": str(lease).lower(),
                    "claim_outcome": str(lease),
                    "task_id": task_id,
                    "correlation_id": correlation_id,
                    "dispatch_id": str(claim.dispatch_id),
                    "fit_id": str(claim.fit_id),
                    "compute_started": False,
                    "worker_generation": worker_authority.generation_id,
                    "worker_pid": worker_authority.pid,
                }
                _append_probe_event(
                    {"event": "bayesian_recoverable_failure_ack_probe", **payload}
                )
                return payload
            mark_dispatch_running_sync(conn, lease=lease)
            outcome = fail_dispatch_recoverable_sync(
                conn,
                lease=lease,
                reason="directive_xiv_acknowledged_worker_failure",
            )
    finally:
        engine.dispose()
    payload = {
        "status": (
            "failed_terminal"
            if outcome is DispatchClaimOutcome.TERMINAL_FAILURE
            else "failed_retryable"
        ),
        "claim_outcome": outcome.value,
        "task_id": task_id,
        "correlation_id": correlation_id,
        "dispatch_id": str(claim.dispatch_id),
        "fit_id": str(claim.fit_id),
        "compute_started": False,
        "worker_generation": worker_authority.generation_id,
        "worker_pid": worker_authority.pid,
        "failure_taxonomy": "recoverable_acknowledged_worker_failure",
    }
    _append_probe_event({"event": "bayesian_recoverable_failure_ack_probe", **payload})
    return payload


@_bayesian_task(
    bind=True,
    name=RECOVERY_RECONCILER_TASK_NAME,
    routing_key="bayesian.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=True,
    max_retries=0,
)
def reconcile_fit_recovery_wakeups(
    self,
    *,
    batch_size: int = 25,
    stale_publishing_seconds: int = 300,
) -> dict:
    """Detect recoverable fit dispatches and republish secret-free wake-ups."""

    assert_bayesian_worker_boot_topology_proven()
    task_id = str(self.request.id)
    engine = create_bayesian_worker_engine()
    try:
        with engine.begin() as conn:
            created = create_recovery_wakeups_sync(conn, batch_size=batch_size)
            published_rows = publish_due_recovery_rows_sync(
                conn,
                batch_size=batch_size,
                stale_publishing_seconds=stale_publishing_seconds,
            )
    finally:
        engine.dispose()

    payload = {
        "status": "ok",
        "task_id": task_id,
        "recovery_wakeups_created": int(created),
        "recovery_wakeups_published": sum(
            1 for row in published_rows if row.published_task_id is not None
        ),
        "recovery_dispatch_ids": [str(row.dispatch_id) for row in published_rows],
        "recovery_published_task_ids": [
            str(row.published_task_id)
            for row in published_rows
            if row.published_task_id is not None
        ],
    }
    logger.info(
        "bayesian_recovery_reconciler_completed",
        extra={
            "event_type": "bayesian.recovery",
            "task_id": task_id,
            "recovery_wakeups_created": payload["recovery_wakeups_created"],
            "recovery_wakeups_published": payload["recovery_wakeups_published"],
        },
    )
    _append_probe_event({"event": "bayesian_recovery_reconciler_completed", **payload})
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

    # The step this task is named for but has never performed. Until now it read
    # the authority table, found nothing, and parked the request for another
    # sixty seconds -- so a planner waiting on a feature authority waited
    # forever, and every proof that ever showed a fit wrote that row itself.
    #
    # The producer is snapshot-keyed: it recomputes the source hash and writes
    # only if the snapshot this request was made about is still the snapshot on
    # disk. If the source moved, nothing is written and the read below parks the
    # request exactly as it always did -- which is the correct answer, because
    # the bytes that request described no longer exist.
    produced = run_in_worker_loop(
        produce_source_window_feature_authority(
            tenant_id=tenant,
            model_type=model_type,
            model_version=model_version,
            source_window_start=_as_utc_datetime(source_window_start),
            source_window_end=_as_utc_datetime(source_window_end),
            expected_source_snapshot_hash=source_snapshot_hash,
        )
    )
    _append_probe_event(
        {
            "event": "b24_feature_authority_produced",
            "task_id": task_id,
            "tenant_id": str(tenant),
            "source_snapshot_hash": source_snapshot_hash,
            "produced": produced is not None,
            "channel_count": getattr(produced, "channel_count", None),
            "currency_count": getattr(produced, "currency_count", None),
            "provider_count": getattr(produced, "provider_count", None),
            "campaign_or_feature_count": getattr(
                produced, "campaign_or_feature_count", None
            ),
            "observed_at": _utc_now(),
        }
    )

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
                # Retry a hash that does not match *yet*; terminate one that
                # names a source state which is gone.
                #
                # The producer writes nothing when the snapshot it observes is
                # not the snapshot the request named -- measuring a state it
                # cannot see would be the hybrid-authority defect. But parking
                # unconditionally, as this did, cannot distinguish a writer
                # mid-flight from a snapshot that has been superseded. The first
                # resolves in seconds. The second never resolves at all, and was
                # re-queued every sixty seconds for the life of the deployment
                # against a question with a permanent answer.
                #
                # The bounded-retry columns for exactly this were already on the
                # table and never consulted. Past max_retries the request
                # terminates as superseded, and the dirty evidence waiting on it
                # is released to the state B2.4 already had a name for -- rather
                # than waiting on a request that will never complete.
                conn.execute(
                    text(
                        """
                        UPDATE public.b24_feature_authority_build_requests
                        SET retry_count = retry_count + 1,
                            status = CASE
                                WHEN retry_count + 1 >= max_retries
                                    THEN 'authority_superseded'
                                ELSE 'authority_waiting'
                            END,
                            retry_after_at = CASE
                                WHEN retry_count + 1 >= max_retries THEN NULL
                                ELSE now() + interval '60 seconds'
                            END,
                            terminal_reason = CASE
                                WHEN retry_count + 1 >= max_retries
                                    THEN 'source_snapshot_superseded'
                                ELSE terminal_reason
                            END,
                            terminal_at = CASE
                                WHEN retry_count + 1 >= max_retries THEN now()
                                ELSE terminal_at
                            END,
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
                superseded = conn.execute(
                    text(
                        """
                        UPDATE public.b24_dirty_events dirty
                        SET status = 'authority_retry_superseded',
                            superseded_at = now(),
                            updated_at = now()
                        FROM public.b24_feature_authority_build_requests request
                        WHERE dirty.tenant_id = request.tenant_id
                          AND dirty.model_type = request.model_type
                          AND dirty.model_version = request.model_version
                          AND dirty.source_window_start = request.source_window_start
                          AND dirty.source_window_end = request.source_window_end
                          AND dirty.source_snapshot_hash = request.source_snapshot_hash
                          AND dirty.status = 'authority_waiting'
                          AND request.status = 'authority_superseded'
                          AND request.tenant_id = :tenant_id
                          AND request.source_snapshot_hash = :source_snapshot_hash
                        """
                    ),
                    {
                        "tenant_id": str(tenant),
                        "source_snapshot_hash": source_snapshot_hash,
                    },
                ).rowcount
                terminal = conn.execute(
                    text(
                        "SELECT status FROM"
                        " public.b24_feature_authority_build_requests"
                        " WHERE tenant_id = :tenant_id"
                        "   AND source_snapshot_hash = :source_snapshot_hash"
                        " ORDER BY updated_at DESC LIMIT 1"
                    ),
                    {
                        "tenant_id": str(tenant),
                        "source_snapshot_hash": source_snapshot_hash,
                    },
                ).scalar_one_or_none()
                return {
                    "status": str(terminal or "authority_waiting"),
                    "task_id": task_id,
                    "tenant_id": str(tenant),
                    "source_snapshot_hash": source_snapshot_hash,
                    "superseded_dirty_events": int(superseded or 0),
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

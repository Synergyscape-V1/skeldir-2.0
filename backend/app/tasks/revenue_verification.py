"""B2.3 revenue verification task registrations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID
from uuid import uuid4

from sqlalchemy import text

from app.celery_app import celery_app
from app.core.queues import QUEUE_B23_MATCH_ENGINE
from app.db.session import engine, get_b23_session
from app.observability.context import set_request_correlation_id
from app.revenue_verification.batch_engine import execute_b23_batch_match_engine
from app.revenue_verification.state_transitions import (
    B23_P3_TRANSITION_BATCH_SIZE,
    B23_P3_TRANSITION_SWEEP_CADENCE,
    transition_stale_pending_to_unmatched,
    transition_stale_provisional_to_confirmed,
)
from app.tasks.context import run_in_worker_loop

logger = logging.getLogger(__name__)


async def _derive_p2_scope_for_window(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    broker_task_id: str | None = None,
) -> Dict[str, Any]:
    """Derive the governed P2 scope after natural B2.3 dispatch (read-only).

    Corrective II dispatch-bound authority: the message tenant/window are
    lower-authority claims. The worker re-resolves authoritative tenant,
    window, and ingress provenance from the durable
    ``b23_match_task_dispatches`` row keyed by the broker-assigned task
    identity (``self.request.id``), compares the message claims against
    that durable authority, and derives scope from the authoritative
    values only. Any absence or mismatch refuses fail-closed (exception);
    callers must propagate to task FAILURE/DLQ, never swallow to
    ``p2_scope: None`` success. The derivation runs in one REPEATABLE READ
    snapshot with exact identity conservation and RLS completeness
    inspection. B2.3 verdict truth is never written here.
    """
    from app.finance_reconciliation import (  # noqa: PLC0415
        candidate_conduction as _p2_conduction,
    )
    from app.finance_reconciliation import (  # noqa: PLC0415
        dispatch_authority as _p2_dispatch,
    )
    from app.finance_reconciliation.tenant_authority import (  # noqa: PLC0415
        open_governed_b23_snapshot_session,
    )

    async with open_governed_b23_snapshot_session(tenant_id) as session:
        authority = await _p2_dispatch.resolve_dispatch_authority(
            session,
            broker_task_id=broker_task_id,
            message_tenant_id=tenant_id,
            message_window_start=window_start,
            message_window_end=window_end,
        )
        scope = await _p2_conduction.derive_governed_scope(
            session,
            tenant_id=authority.tenant_id,
            window_start=authority.window_start,
            window_end=authority.window_end,
        )
    summary = _p2_conduction.describe_scope_summary(scope)
    summary["dispatch_id"] = str(authority.dispatch_id)
    summary["broker_task_id"] = str(authority.broker_task_id)
    summary["webhook_ingress_identity_id"] = str(authority.webhook_ingress_identity_id)
    summary["dispatch_bound"] = True
    return summary


async def _fetch_b23_transition_tenant_ids() -> list[str]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id FROM public.tenants ORDER BY id"))
        return [str(row[0]) for row in result.fetchall()]


async def _run_pending_to_unmatched_for_tenant(
    *, tenant_id: str, correlation_id: str
) -> Dict[str, int | str]:
    tenant_uuid = UUID(tenant_id)
    async with get_b23_session(tenant_uuid) as session:
        result = await transition_stale_pending_to_unmatched(
            session,
            tenant_id=tenant_uuid,
            now_utc=datetime.now(timezone.utc),
            batch_size=B23_P3_TRANSITION_BATCH_SIZE,
        )
    return {
        "tenant_id": tenant_id,
        "transitioned_count": result.transitioned_count,
        "cadence_seconds": result.cadence_seconds,
        "correlation_id": correlation_id,
    }


async def _run_provisional_to_confirmed_for_tenant(
    *, tenant_id: str, correlation_id: str
) -> Dict[str, int | str]:
    tenant_uuid = UUID(tenant_id)
    async with get_b23_session(tenant_uuid) as session:
        result = await transition_stale_provisional_to_confirmed(
            session,
            tenant_id=tenant_uuid,
            now_utc=datetime.now(timezone.utc),
            batch_size=B23_P3_TRANSITION_BATCH_SIZE,
        )
    return {
        "tenant_id": tenant_id,
        "transitioned_count": result.transitioned_count,
        "cadence_seconds": result.cadence_seconds,
        "correlation_id": correlation_id,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.revenue_verification.transition_stale_pending_to_unmatched",
    routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
    max_retries=3,
    default_retry_delay=60,
)
def transition_stale_pending_to_unmatched_task(
    self, tenant_id: str, correlation_id: str | None = None
) -> Dict[str, int | str]:
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    return run_in_worker_loop(
        _run_pending_to_unmatched_for_tenant(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
    )


@celery_app.task(
    bind=True,
    name="app.tasks.revenue_verification.transition_stale_provisional_to_confirmed",
    routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
    max_retries=3,
    default_retry_delay=60,
)
def transition_stale_provisional_to_confirmed_task(
    self, tenant_id: str, correlation_id: str | None = None
) -> Dict[str, int | str]:
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    return run_in_worker_loop(
        _run_provisional_to_confirmed_for_tenant(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
    )


@celery_app.task(
    bind=True,
    name="app.tasks.revenue_verification.transition_stale_pending_to_unmatched_all_tenants",
    routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
    max_retries=3,
    default_retry_delay=60,
)
def transition_stale_pending_to_unmatched_all_tenants(self) -> Dict[str, int]:
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    tenant_ids = run_in_worker_loop(_fetch_b23_transition_tenant_ids())
    transitioned = 0
    for tenant_id in tenant_ids:
        result = run_in_worker_loop(
            _run_pending_to_unmatched_for_tenant(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
            )
        )
        transitioned += int(result["transitioned_count"])
    return {
        "tenant_count": len(tenant_ids),
        "transitioned_count": transitioned,
        "cadence_seconds": int(B23_P3_TRANSITION_SWEEP_CADENCE.total_seconds()),
    }


@celery_app.task(
    bind=True,
    name="app.tasks.revenue_verification.transition_stale_provisional_to_confirmed_all_tenants",
    routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
    max_retries=3,
    default_retry_delay=60,
)
def transition_stale_provisional_to_confirmed_all_tenants(self) -> Dict[str, int]:
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    tenant_ids = run_in_worker_loop(_fetch_b23_transition_tenant_ids())
    transitioned = 0
    for tenant_id in tenant_ids:
        result = run_in_worker_loop(
            _run_provisional_to_confirmed_for_tenant(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
            )
        )
        transitioned += int(result["transitioned_count"])
    return {
        "tenant_count": len(tenant_ids),
        "transitioned_count": transitioned,
        "cadence_seconds": int(B23_P3_TRANSITION_SWEEP_CADENCE.total_seconds()),
    }


@celery_app.task(
    bind=True,
    name="app.tasks.revenue_verification.execute_b23_batch_match_engine",
    routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
    max_retries=2,
    default_retry_delay=30,
)
def execute_b23_batch_match_engine_task(
    self,
    tenant_id: str,
    window_start_iso: str,
    window_end_iso: str,
    chunk_size: int = 100,
    correlation_id: str | None = None,
) -> Dict[str, int | str | float]:
    correlation_id = correlation_id or str(uuid4())
    set_request_correlation_id(correlation_id)
    window_start = datetime.fromisoformat(window_start_iso)
    window_end = datetime.fromisoformat(window_end_iso)
    broker_task_id: str | None = None
    try:
        broker_task_id = getattr(getattr(self, "request", None), "id", None)
    except Exception:
        broker_task_id = None
    # Corrective III authority-before-B2.3: durable invocation authority is
    # established BEFORE the B2.3 engine runs, from the least forgeable
    # stable handle (broker task identity) via the constrained resolver,
    # without trusting caller-supplied tenant semantics. Missing/mismatched
    # authority refuses here with zero B2.3 consequence (exception -> task
    # FAILURE/DLQ). Only the admitted authoritative tenant/window proceeds.
    from app.db.session import B23AsyncSessionLocal as _B23BareSession  # noqa: PLC0415
    from app.finance_reconciliation import dispatch_authority as _p2_admit  # noqa: PLC0415

    async def _admit() -> Any:
        async with _B23BareSession() as _bare:
            return await _p2_admit.admit_execution_before_b23(
                _bare,
                broker_task_id=str(broker_task_id) if broker_task_id else None,
                message_tenant_id=tenant_id,
                message_window_start=window_start,
                message_window_end=window_end,
            )

    authority = run_in_worker_loop(_admit())

    async def _capture_worker_principal() -> str:
        from app.db.session import B23AsyncSessionLocal as _B23ProbeSession  # noqa: PLC0415

        async with _B23ProbeSession() as _probe:
            row = await _probe.execute(text("SELECT current_user AS u"))
            return str(row.mappings().one()["u"])

    worker_principal = run_in_worker_loop(_capture_worker_principal())
    result = run_in_worker_loop(
        execute_b23_batch_match_engine(
            tenant_id=authority.tenant_id,
            window_start=authority.window_start,
            window_end=authority.window_end,
            chunk_size=chunk_size,
        )
    )
    # Corrective II dispatch-bound P2 conduction (preserved): B2.3 truth is
    # already committed in its own session above, so a later P2 refusal
    # cannot roll it back (idempotent retry preserves verdicts). P2
    # authority failures propagate to task FAILURE/DLQ (observable) -- never
    # a silent ``p2_scope: None`` success.
    p2_scope = run_in_worker_loop(
        _derive_p2_scope_for_window(
            tenant_id=authority.tenant_id,
            window_start=authority.window_start,
            window_end=authority.window_end,
            broker_task_id=str(broker_task_id) if broker_task_id else None,
        )
    )
    logger.info(
        "b26_p2_worker_scope_derived",
        extra={
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "candidate_count": p2_scope.get("candidate_count"),
            "excluded_count": p2_scope.get("excluded_count"),
            "scope_policy_version": p2_scope.get("scope_policy_version"),
            "scope_identity": p2_scope.get("scope_identity"),
            "dispatch_id": p2_scope.get("dispatch_id"),
        },
    )
    # Corrective IV conducted marking: broker publication success must never
    # be mistaken for deterministic B2.3 -> P2 conduction. Only the worker
    # that actually conducted the work (admitted authority + B2.3 verdicts
    # + governed P2 scope, all above) advances the delivery state to
    # conducted, under its least-privilege column-scoped UPDATE. The mark
    # is operational state, never financial truth. A crash before this mark
    # leaves published state for at-least-once redelivery (idempotent by
    # stable task identity); terminal task failure stays observable as
    # published + worker_failed_jobs DLQ FAILURE + result-backend FAILURE.
    run_in_worker_loop(
        _mark_dispatch_conducted(
            tenant_id=authority.tenant_id,
            broker_task_id=str(broker_task_id) if broker_task_id else None,
        )
    )
    return {
        "tenant_id": tenant_id,
        "task_name": self.name,
        "queue": QUEUE_B23_MATCH_ENGINE,
        "db_session_pool": "b23",
        "db_worker_principal": worker_principal,
        "processed_count": result.processed_count,
        "chunk_count": result.chunk_count,
        "chunk_size": result.chunk_size,
        "duration_seconds": result.duration_seconds,
        "correlation_id": correlation_id,
        "p2_scope": p2_scope,
    }


async def _mark_dispatch_conducted(
    *, tenant_id: UUID, broker_task_id: str | None
) -> None:
    """Advance one execution identity to conducted after real conduction.

    Runs on the worker pool under the ADMITTED tenant (governed session
    binds the tenant GUC, so RLS observes the row; worker principal,
    column-scoped UPDATE). The trigger refuses any illegal transition, so
    this advances exactly published rows for this task identity and is a
    no-op otherwise.
    """
    if not broker_task_id:
        return
    from app.db.session import get_b23_session  # noqa: PLC0415

    async with get_b23_session(tenant_id) as session:
        await session.execute(
            text(
                "UPDATE public.b23_match_task_dispatches"
                " SET delivery_state = 'conducted', updated_at = now()"
                " WHERE task_id = :task_id AND delivery_state = 'published'"
            ),
            {"task_id": broker_task_id},
        )
        await session.execute(
            text(
                "UPDATE public.b26_p2_execution_outbox"
                " SET state = 'conducted', updated_at = now()"
                " WHERE dispatch_task_id = :task_id AND state = 'published'"
            ),
            {"task_id": broker_task_id},
        )

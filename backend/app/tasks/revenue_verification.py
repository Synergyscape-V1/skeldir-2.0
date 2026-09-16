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
) -> Dict[str, Any]:
    """Derive the governed P2 scope after natural B2.3 dispatch (read-only).

    B2.6-P2 Corrective I natural conduction: the tenant is the task's
    server-derived tenant (originating from verified webhook dispatch, bound
    here through the governed B23 session), the population is re-read from
    durable state, and every candidate is classified through the single
    scope authority with independent conservation. Read-only observation:
    B2.3 verdict truth is never written here.
    """
    from app.db.session import get_b23_session  # noqa: PLC0415
    from app.finance_reconciliation import (  # noqa: PLC0415
        candidate_conduction as _p2_conduction,
    )

    async with get_b23_session(tenant_id) as session:
        scope = await _p2_conduction.derive_governed_scope(
            session,
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
        )
    return _p2_conduction.describe_scope_summary(scope)


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
    result = run_in_worker_loop(
        execute_b23_batch_match_engine(
            tenant_id=UUID(tenant_id),
            window_start=window_start,
            window_end=window_end,
            chunk_size=chunk_size,
        )
    )
    # Natural P2 conduction after B2.3 dispatch: best-effort observation that
    # never breaks B2.3 truth. Failures log with tenant context and yield a
    # None scope; the mandatory fail-closed edge lives in the canonical sink.
    p2_scope: Dict[str, Any] | None = None
    try:
        p2_scope = run_in_worker_loop(
            _derive_p2_scope_for_window(
                tenant_id=UUID(tenant_id),
                window_start=window_start,
                window_end=window_end,
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
            },
        )
    except Exception:
        logger.exception(
            "b26_p2_worker_scope_derivation_failed",
            extra={
                "tenant_id": tenant_id,
                "correlation_id": correlation_id,
            },
        )
    return {
        "tenant_id": tenant_id,
        "task_name": self.name,
        "queue": QUEUE_B23_MATCH_ENGINE,
        "db_session_pool": "b23",
        "processed_count": result.processed_count,
        "chunk_count": result.chunk_count,
        "chunk_size": result.chunk_size,
        "duration_seconds": result.duration_seconds,
        "correlation_id": correlation_id,
        "p2_scope": p2_scope,
    }

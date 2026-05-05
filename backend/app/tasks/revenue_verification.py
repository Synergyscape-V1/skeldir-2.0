"""B2.3 revenue verification task registrations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict
from uuid import UUID
from uuid import uuid4

from sqlalchemy import text

from app.celery_app import celery_app
from app.db.session import engine, get_session
from app.observability.context import set_request_correlation_id
from app.revenue_verification.state_transitions import (
    B23_P3_TRANSITION_BATCH_SIZE,
    B23_P3_TRANSITION_SWEEP_CADENCE,
    transition_stale_pending_to_unmatched,
    transition_stale_provisional_to_confirmed,
)
from app.tasks.context import run_in_worker_loop


async def _fetch_b23_transition_tenant_ids() -> list[str]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id FROM public.tenants ORDER BY id"))
        return [str(row[0]) for row in result.fetchall()]


async def _run_pending_to_unmatched_for_tenant(
    *, tenant_id: str, correlation_id: str
) -> Dict[str, int | str]:
    tenant_uuid = UUID(tenant_id)
    async with get_session(tenant_uuid) as session:
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
    async with get_session(tenant_uuid) as session:
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
    routing_key="maintenance.task",
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
    routing_key="maintenance.task",
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
    routing_key="maintenance.task",
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
    routing_key="maintenance.task",
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

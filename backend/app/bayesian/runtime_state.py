"""Durable B2.4-P5 timeout and stale-running state transitions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.enums import FallbackReason, FitStatus


async def bind_runtime_tenant_context(session: AsyncSession, *, tenant_id: UUID) -> None:
    """Bind the transaction-local tenant GUC required by RLS-protected fit writes."""

    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def mark_fit_timeout(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    runtime_seconds: int,
    reason: FallbackReason = FallbackReason.TIMEOUT,
) -> bool:
    """Persist timeout fallback from the parent supervisor, not the child."""

    await bind_runtime_tenant_context(session, tenant_id=tenant_id)
    result = await session.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = :status,
                fallback_applied = true,
                fallback_reason = :fallback_reason,
                credible_interval_status = 'not_available',
                runtime_seconds = :runtime_seconds,
                completed_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
              AND status IN ('queued', 'running')
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "status": FitStatus.TIMEOUT.value,
            "fallback_reason": reason.value,
            "runtime_seconds": max(0, int(runtime_seconds)),
        },
    )
    return bool(result.rowcount)


async def sweep_stale_running_fits(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    stale_before: datetime | None = None,
    max_age_seconds: int = 3600,
) -> int:
    """Repair running rows whose sampler parent disappeared before final write."""

    await bind_runtime_tenant_context(session, tenant_id=tenant_id)
    cutoff = stale_before or datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    result = await session.execute(
        text(
            """
            UPDATE public.bayesian_model_fits
            SET status = :status,
                fallback_applied = true,
                fallback_reason = :fallback_reason,
                credible_interval_status = 'not_available',
                completed_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND status = 'running'
              AND sampling_started_at < :cutoff
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "status": FitStatus.WORKER_LOST.value,
            "fallback_reason": FallbackReason.WORKER_FAILURE.value,
            "cutoff": cutoff,
        },
    )
    return int(result.rowcount or 0)

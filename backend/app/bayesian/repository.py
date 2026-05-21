"""Tenant-scoped repository helpers for B2.4 fit authority rows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.exceptions import BayesianFitNotFoundError
from app.bayesian.models import BayesianModelFit
from app.bayesian.source_snapshot import SourceSnapshotResult


class BayesianFitRepository:
    """Read/write authority wrapper for persisted fit rows.

    Callers must use a session with `app.current_tenant_id` already set.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, tenant_id: UUID, fit_id: UUID) -> BayesianModelFit:
        stmt = select(BayesianModelFit).where(
            BayesianModelFit.tenant_id == tenant_id,
            BayesianModelFit.id == fit_id,
        )
        result = await self._session.execute(stmt)
        fit = result.scalar_one_or_none()
        if fit is None:
            raise BayesianFitNotFoundError(f"bayesian fit not found: {fit_id}")
        return fit

    async def latest_for_snapshot(
        self,
        *,
        tenant_id: UUID,
        model_type: str,
        source_snapshot_hash: str,
    ) -> BayesianModelFit | None:
        stmt = (
            select(BayesianModelFit)
            .where(
                BayesianModelFit.tenant_id == tenant_id,
                BayesianModelFit.model_type == model_type,
                BayesianModelFit.source_snapshot_hash == source_snapshot_hash,
            )
            .order_by(BayesianModelFit.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_fallback_from_snapshot(
        self,
        *,
        snapshot: SourceSnapshotResult,
        checked_at: datetime | None = None,
    ) -> UUID:
        """Debounce cold/sparse fallback metadata without compute markers.

        This is P2 metadata persistence only. It does not enqueue work, claim a
        fit, write artifacts, or set sampling/fit timestamps.
        """

        if snapshot.preflight.fallback_reason is None:
            raise ValueError("fallback snapshot requires fallback_reason")
        check_time = checked_at or snapshot.preflight.last_eligibility_check_at
        result = await self._session.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash,
                    status,
                    eligibility_status,
                    data_completeness_status,
                    fallback_applied,
                    fallback_reason,
                    last_eligibility_check_at,
                    sampling_started_at,
                    last_fit_at,
                    completed_at,
                    runtime_seconds,
                    n_samples_actual,
                    r_hat_max,
                    ess_min,
                    divergence_count,
                    artifact_ref,
                    artifact_hash,
                    max_runtime_seconds,
                    max_samples,
                    max_cores
                )
                VALUES (
                    :tenant_id,
                    :model_type,
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    'fallback_only',
                    'fallback_only',
                    'insufficient',
                    true,
                    :fallback_reason,
                    :last_eligibility_check_at,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    0,
                    0,
                    0
                )
                ON CONFLICT (
                    tenant_id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash
                )
                DO UPDATE SET
                    status = 'fallback_only',
                    eligibility_status = 'fallback_only',
                    data_completeness_status = 'insufficient',
                    fallback_applied = true,
                    fallback_reason = EXCLUDED.fallback_reason,
                    last_eligibility_check_at = EXCLUDED.last_eligibility_check_at,
                    sampling_started_at = NULL,
                    last_fit_at = NULL,
                    completed_at = NULL,
                    runtime_seconds = NULL,
                    n_samples_actual = NULL,
                    r_hat_max = NULL,
                    ess_min = NULL,
                    divergence_count = NULL,
                    artifact_ref = NULL,
                    artifact_hash = NULL,
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                "tenant_id": str(snapshot.tenant_id),
                "model_type": snapshot.model_type,
                "model_version": snapshot.model_version,
                "source_window_start": snapshot.source_window_start,
                "source_window_end": snapshot.source_window_end,
                "source_snapshot_hash": snapshot.source_snapshot_hash,
                "fallback_reason": snapshot.preflight.fallback_reason.value,
                "last_eligibility_check_at": check_time,
            },
        )
        return result.scalar_one()

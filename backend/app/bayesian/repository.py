"""Tenant-scoped repository helpers for B2.4 fit authority rows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.exceptions import BayesianFitNotFoundError
from app.bayesian.models import BayesianModelFit


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

"""Tenant-scoped repository helpers for B2.4 artifact authority rows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.exceptions import BayesianArtifactNotFoundError
from app.bayesian.models import BayesianArtifact


class BayesianArtifactRepository:
    """Read authority wrapper for persisted artifact rows.

    Artifact generation, pruning, and storage lifecycle jobs are out of P1 scope.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ref(self, *, tenant_id: UUID, artifact_ref: str) -> BayesianArtifact:
        stmt = select(BayesianArtifact).where(
            BayesianArtifact.tenant_id == tenant_id,
            BayesianArtifact.artifact_ref == artifact_ref,
        )
        result = await self._session.execute(stmt)
        artifact = result.scalar_one_or_none()
        if artifact is None:
            raise BayesianArtifactNotFoundError(f"bayesian artifact not found: {artifact_ref}")
        return artifact

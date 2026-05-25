"""Snapshot-scoped B2.4-P4 source-window feature cardinality authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.enums import FallbackReason
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY_VERSION


B24_FEATURE_AUTHORITY_POLICY_VERSION = B24_RESOURCE_POLICY_VERSION


class FeatureAuthorityStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    MISMATCHED = "mismatched"


@dataclass(frozen=True)
class SourceWindowFeatureAuthority:
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    channel_count: int
    currency_count: int
    provider_count: int
    campaign_or_feature_count: int
    freshness_status: FeatureAuthorityStatus
    policy_version: str
    computed_at: datetime


class FeatureAuthorityUnavailable(RuntimeError):
    """Raised when P4 must fail closed before resource profiling."""

    def __init__(self, reason: FallbackReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


SOURCE_WINDOW_FEATURE_AUTHORITY_LOOKUP_SQL = """
SELECT
    tenant_id,
    model_type,
    model_version,
    source_window_start,
    source_window_end,
    source_snapshot_hash,
    channel_count,
    currency_count,
    provider_count,
    campaign_or_feature_count,
    freshness_status,
    policy_version,
    computed_at
FROM public.b24_source_window_feature_authority
WHERE tenant_id = :tenant_id
  AND model_type = :model_type
  AND model_version = :model_version
  AND source_window_start = :source_window_start
  AND source_window_end = :source_window_end
  AND source_snapshot_hash = :source_snapshot_hash
"""

_RELATED_AUTHORITY_SQL = """
SELECT source_snapshot_hash, freshness_status, computed_at
FROM public.b24_source_window_feature_authority
WHERE tenant_id = :tenant_id
  AND model_type = :model_type
  AND model_version = :model_version
  AND source_window_start = :source_window_start
  AND source_window_end = :source_window_end
ORDER BY computed_at DESC
LIMIT 1
"""

UPSERT_SOURCE_WINDOW_FEATURE_AUTHORITY_SQL = """
INSERT INTO public.b24_source_window_feature_authority (
    tenant_id,
    model_type,
    model_version,
    source_window_start,
    source_window_end,
    source_snapshot_hash,
    channel_count,
    currency_count,
    provider_count,
    campaign_or_feature_count,
    freshness_status,
    policy_version,
    computed_at
)
VALUES (
    :tenant_id,
    :model_type,
    :model_version,
    :source_window_start,
    :source_window_end,
    :source_snapshot_hash,
    :channel_count,
    :currency_count,
    :provider_count,
    :campaign_or_feature_count,
    :freshness_status,
    :policy_version,
    COALESCE(:computed_at, now())
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
    channel_count = EXCLUDED.channel_count,
    currency_count = EXCLUDED.currency_count,
    provider_count = EXCLUDED.provider_count,
    campaign_or_feature_count = EXCLUDED.campaign_or_feature_count,
    freshness_status = EXCLUDED.freshness_status,
    policy_version = EXCLUDED.policy_version,
    computed_at = EXCLUDED.computed_at,
    updated_at = now()
"""


def _authority_from_row(row: dict[str, object]) -> SourceWindowFeatureAuthority:
    return SourceWindowFeatureAuthority(
        tenant_id=row["tenant_id"],
        model_type=str(row["model_type"]),
        model_version=str(row["model_version"]),
        source_window_start=row["source_window_start"],
        source_window_end=row["source_window_end"],
        source_snapshot_hash=str(row["source_snapshot_hash"]),
        channel_count=int(row["channel_count"]),
        currency_count=int(row["currency_count"]),
        provider_count=int(row["provider_count"]),
        campaign_or_feature_count=int(row["campaign_or_feature_count"]),
        freshness_status=FeatureAuthorityStatus(str(row["freshness_status"])),
        policy_version=str(row["policy_version"]),
        computed_at=row["computed_at"],
    )


async def load_source_window_feature_authority(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
) -> SourceWindowFeatureAuthority:
    """Load snapshot-fresh feature counts without raw source discovery."""

    params = {
        "tenant_id": str(tenant_id),
        "model_type": model_type,
        "model_version": model_version,
        "source_window_start": source_window_start,
        "source_window_end": source_window_end,
        "source_snapshot_hash": source_snapshot_hash,
    }
    exact = await session.execute(
        text(SOURCE_WINDOW_FEATURE_AUTHORITY_LOOKUP_SQL), params
    )
    row = exact.mappings().one_or_none()
    if row is None:
        related = await session.execute(text(_RELATED_AUTHORITY_SQL), params)
        related_row = related.mappings().one_or_none()
        if related_row is not None:
            raise FeatureAuthorityUnavailable(
                FallbackReason.CARDINALITY_AUTHORITY_MISMATCH,
                "feature authority snapshot hash does not match P2 source snapshot",
            )
        raise FeatureAuthorityUnavailable(
            FallbackReason.CARDINALITY_AUTHORITY_MISSING,
            "feature authority is missing for P2 source snapshot",
        )

    authority = _authority_from_row(dict(row))
    if authority.freshness_status != FeatureAuthorityStatus.FRESH:
        raise FeatureAuthorityUnavailable(
            FallbackReason.CARDINALITY_AUTHORITY_STALE,
            "feature authority is not marked fresh for P2 source snapshot",
        )
    if authority.policy_version != B24_FEATURE_AUTHORITY_POLICY_VERSION:
        raise FeatureAuthorityUnavailable(
            FallbackReason.CARDINALITY_AUTHORITY_STALE,
            "feature authority policy version is stale",
        )
    return authority


async def upsert_source_window_feature_authority(
    session: AsyncSession,
    *,
    authority: SourceWindowFeatureAuthority,
) -> None:
    """Persist one bounded rollup row outside the P4 planner hot path."""

    await session.execute(
        text(UPSERT_SOURCE_WINDOW_FEATURE_AUTHORITY_SQL),
        {
            "tenant_id": str(authority.tenant_id),
            "model_type": authority.model_type,
            "model_version": authority.model_version,
            "source_window_start": authority.source_window_start,
            "source_window_end": authority.source_window_end,
            "source_snapshot_hash": authority.source_snapshot_hash,
            "channel_count": authority.channel_count,
            "currency_count": authority.currency_count,
            "provider_count": authority.provider_count,
            "campaign_or_feature_count": authority.campaign_or_feature_count,
            "freshness_status": authority.freshness_status.value,
            "policy_version": authority.policy_version,
            "computed_at": authority.computed_at,
        },
    )

"""Deterministic authority read path for canonical attribution explanations (B1.7-P1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.realtime_revenue_cache import DEFAULT_CACHE_KEY

AuthorityEntityType = Literal[
    "attribution_score",
    "channel_performance",
    "reconciliation_discrepancy",
]

DETERMINISTIC_TRUTH_SOURCES: tuple[str, str] = (
    "attribution_allocations",
    "revenue_cache_entries",
)


class AttributionExplanationAuthorityNotFound(Exception):
    """Raised when no deterministic authority row exists for the requested entity."""


class AttributionExplanationAuthorityUnavailable(Exception):
    """Raised when authority prerequisites exist but are not fully readable."""


@dataclass(frozen=True)
class AttributionExplanationAuthorityRecord:
    entity_type: AuthorityEntityType
    entity_id: UUID
    tenant_id: UUID
    metric_key: str
    metric_value_cents: int
    metric_value_usd: float
    channel_code: str
    model_type: str
    model_version: str
    confidence_score: float
    verification_state: Literal["verified", "unverified"]
    revenue_cache_key: str
    revenue_total_cents: int
    revenue_total_usd: float
    revenue_data_as_of: datetime
    last_updated: datetime
    data_freshness_seconds: int
    truth_snapshot_version: str
    truth_snapshot_watermark: int
    truth_snapshot_as_of: datetime


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _payload_to_dict(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            decoded = json.loads(payload)
            return decoded if isinstance(decoded, dict) else {}
        except Exception:
            return {}
    return {}


def _extract_revenue_total_cents(payload: dict[str, Any]) -> int:
    if "revenue_total_cents" in payload:
        try:
            return int(payload["revenue_total_cents"])
        except (TypeError, ValueError) as exc:
            raise AttributionExplanationAuthorityUnavailable(
                "revenue_cache_entries.payload.revenue_total_cents is invalid"
            ) from exc
    if "total_revenue" in payload:
        try:
            return int(round(float(payload["total_revenue"]) * 100))
        except (TypeError, ValueError) as exc:
            raise AttributionExplanationAuthorityUnavailable(
                "revenue_cache_entries.payload.total_revenue is invalid"
            ) from exc
    raise AttributionExplanationAuthorityUnavailable(
        "revenue_cache_entries payload missing revenue_total_cents/total_revenue"
    )


def _metric_key_for_entity_type(entity_type: AuthorityEntityType) -> str:
    if entity_type == "attribution_score":
        return "attribution_score_revenue"
    if entity_type == "channel_performance":
        return "channel_performance_revenue"
    return "reconciliation_discrepancy_revenue_delta"


def _metric_cents_for_entity_type(
    *,
    entity_type: AuthorityEntityType,
    allocated_revenue_cents: int,
    revenue_total_cents: int,
) -> int:
    if entity_type == "reconciliation_discrepancy":
        return revenue_total_cents - allocated_revenue_cents
    return allocated_revenue_cents


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _truth_snapshot_version(seed: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(seed).encode("utf-8")).hexdigest()


def _truth_snapshot_watermark(version: str) -> int:
    bounded = int(version[:16], 16) & ((1 << 63) - 1)
    return max(1, bounded)


async def fetch_attribution_explanation_authority(
    *,
    db_session: AsyncSession,
    tenant_id: UUID,
    entity_type: AuthorityEntityType,
    entity_id: UUID,
    cache_key: str = DEFAULT_CACHE_KEY,
) -> AttributionExplanationAuthorityRecord:
    """Resolve deterministic authority from tenant-scoped attribution + revenue cache tables."""
    allocation_query = text(
        """
        SELECT
            aa.id,
            aa.channel_code,
            aa.allocated_revenue_cents,
            aa.model_type,
            aa.model_version,
            aa.confidence_score,
            aa.verified,
            aa.updated_at
        FROM attribution_allocations aa
        WHERE aa.tenant_id = :tenant_id
          AND aa.id = :entity_id
        """
    )
    allocation_row = (
        (
            await db_session.execute(
                allocation_query,
                {"tenant_id": str(tenant_id), "entity_id": str(entity_id)},
            )
        )
        .mappings()
        .first()
    )

    if allocation_row is None:
        raise AttributionExplanationAuthorityNotFound(
            "Deterministic authority row does not exist for this tenant/entity."
        )

    revenue_cache_query = text(
        """
        SELECT payload, data_as_of
        FROM revenue_cache_entries
        WHERE tenant_id = :tenant_id
          AND cache_key = :cache_key
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    revenue_row = (
        (
            await db_session.execute(
                revenue_cache_query,
                {"tenant_id": str(tenant_id), "cache_key": cache_key},
            )
        )
        .mappings()
        .first()
    )

    if revenue_row is None:
        raise AttributionExplanationAuthorityUnavailable(
            "Deterministic revenue cache authority is unavailable for this tenant."
        )

    payload = _payload_to_dict(revenue_row.get("payload"))
    revenue_total_cents = _extract_revenue_total_cents(payload)
    revenue_data_as_of = _as_utc(revenue_row["data_as_of"])

    allocation_updated_at = _as_utc(allocation_row["updated_at"])
    metric_cents = _metric_cents_for_entity_type(
        entity_type=entity_type,
        allocated_revenue_cents=int(allocation_row["allocated_revenue_cents"]),
        revenue_total_cents=revenue_total_cents,
    )
    metric_key = _metric_key_for_entity_type(entity_type)
    last_updated = max(allocation_updated_at, revenue_data_as_of)
    freshness_seconds = max(
        0, int((datetime.now(timezone.utc) - last_updated).total_seconds())
    )
    truth_seed = {
        "tenant_id": str(tenant_id),
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "metric_key": metric_key,
        "metric_value_cents": int(metric_cents),
        "revenue_total_cents": int(revenue_total_cents),
        "channel_code": str(allocation_row["channel_code"]),
        "model_type": str(allocation_row["model_type"]),
        "model_version": str(allocation_row["model_version"]),
        "verified": bool(allocation_row["verified"]),
        "allocation_updated_at": allocation_updated_at.isoformat(),
        "revenue_data_as_of": revenue_data_as_of.isoformat(),
    }
    truth_snapshot_version = _truth_snapshot_version(truth_seed)
    truth_snapshot_watermark = _truth_snapshot_watermark(truth_snapshot_version)

    return AttributionExplanationAuthorityRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        tenant_id=tenant_id,
        metric_key=metric_key,
        metric_value_cents=metric_cents,
        metric_value_usd=metric_cents / 100.0,
        channel_code=str(allocation_row["channel_code"]),
        model_type=str(allocation_row["model_type"]),
        model_version=str(allocation_row["model_version"]),
        confidence_score=float(allocation_row["confidence_score"]),
        verification_state=(
            "verified" if bool(allocation_row["verified"]) else "unverified"
        ),
        revenue_cache_key=cache_key,
        revenue_total_cents=revenue_total_cents,
        revenue_total_usd=revenue_total_cents / 100.0,
        revenue_data_as_of=revenue_data_as_of,
        last_updated=last_updated,
        data_freshness_seconds=freshness_seconds,
        truth_snapshot_version=truth_snapshot_version,
        truth_snapshot_watermark=truth_snapshot_watermark,
        truth_snapshot_as_of=last_updated,
    )

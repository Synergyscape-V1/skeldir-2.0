"""Durable non-PII commerce identity persistence for delayed verified-revenue matching."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case

from app.models import AttributionCommerceIdentity


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_provider(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or "unknown"


def _normalize_reference(value: str) -> str:
    return str(value or "").strip().lower()


async def upsert_durable_commerce_identity_link(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    attribution_event_id: UUID,
    provider: str,
    canonical_commerce_reference: str,
    source: str = "ingestion_runtime",
    observed_at: datetime | None = None,
) -> None:
    """
    Persist durable, tenant-scoped, non-PII commerce-grain identity for delayed matching.

    This substrate is intentionally separate from session continuity and user identity.
    """
    normalized_reference = _normalize_reference(canonical_commerce_reference)
    if not normalized_reference:
        return

    now_utc = observed_at.astimezone(timezone.utc) if observed_at else _utc_now()
    normalized_provider = _normalize_provider(provider)

    stmt = insert(AttributionCommerceIdentity)
    await session.execute(
        stmt.values(
            tenant_id=tenant_id,
            attribution_event_id=attribution_event_id,
            provider=normalized_provider,
            canonical_commerce_reference=normalized_reference,
            source=str(source or "ingestion_runtime").strip() or "ingestion_runtime",
            first_observed_at=now_utc,
            last_observed_at=now_utc,
            created_at=now_utc,
            updated_at=now_utc,
        )
        .on_conflict_do_update(
            index_elements=[
                "tenant_id",
                "provider",
                "canonical_commerce_reference",
            ],
            set_={
                "attribution_event_id": case(
                    (
                        AttributionCommerceIdentity.source.in_(
                            ("shopify", "stripe", "paypal", "woocommerce", "webhook")
                        ),
                        stmt.excluded.attribution_event_id,
                    ),
                    else_=AttributionCommerceIdentity.attribution_event_id,
                ),
                "last_observed_at": now_utc,
                "source": case(
                    (
                        AttributionCommerceIdentity.source.in_(
                            ("shopify", "stripe", "paypal", "woocommerce", "webhook")
                        ),
                        stmt.excluded.source,
                    ),
                    else_=AttributionCommerceIdentity.source,
                ),
                "updated_at": now_utc,
            },
        )
    )

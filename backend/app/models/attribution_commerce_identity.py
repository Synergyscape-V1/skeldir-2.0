"""Durable attribution-side commerce identity substrate for B2.3 delayed-arrival matching."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class AttributionCommerceIdentity(Base, TenantMixin):
    __tablename__ = "attribution_commerce_identities"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    attribution_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attribution_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_commerce_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="ingestion_runtime",
    )
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "attribution_event_id",
            name="uq_attr_commerce_identity_tenant_event",
        ),
        UniqueConstraint(
            "tenant_id",
            "provider",
            "canonical_commerce_reference",
            name="uq_attr_commerce_identity_tenant_provider_reference",
        ),
        CheckConstraint(
            "char_length(provider) > 0",
            name="ck_attr_commerce_identity_provider_not_blank",
        ),
        CheckConstraint(
            "char_length(canonical_commerce_reference) > 0",
            name="ck_attr_commerce_identity_reference_not_blank",
        ),
        CheckConstraint(
            "last_observed_at >= first_observed_at",
            name="ck_attr_commerce_identity_observed_time_order",
        ),
        Index(
            "idx_attr_commerce_identity_tenant_provider_reference",
            "tenant_id",
            "provider",
            "canonical_commerce_reference",
        ),
        Index(
            "idx_attr_commerce_identity_tenant_last_observed",
            "tenant_id",
            "last_observed_at",
        ),
        Index(
            "idx_attr_commerce_identity_last_observed",
            "last_observed_at",
        ),
    )

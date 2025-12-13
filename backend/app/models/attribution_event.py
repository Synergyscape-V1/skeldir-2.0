"""
AttributionEvent ORM model.

Maps to the attribution_events table in B0.3 schema foundation.
Enforces idempotency, channel taxonomy FK, and RLS tenant isolation.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin

if TYPE_CHECKING:
    from app.models.channel_taxonomy import ChannelTaxonomy


class AttributionEvent(Base, TenantMixin):
    """
    Attribution event model representing revenue-generating actions.

    Schema Source: db/schema/canonical_schema.sql:675-700
    RLS Enabled: Yes (tenant_id isolation via app.current_tenant_id)
    Idempotency: Enforced via UNIQUE(idempotency_key)
    Channel Validation: FK to channel_taxonomy.code

    B0.4 Critical Columns:
        - id: Primary key
        - idempotency_key: Deduplication key for webhook ingestion
        - channel: FK to channel_taxonomy (normalized via channel_normalization.py)
        - event_type: Event categorization (click, conversion, etc.)
        - raw_payload: Original webhook payload (PII-stripped)
    """

    __tablename__ = "attribution_events"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Timestamps (inherited tenant_id, created_at, updated_at from TenantMixin)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Event Identity & Correlation
    external_event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Revenue Tracking
    revenue_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Raw Data Storage (PII-stripped by PIIStrippingMiddleware)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Idempotency & Deduplication
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )

    # Event Classification
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Channel Attribution (FK to channel_taxonomy.code)
    channel: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("channel_taxonomy.code"),
        nullable=False,
    )

    # Campaign Attribution
    campaign_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    conversion_value_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Currency (ISO 4217)
    currency: Mapped[str] = mapped_column(
        CHAR(3), default="USD", server_default="USD", nullable=False
    )

    # Processing Metadata
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=True
    )
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # Relationships
    channel_taxonomy: Mapped["ChannelTaxonomy"] = relationship(
        "ChannelTaxonomy", back_populates="attribution_events"
    )

    # Table Constraints (replicated from canonical_schema.sql:696-699)
    __table_args__ = (
        CheckConstraint("revenue_cents >= 0", name="attribution_events_revenue_cents_check"),
        CheckConstraint(
            "processing_status IN ('pending', 'processed', 'failed')",
            name="ck_attribution_events_processing_status_valid",
        ),
        CheckConstraint("retry_count >= 0", name="ck_attribution_events_retry_count_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<AttributionEvent(id={self.id}, channel={self.channel}, "
            f"event_type={self.event_type}, revenue_cents={self.revenue_cents})>"
        )

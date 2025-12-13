"""
ChannelTaxonomy ORM model.

Maps to the channel_taxonomy table (reference data) in B0.3 schema foundation.
Defines canonical marketing channel codes used by attribution_events.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, CheckConstraint, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.attribution_event import AttributionEvent


class ChannelTaxonomy(Base):
    """
    Canonical marketing channel taxonomy (reference data).

    Schema Source: db/schema/canonical_schema.sql:996-1005
    RLS Enabled: No (tenant-agnostic reference data)

    Purpose:
        Define standard channel codes used across all tenants for attribution.
        Enforces referential integrity via FK from attribution_events.channel.

    Channel Mapping:
        Source mappings defined in db/channel_mapping.yaml (19 vendor indicators → 10 codes).
        Normalization logic in backend/app/ingestion/channel_normalization.py.

    Canonical Codes (10 total):
        - unknown: Fallback for unmapped channels
        - direct: Direct traffic
        - email: Email campaigns
        - facebook_brand: Facebook brand awareness
        - facebook_paid: Facebook paid ads
        - google_display_paid: Google Display Network
        - google_search_paid: Google Search Ads
        - organic: Organic search/social
        - referral: Referral traffic
        - tiktok_paid: TikTok paid ads

    Note:
        This model does NOT inherit TenantMixin (no tenant_id column).
        Reference data is shared across all tenants.
    """

    __tablename__ = "channel_taxonomy"

    # Primary Key
    code: Mapped[str] = mapped_column(Text, primary_key=True)

    # Channel Metadata
    family: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., 'paid_social', 'organic'
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), nullable=False
    )

    # State Machine
    state: Mapped[str] = mapped_column(
        String(50), default="active", server_default="active", nullable=False
    )

    # Relationships (reverse FK from attribution_events)
    attribution_events: Mapped[List["AttributionEvent"]] = relationship(
        "AttributionEvent", back_populates="channel_taxonomy"
    )

    # Table Constraints (replicated from canonical_schema.sql:1004)
    __table_args__ = (
        CheckConstraint(
            "state IN ('draft', 'active', 'deprecated', 'archived')",
            name="channel_taxonomy_state_check",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ChannelTaxonomy(code={self.code}, display_name={self.display_name}, "
            f"is_paid={self.is_paid}, state={self.state})>"
        )

"""
ORM Models Package.

Exposes all SQLAlchemy ORM models for B0.4 ingestion pipeline.

Models:
    - Base: Declarative base for all models
    - TenantMixin: Common mixin for tenant-scoped tables
    - AttributionEvent: Revenue-generating attribution events (RLS enabled)
    - DeadEvent: Dead-letter queue for failed ingestion (RLS enabled)
    - ChannelTaxonomy: Marketing channel reference data (no RLS)

Usage:
    from app.models import AttributionEvent, DeadEvent, ChannelTaxonomy
    from app.db.session import get_session

    async with get_session(tenant_id=some_uuid) as session:
        event = AttributionEvent(...)
        session.add(event)
        await session.commit()
"""

from app.models.attribution_event import AttributionEvent
from app.models.base import Base, TenantMixin
from app.models.channel_taxonomy import ChannelTaxonomy
from app.models.dead_event import DeadEvent

__all__ = [
    "Base",
    "TenantMixin",
    "AttributionEvent",
    "DeadEvent",
    "ChannelTaxonomy",
]

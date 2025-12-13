"""
SQLAlchemy ORM base classes and mixins.

This module defines the declarative base for all ORM models and common mixins
for tenant isolation and timestamp tracking.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    Uses public schema by default to align with B0.3 schema foundation.
    """

    metadata = MetaData(schema="public")


class TenantMixin:
    """
    Mixin for tenant-scoped tables requiring RLS enforcement.

    All tables with this mixin must have:
    - tenant_id column for RLS policy evaluation
    - created_at and updated_at for audit trail

    RLS Requirement:
        Sessions must set `app.current_tenant_id` session variable using
        `get_session(tenant_id)` from app.db.session module.
    """

    tenant_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

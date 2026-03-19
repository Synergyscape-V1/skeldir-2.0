"""
Tenant-scoped session authority substrate for B1.4-P2.

Defines explicit, expirable session authority rows used by ingestion runtime
to enforce 24-hour session validity and prevent durable cross-session bridges.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class SessionAuthority(Base, TenantMixin):
    __tablename__ = "session_authority"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    invalidation_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    issued_by: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="ingestion_runtime",
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
            "session_id",
            name="uq_session_authority_tenant_session_id",
        ),
        CheckConstraint("expires_at > issued_at", name="ck_session_authority_expires_after_issued"),
        CheckConstraint(
            "expires_at <= issued_at + interval '24 hours'",
            name="ck_session_authority_max_24h",
        ),
        CheckConstraint(
            "invalidated_at IS NULL OR invalidated_at >= issued_at",
            name="ck_session_authority_invalidation_after_issued",
        ),
        Index(
            "idx_session_authority_tenant_expires",
            "tenant_id",
            "expires_at",
        ),
        Index(
            "idx_session_authority_tenant_last_seen",
            "tenant_id",
            "last_seen_at",
        ),
    )

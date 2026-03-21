"""Ephemeral write-time resolution substrate for B1.4-P3 terminal corrective."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class EphemeralOrderResolution(Base, TenantMixin):
    __tablename__ = "ephemeral_order_resolution"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    order_id: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(
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
            "order_id",
            name="uq_ephemeral_order_resolution_tenant_order",
        ),
        CheckConstraint(
            "expires_at > observed_at",
            name="ck_ephemeral_order_resolution_expires_after_observed",
        ),
        CheckConstraint(
            "expires_at <= observed_at + interval '24 hours'",
            name="ck_ephemeral_order_resolution_max_24h",
        ),
        Index(
            "idx_ephemeral_order_resolution_tenant_expires",
            "tenant_id",
            "expires_at",
        ),
        Index(
            "idx_ephemeral_order_resolution_tenant_order",
            "tenant_id",
            "order_id",
        ),
    )


class EphemeralClickResolution(Base, TenantMixin):
    __tablename__ = "ephemeral_click_resolution"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    click_id: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(
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
            "click_id",
            name="uq_ephemeral_click_resolution_tenant_click",
        ),
        CheckConstraint(
            "expires_at > observed_at",
            name="ck_ephemeral_click_resolution_expires_after_observed",
        ),
        CheckConstraint(
            "expires_at <= observed_at + interval '24 hours'",
            name="ck_ephemeral_click_resolution_max_24h",
        ),
        Index(
            "idx_ephemeral_click_resolution_tenant_expires",
            "tenant_id",
            "expires_at",
        ),
        Index(
            "idx_ephemeral_click_resolution_tenant_click",
            "tenant_id",
            "click_id",
        ),
    )

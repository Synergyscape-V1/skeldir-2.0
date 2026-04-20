"""Durable canonical webhook ingress identity envelope (B2.2-P3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class WebhookIngressIdentity(Base, TenantMixin):
    __tablename__ = "webhook_ingress_identities"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attribution_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_native_event_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_native_commerce_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_commerce_reference_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_commerce_reference_value: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_amount_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    verified_amount_scale: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    verified_commerce_ingress_state: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            name="uq_webhook_ingress_identities_event_id",
        ),
        UniqueConstraint(
            "tenant_id",
            "event_id",
            name="uq_webhook_ingress_identities_tenant_event",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_webhook_ingress_identities_tenant_idempotency",
        ),
        CheckConstraint("verified_amount_minor >= 0", name="ck_webhook_ingress_amount_minor_non_negative"),
        CheckConstraint("verified_amount_scale >= 0", name="ck_webhook_ingress_amount_scale_non_negative"),
    )

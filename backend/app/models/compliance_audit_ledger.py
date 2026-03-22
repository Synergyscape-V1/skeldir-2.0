"""Compliance audit ledger substrate for deterministic privacy erasure artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class ComplianceAuditLedger(Base, TenantMixin):
    __tablename__ = "compliance_audit_ledger"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    selector: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    selector_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    effects: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    evidence_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    actor: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'privacy_worker'"),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_compliance_audit_ledger_tenant_idempotency_key",
        ),
        Index(
            "idx_compliance_audit_ledger_tenant_created",
            "tenant_id",
            "created_at",
        ),
        Index(
            "idx_compliance_audit_ledger_tenant_correlation",
            "tenant_id",
            "correlation_id",
        ),
    )

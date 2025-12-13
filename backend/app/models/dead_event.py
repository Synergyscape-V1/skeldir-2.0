"""
DeadEvent ORM model.

Maps to the dead_events table (dead-letter queue) in B0.3 schema foundation.
Stores failed ingestion attempts for operator triage and remediation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeadEvent(Base):
    """
    Dead-letter queue entry for failed webhook ingestion.

    Schema Source: db/schema/canonical_schema.sql:1071-1092
    RLS Enabled: Yes (tenant_id isolation via app.current_tenant_id)

    Purpose:
        Store webhook payloads that fail ingestion validation or processing.
        Enable operator investigation, remediation, and replay workflows.

    B0.4 Critical Columns:
        - id: Primary key
        - raw_payload: Original webhook payload (PII-stripped)
        - error_type: Error classification (validation_error, network_error, etc.)
        - error_message: Human-readable error description
        - retry_count: Number of processing attempts
        - remediation_status: Workflow state (pending, in_progress, resolved, abandoned)

    Note:
        Does NOT use TenantMixin because dead_events has ingested_at instead of created_at,
        and no updated_at column.
    """

    __tablename__ = "dead_events"

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Tenant & Timestamps (manually defined, NOT from Mixin)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    # Source & Classification
    source: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., 'shopify', 'stripe'
    error_code: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., 'VALIDATION_ERROR'
    error_detail: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Raw Payload (PII-stripped)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Event Correlation
    correlation_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    external_event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Error Details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Retry Tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Remediation Workflow
    remediation_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    remediation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Table Constraints (replicated from canonical_schema.sql:1090-1091)
    __table_args__ = (
        CheckConstraint(
            "remediation_status IN ('pending', 'in_progress', 'resolved', 'abandoned')",
            name="ck_dead_events_remediation_status_valid",
        ),
        CheckConstraint("retry_count >= 0", name="ck_dead_events_retry_count_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeadEvent(id={self.id}, source={self.source}, "
            f"error_type={self.error_type}, remediation_status={self.remediation_status})>"
        )

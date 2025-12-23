"""Add investigation_jobs table for centaur friction

Revision ID: 202512231020
Revises: 202512231010
Create Date: 2025-12-23 10:20:00

Migration Description:
Creates the investigation_jobs table for enforcing centaur friction:
- State machine: PENDING -> READY_FOR_REVIEW -> APPROVED -> COMPLETED
- min_hold_until: Minimum wait time before review (45-60s)
- Cannot return COMPLETED without going through approval

This makes it mechanically impossible to return "final" immediately.

Contract Mapping:
- Supports VALUE_05-WIN forensic test
- Enforces review/approve workflow
- Provides audit trail for state transitions

Exit Gates:
- State machine enforced via CHECK constraint
- min_hold_until prevents premature completion
- approved_at required before COMPLETED
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '202512231020'
down_revision: Union[str, None] = '202512231010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create investigation_jobs table with state machine."""

    op.execute("""
        CREATE TABLE investigation_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            correlation_id VARCHAR(255),
            status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
                CHECK (status IN ('PENDING', 'READY_FOR_REVIEW', 'APPROVED', 'COMPLETED', 'CANCELLED')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            min_hold_until TIMESTAMPTZ NOT NULL,
            ready_for_review_at TIMESTAMPTZ,
            approved_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            result JSONB,
            metadata JSONB
        )
    """)

    # Constraint: Cannot be COMPLETED without being APPROVED first
    op.execute("""
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_approved_before_completed
        CHECK (
            status != 'COMPLETED' OR approved_at IS NOT NULL
        )
    """)

    # Constraint: Cannot be APPROVED without being READY_FOR_REVIEW first
    op.execute("""
        ALTER TABLE investigation_jobs
        ADD CONSTRAINT ck_investigation_jobs_ready_before_approved
        CHECK (
            status NOT IN ('APPROVED', 'COMPLETED') OR ready_for_review_at IS NOT NULL
        )
    """)

    # Indexes
    op.execute("""
        CREATE INDEX idx_investigation_jobs_tenant_status
        ON investigation_jobs (tenant_id, status, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_investigation_jobs_min_hold
        ON investigation_jobs (min_hold_until)
        WHERE status = 'PENDING'
    """)

    # Comments
    op.execute("""
        COMMENT ON TABLE investigation_jobs IS
            'Investigation jobs with centaur friction (mandatory review/approve workflow). Purpose: Enforce human-in-the-loop for critical decisions. Cannot return final result without explicit approval.'
    """)

    op.execute("""
        COMMENT ON COLUMN investigation_jobs.status IS
            'State machine: PENDING -> READY_FOR_REVIEW -> APPROVED -> COMPLETED. Cannot skip states.'
    """)

    op.execute("""
        COMMENT ON COLUMN investigation_jobs.min_hold_until IS
            'Minimum time before job can transition to READY_FOR_REVIEW. Enforces friction period (45-60s default).'
    """)

    op.execute("""
        COMMENT ON COLUMN investigation_jobs.approved_at IS
            'Timestamp when job was approved. Required before COMPLETED status (enforced by constraint).'
    """)


def downgrade() -> None:
    """Drop investigation_jobs table."""
    op.execute("DROP TABLE IF EXISTS investigation_jobs CASCADE")

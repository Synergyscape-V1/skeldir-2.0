"""Add LLM call audit table for budget enforcement

Revision ID: 202512231010
Revises: 202512231000
Create Date: 2025-12-23 10:10:00

Migration Description:
Creates the llm_call_audit table for forensic tracking of all LLM call
decisions. This is the "black box recorder" for budget enforcement.

Every LLM call attempt is recorded with:
- Requested model and resolved model (after policy application)
- Estimated cost and cap
- Decision (ALLOW, BLOCK, FALLBACK)
- Reason for decision

Contract Mapping:
- Supports VALUE_03-WIN forensic test
- Enables "0 premium calls beyond cap" proof
- Provides audit trail for budget violations

Exit Gates:
- Table exists with all required columns
- Indexes for tenant and decision queries
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '202512231010'
down_revision: Union[str, None] = '202512231000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create LLM call audit table."""

    op.execute("""
        CREATE TABLE llm_call_audit (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            request_id VARCHAR(255) NOT NULL,
            correlation_id VARCHAR(255),
            requested_model VARCHAR(100) NOT NULL,
            resolved_model VARCHAR(100) NOT NULL,
            estimated_cost_cents INTEGER NOT NULL,
            cap_cents INTEGER NOT NULL,
            decision VARCHAR(20) NOT NULL CHECK (decision IN ('ALLOW', 'BLOCK', 'FALLBACK')),
            reason TEXT NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Indexes for common queries
    op.execute("""
        CREATE INDEX idx_llm_call_audit_tenant_created
        ON llm_call_audit (tenant_id, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_audit_decision
        ON llm_call_audit (decision, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_audit_request_id
        ON llm_call_audit (request_id)
    """)

    # Comments
    op.execute("""
        COMMENT ON TABLE llm_call_audit IS
            'Append-only audit log for LLM call budget decisions. Purpose: Forensic proof of budget enforcement. Every call attempt is recorded with decision and reason.'
    """)

    op.execute("""
        COMMENT ON COLUMN llm_call_audit.requested_model IS
            'The model originally requested by the caller. May differ from resolved_model after policy application.'
    """)

    op.execute("""
        COMMENT ON COLUMN llm_call_audit.resolved_model IS
            'The model actually used after budget policy. Same as requested_model for ALLOW, fallback model for FALLBACK, null-ish for BLOCK.'
    """)

    op.execute("""
        COMMENT ON COLUMN llm_call_audit.decision IS
            'Policy decision: ALLOW (under budget), BLOCK (HTTP 429), FALLBACK (cheaper model substituted).'
    """)


def downgrade() -> None:
    """Drop LLM call audit table."""
    # CI:DESTRUCTIVE_OK - Downgrade function intentionally removes forensic audit table
    op.execute("DROP TABLE IF EXISTS llm_call_audit CASCADE")  # CI:DESTRUCTIVE_OK

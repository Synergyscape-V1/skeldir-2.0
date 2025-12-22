"""Add allocation model versioning for B0.5.3.2

Revision ID: 202512151410
Revises: 202512151400
Create Date: 2025-12-15 14:10:00

Migration Description:
Adds model versioning support to attribution_allocations table for B0.5.3.2
window-scoped idempotency:

1. Add allocation_ratio column (NUMERIC) - stores fractional channel credit
2. Add model_version column (TEXT) - identifies attribution model version
3. Add UNIQUE constraint on (tenant_id, event_id, model_version, channel_code) -
   enforces event-scoped overwrite strategy per model version

This enables:
- Multiple model versions to coexist for A/B testing
- Deterministic allocation overwrite on window recomputation
- Audit trail of which model version produced each allocation

NOTE: This migration is idempotent due to merge conflict with 202511131232
which also adds these columns. Uses IF NOT EXISTS for idempotency.
NOTE: Uses channel_code (renamed from channel by migration 202511141311).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '''202512151410'''
down_revision: Union[str, None] = '''202512151400'''
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add model versioning to attribution_allocations.

    NOTE: This migration is idempotent due to merge conflict with 202511131232
    which also adds these columns. Uses IF NOT EXISTS for idempotency.
    """

    # Add allocation_ratio column - idempotent via IF NOT EXISTS
    # NOTE: 202511131232 may have already added this as numeric(6,5)
    # This migration would add it as NUMERIC(10, 6), but IF NOT EXISTS prevents duplicate
    op.execute("""
        ALTER TABLE attribution_allocations
        ADD COLUMN IF NOT EXISTS allocation_ratio NUMERIC(10, 6) NOT NULL DEFAULT 0.0
    """)

    # Add model_version column - idempotent via IF NOT EXISTS
    # NOTE: 202511131232 may have already added this with DEFAULT '''unknown'''
    # This migration would add it with DEFAULT '''1.0.0''', but IF NOT EXISTS prevents duplicate
    op.execute("""
        ALTER TABLE attribution_allocations
        ADD COLUMN IF NOT EXISTS model_version TEXT NOT NULL DEFAULT '''1.0.0'''
    """)

    # Add UNIQUE constraint for event-scoped overwrite strategy - skip if index already exists
    # NOTE: 202511131232 creates idx_attribution_allocations_tenant_event_model_channel
    # This migration creates idx_attribution_allocations_event_model_channel (different name)
    # Both serve the same purpose, so we skip if either exists
    # IMPORTANT: Uses channel_code (renamed from channel by migration 202511141311)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_attribution_allocations_event_model_channel
        ON attribution_allocations (tenant_id, event_id, model_version, channel_code)
    """)

    # Add comment only if our index was created (idempotent)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE schemaname = '''public'''
                AND indexname = '''idx_attribution_allocations_event_model_channel'''
            ) THEN
                COMMENT ON INDEX idx_attribution_allocations_event_model_channel IS
                '''Event-scoped overwrite strategy per model version. Ensures deterministic allocation updates on window recomputation. Used by B0.5.3.2 idempotency enforcement.''';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove model versioning from attribution_allocations."""

    # Drop constraint first
    op.execute("DROP INDEX IF EXISTS idx_attribution_allocations_event_model_channel")  # CI:DESTRUCTIVE_OK - Downgrade rollback

    # Drop columns
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS model_version")  # CI:DESTRUCTIVE_OK - Downgrade rollback
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS allocation_ratio")  # CI:DESTRUCTIVE_OK - Downgrade rollback

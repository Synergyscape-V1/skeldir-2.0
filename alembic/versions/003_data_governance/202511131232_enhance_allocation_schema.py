"""Enhance attribution_allocations schema with revenue accounting determinism

Revision ID: 202511131232
Revises: 202511131121
Create Date: 2025-11-13 12:32:00

Migration Description:
Adds revenue accounting determinism to attribution_allocations table per Phase 4A requirements:
- allocation_ratio: numeric(6,5) with CHECK (0-1) for allocation ratio tracking
- model_version: text NOT NULL for attribution model version tracking
- channel_code validation: CHECK constraint for channel code enum (deferred to contract review)
- Updated idempotency constraint: includes model_version in unique key

Contract Mapping:
- Supports deterministic revenue allocation per (tenant_id, event_id, model_version)
- Enables sum-equality validation (allocations sum to event revenue)

Governance Compliance:
- Style guide compliance (snake_case, CHECK constraints, comments)
- Contract mapping (allocation_ratio, model_version fields)
- DDL lint rules (comments, constraints, indexes)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511131232'
down_revision: Union[str, None] = '202511131121'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply migration changes.
    
    Adds:
    1. allocation_ratio column (numeric(6,5) NOT NULL with CHECK 0-1)
    2. model_version column (text NOT NULL)
    3. channel_code validation (CHECK constraint - deferred to contract review)
    4. Updated idempotency unique index (includes model_version)
    """
    
    # Add allocation_ratio column
    op.execute("""
        ALTER TABLE attribution_allocations
            ADD COLUMN IF NOT EXISTS allocation_ratio numeric(6,5) NOT NULL DEFAULT 0.0
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations
            ADD CONSTRAINT ck_attribution_allocations_allocation_ratio_bounds
            CHECK (allocation_ratio >= 0 AND allocation_ratio <= 1)
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.allocation_ratio IS
            'Allocation ratio (0.0 to 1.0) representing the proportion of event revenue allocated to this channel. Purpose: Enable deterministic revenue accounting and sum-equality validation. Data class: Non-PII.'
    """)
    
    # Add model_version column
    op.execute("""
        ALTER TABLE attribution_allocations
            ADD COLUMN IF NOT EXISTS model_version text NOT NULL DEFAULT 'unknown'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.model_version IS
            'Attribution model version (semantic version string). Purpose: Track which model version generated this allocation, enabling model rollups and sum-equality validation per model version. Data class: Non-PII.'
    """)
    
    # Add channel_code validation (CHECK constraint)
    # NOTE: Channel codes deferred to contract review. Using common codes as placeholder.
    # This should be updated once contracts define the channel_code enum.
    op.execute("""
        ALTER TABLE attribution_allocations
            ADD CONSTRAINT ck_attribution_allocations_channel_code_valid
            CHECK (channel IN (
                'google_search',
                'facebook_ads',
                'direct',
                'email',
                'organic',
                'referral',
                'social',
                'paid_search',
                'display'
            ))
    """)
    
    op.execute("""
        COMMENT ON CONSTRAINT ck_attribution_allocations_channel_code_valid ON attribution_allocations IS
            'Validates channel code against allowed enum values. Purpose: Enforce channel code consistency. NOTE: Channel codes should be reviewed against contract definitions. Data class: Non-PII.'
    """)
    
    # Create updated idempotency unique index with model_version
    # Drop old indexes if they exist (they were created in add_core_tables migration)
    # Note: The original migration didn't have a unique constraint on (tenant_id, event_id, model_version, channel)
    # We're adding it now as part of Phase 4A
    
    op.execute("""
        CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel
            ON attribution_allocations (tenant_id, event_id, model_version, channel)
            WHERE model_version IS NOT NULL
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_attribution_allocations_tenant_event_model_channel IS
            'Unique index ensuring idempotency per (tenant_id, event_id, model_version, channel). Purpose: Prevent duplicate allocations for the same event/model/channel combination. Supports sum-equality validation.'
    """)
    
    # Add index on (tenant_id, model_version) for model rollups (Jamie's requirement)
    op.execute("""
        CREATE INDEX idx_attribution_allocations_tenant_model_version
            ON attribution_allocations (tenant_id, model_version)
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_attribution_allocations_tenant_model_version IS
            'Composite index on (tenant_id, model_version). Purpose: Enable fast model rollups and sum-equality validation queries per model version.'
    """)


def downgrade() -> None:
    """
    Rollback migration changes.
    
    Removes:
    1. allocation_ratio column
    2. model_version column
    3. channel_code validation constraint
    4. Updated idempotency unique index
    """
    
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_attribution_allocations_tenant_model_version")
    op.execute("DROP INDEX IF EXISTS idx_attribution_allocations_tenant_event_model_channel")
    
    # Drop constraints
    op.execute("ALTER TABLE attribution_allocations DROP CONSTRAINT IF EXISTS ck_attribution_allocations_channel_code_valid")
    op.execute("ALTER TABLE attribution_allocations DROP CONSTRAINT IF EXISTS ck_attribution_allocations_allocation_ratio_bounds")
    
    # Drop columns
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS model_version")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS allocation_ratio")


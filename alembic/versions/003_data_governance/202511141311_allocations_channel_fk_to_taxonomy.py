"""Migrate attribution_allocations from CHECK constraint to FK to channel_taxonomy

Revision ID: 202511141311
Revises: 202511141310
Create Date: 2025-11-14 13:11:00

Migration Description:
Safely migrates attribution_allocations from legacy CHECK constraint to
FOREIGN KEY constraint referencing channel_taxonomy table.

This migration implements Phase T2 of B0.3 Channel Taxonomy:
1. DROP CHECK constraint ck_attribution_allocations_channel_code_valid
2. RENAME COLUMN channel TO channel_code
3. Data backfill: Map legacy CHECK values to canonical taxonomy codes
4. ADD FOREIGN KEY constraint fk_attribution_allocations_channel_code

Legacy to Canonical Mapping:
- 'google_search' → 'google_search_paid'
- 'facebook_ads' → 'facebook_paid'
- 'direct' → 'direct' (unchanged)
- 'email' → 'email' (unchanged)
- 'organic' → 'organic' (unchanged)
- 'referral' → 'referral' (unchanged)
- 'social' → 'facebook_paid' (mapped to closest paid social channel)
- 'paid_search' → 'google_search_paid'
- 'display' → 'google_display_paid'

Contract Mapping:
- Enforces canonical channel taxonomy via FK constraint
- Replaces ad-hoc CHECK constraint with referential integrity
- Supports channel_mapping.yaml as ingestion mapping source

Governance Compliance:
- Style guide compliance (snake_case, FK constraints, comments)
- Policy alignment (canonical taxonomy requirement)
- DDL lint rules (comments, constraint naming)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511141311'
down_revision: Union[str, None] = '202511141310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migrate from CHECK constraint to FK constraint.
    
    Execution order is critical:
    1. Drop CHECK constraint
    2. Rename column for clarity
    3. Backfill legacy values to canonical codes
    4. Add FK constraint (will fail if backfill incomplete)
    """
    
    # Step 1: Drop CHECK constraint
    op.execute("""
        ALTER TABLE attribution_allocations 
        DROP CONSTRAINT IF EXISTS ck_attribution_allocations_channel_code_valid
    """)
    
    # Step 2: Rename column from channel to channel_code
    op.execute("""
        ALTER TABLE attribution_allocations 
        RENAME COLUMN channel TO channel_code
    """)
    
    # Step 3: Data backfill - Map legacy values to canonical codes
    # This must complete successfully before FK constraint can be added
    
    # Map legacy values to canonical taxonomy codes
    op.execute("""
        UPDATE attribution_allocations
        SET channel_code = 'google_search_paid'
        WHERE channel_code = 'google_search'
    """)
    
    op.execute("""
        UPDATE attribution_allocations
        SET channel_code = 'facebook_paid'
        WHERE channel_code = 'facebook_ads'
    """)
    
    op.execute("""
        UPDATE attribution_allocations
        SET channel_code = 'facebook_paid'
        WHERE channel_code = 'social'
    """)
    
    op.execute("""
        UPDATE attribution_allocations
        SET channel_code = 'google_search_paid'
        WHERE channel_code = 'paid_search'
    """)
    
    op.execute("""
        UPDATE attribution_allocations
        SET channel_code = 'google_display_paid'
        WHERE channel_code = 'display'
    """)
    
    # Note: 'direct', 'email', 'organic', 'referral' remain unchanged
    # as they already match canonical codes
    
    # Validate that all channel_code values exist in taxonomy
    # This query will raise an exception if any unmapped values remain
    op.execute("""
        DO $$
        DECLARE
            unmapped_count INTEGER;
            unmapped_values TEXT;
        BEGIN
            SELECT COUNT(*), string_agg(DISTINCT channel_code, ', ')
            INTO unmapped_count, unmapped_values
            FROM attribution_allocations
            WHERE channel_code NOT IN (SELECT code FROM channel_taxonomy);
            
            IF unmapped_count > 0 THEN
                RAISE EXCEPTION 'Cannot add FK constraint: % rows have unmapped channel_code values: %. All values must exist in channel_taxonomy.', unmapped_count, unmapped_values;
            END IF;
        END $$;
    """)
    
    # Step 4: Add FOREIGN KEY constraint
    op.execute("""
        ALTER TABLE attribution_allocations
        ADD CONSTRAINT fk_attribution_allocations_channel_code
        FOREIGN KEY (channel_code) REFERENCES channel_taxonomy(code)
    """)
    
    # Update column comment
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.channel_code IS
            'Canonical channel code (FK to channel_taxonomy.code). Purpose: Identify attribution channel using canonical taxonomy. Data class: Non-PII.'
    """)


def downgrade() -> None:
    """
    Reverse migration: Remove FK, rename column, restore CHECK constraint.
    
    WARNING: This rollback removes FK enforcement and restores ad-hoc CHECK.
    Data backfill is not reversed (legacy values remain mapped).
    """
    
    # Step 1: Drop FK constraint
    op.execute("""
        ALTER TABLE attribution_allocations
        DROP CONSTRAINT IF EXISTS fk_attribution_allocations_channel_code
    """)
    
    # Step 2: Rename column back to channel
    op.execute("""
        ALTER TABLE attribution_allocations
        RENAME COLUMN channel_code TO channel
    """)
    
    # Step 3: Restore CHECK constraint (with original legacy values)
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
    
    # Restore original column comment
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.channel IS
            'Channel identifier (e.g., google_search, facebook_ads). Purpose: Identify attribution channel. Data class: Non-PII.'
    """)



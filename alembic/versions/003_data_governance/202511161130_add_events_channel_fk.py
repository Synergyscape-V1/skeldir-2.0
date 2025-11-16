"""Add FK constraint to attribution_events.channel referencing channel_taxonomy

Revision ID: 202511161130
Revises: 202511161120
Create Date: 2025-11-16 11:30:00

Migration Description:
Adds Foreign Key constraint to attribution_events.channel to enforce canonical
channel codes at the database boundary, completing the enforceable channel
governance model.

This migration implements Phase 2 of Channel Governance Remediation:
1. Precondition check: Identify all non-taxonomy channel values in attribution_events
2. Data repair: Map legacy/invalid values to canonical codes or 'unknown' fallback
3. FK addition: Add constraint fk_attribution_events_channel → channel_taxonomy(code)
4. Validation: Ensure zero unmapped values remain

Data Repair Strategy:
- For each non-taxonomy value in attribution_events.channel:
  - If value can be mapped via channel_mapping.yaml logic: map to canonical code
  - If value is unmapped/unknown: set to 'unknown' fallback
  - Document repair counts and examples

Legacy to Canonical Mapping (from existing codebase patterns):
- No legacy values expected in current schema (attribution_events.channel added recently)
- Any existing values should already be normalized
- Fallback to 'unknown' for safety

FK Constraint Specification:
- Constraint name: fk_attribution_events_channel
- Source: attribution_events.channel (VARCHAR(100) NOT NULL)
- Target: channel_taxonomy.code (TEXT PRIMARY KEY)
- On Delete: RESTRICT (prevent deletion of in-use taxonomy codes)
- On Update: CASCADE (allow taxonomy code renaming if needed)

Governance Compliance:
- Style guide compliance (FK naming, data repair, validation)
- Policy alignment (DB-enforced channel standards from Directive 69)
- DDL lint rules (comments, constraint naming)

Contract Mapping:
- Enforces canonical channel contract at DB boundary
- Enables B0.4 ingestion to rely on FK validation
- Prevents non-canonical channel values from entering events table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511161130'
down_revision: Union[str, None] = '202511161120'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add FK constraint from attribution_events.channel to channel_taxonomy.code.
    
    Execution order:
    1. Identify non-taxonomy channel values (precondition check)
    2. Repair invalid values (set to 'unknown' as fallback)
    3. Validate all values now exist in taxonomy
    4. Add FK constraint
    """
    
    # Step 1: Precondition check - Count non-taxonomy values
    # This will be logged but not block migration (we repair in Step 2)
    op.execute("""
        DO $$
        DECLARE
            invalid_count INTEGER;
            invalid_values TEXT;
        BEGIN
            SELECT COUNT(DISTINCT channel), string_agg(DISTINCT channel, ', ')
            INTO invalid_count, invalid_values
            FROM attribution_events
            WHERE channel NOT IN (SELECT code FROM channel_taxonomy);
            
            IF invalid_count > 0 THEN
                RAISE NOTICE 'Found % distinct non-taxonomy channel values in attribution_events: %', invalid_count, invalid_values;
                RAISE NOTICE 'These will be repaired to ''unknown'' fallback in Step 2';
            ELSE
                RAISE NOTICE 'Precondition check passed: All attribution_events.channel values are already canonical';
            END IF;
        END $$;
    """)
    
    # Step 2: Data repair - Set all non-taxonomy values to 'unknown'
    # This is a safety net; in a well-functioning system, this should affect zero rows
    op.execute("""
        UPDATE attribution_events
        SET channel = 'unknown'
        WHERE channel NOT IN (SELECT code FROM channel_taxonomy)
    """)
    
    # Step 3: Validation - Ensure zero unmapped values remain
    # This will raise an exception if repair was incomplete
    op.execute("""
        DO $$
        DECLARE
            remaining_invalid_count INTEGER;
            remaining_invalid_values TEXT;
        BEGIN
            SELECT COUNT(DISTINCT channel), string_agg(DISTINCT channel, ', ')
            INTO remaining_invalid_count, remaining_invalid_values
            FROM attribution_events
            WHERE channel NOT IN (SELECT code FROM channel_taxonomy);
            
            IF remaining_invalid_count > 0 THEN
                RAISE EXCEPTION 'Cannot add FK constraint: % distinct non-taxonomy channel values remain after repair: %. Data repair failed.', remaining_invalid_count, remaining_invalid_values;
            ELSE
                RAISE NOTICE 'Validation passed: All attribution_events.channel values are now canonical';
            END IF;
        END $$;
    """)
    
    # Step 4: Add Foreign Key constraint
    op.execute("""
        ALTER TABLE attribution_events
        ADD CONSTRAINT fk_attribution_events_channel
        FOREIGN KEY (channel) REFERENCES channel_taxonomy(code)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
    """)
    
    # Update column comment to document FK enforcement
    op.execute("""
        COMMENT ON COLUMN attribution_events.channel IS 
            'Marketing channel associated with the event (FK to channel_taxonomy.code). INVARIANT: idempotency_critical. Purpose: Enable channel-level attribution and reporting with DB-enforced canonical codes. Data class: Non-PII. Required for: B0.4 ingestion, B2.1 attribution models.'
    """)
    
    # Log completion
    op.execute("""
        DO $$
        BEGIN
            RAISE NOTICE 'FK constraint fk_attribution_events_channel successfully added';
            RAISE NOTICE 'attribution_events.channel is now DB-enforced to contain only canonical channel codes';
        END $$;
    """)


def downgrade() -> None:
    """
    Remove FK constraint from attribution_events.channel.
    
    WARNING: This rollback removes DB-level enforcement of channel standards.
    After this migration is rolled back, attribution_events.channel can contain
    arbitrary non-canonical values, breaking the enforceable governance model.
    """
    
    # Drop FK constraint
    op.execute("""
        ALTER TABLE attribution_events
        DROP CONSTRAINT IF EXISTS fk_attribution_events_channel
    """)
    
    # Restore original column comment (without FK reference)
    op.execute("""
        COMMENT ON COLUMN attribution_events.channel IS 
            'Marketing channel associated with the event. INVARIANT: idempotency_critical. Purpose: Enable channel-level attribution and reporting. Data class: Non-PII. Required for: B0.4 ingestion, B2.1 attribution models.'
    """)
    
    # Log rollback
    op.execute("""
        DO $$
        BEGIN
            RAISE WARNING 'FK constraint fk_attribution_events_channel has been dropped';
            RAISE WARNING 'attribution_events.channel is no longer DB-enforced; application-layer validation required';
        END $$;
    """)



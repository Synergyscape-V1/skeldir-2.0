"""Add retry tracking and remediation fields to dead_events

Revision ID: 202511151440
Revises: 202511151430
Create Date: 2025-11-15 14:40:00.000000

Phase 8a of B0.3 Schema Realignment Plan

This migration adds 9 columns to dead_events for comprehensive error tracking:
1. event_type - Type of event that failed (NOT NULL)
2. error_type - Categorization of the error (NOT NULL)
3. error_message - Detailed error message (NOT NULL)
4. error_traceback - Stack trace of the error
5. retry_count - Number of processing retry attempts (NOT NULL DEFAULT 0)
6. last_retry_at - Timestamp of last retry attempt
7. remediation_status - Status of remediation (pending, in_progress, resolved, abandoned)
8. remediation_notes - Notes on remediation actions
9. resolved_at - Timestamp when dead event was resolved

Additionally:
- Adds CHECK constraint on remediation_status enum
- Creates index for remediation queue queries
- Aligns with canonical dead_events specification

These changes are required for:
- B0.5 Error Handling & Retry Logic
- Dead Event Remediation Workflow

Exit Gates:
- Migration applies cleanly
- All 9 columns exist with correct types
- remediation_status CHECK constraint enforced
- Canonical remediation index exists

References:
- Architecture Guide §3.1 (Dead Events Table)
- db/schema/canonical_schema.sql (dead_events table)
- db/schema/schema_gap_catalogue.md (Table 5, dead_events gaps)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151440'
down_revision: Union[str, None] = '202511151430'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Add retry tracking and remediation columns to dead_events.
    
    Implementation strategy:
    1. Add all columns as nullable first (except those with defaults)
    2. Backfill with appropriate values for legacy data
    3. Set NOT NULL constraints for required columns
    4. Add CHECK constraint on remediation_status
    5. Create canonical index
    6. Add comments with INVARIANT tags
    """
    
    # ========================================================================
    # Step 1: Add new columns
    # ========================================================================
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN event_type VARCHAR(50)
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN error_type VARCHAR(100)
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN error_message TEXT
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN error_traceback TEXT
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN retry_count INTEGER DEFAULT 0
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN last_retry_at TIMESTAMPTZ
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN remediation_status VARCHAR(20) DEFAULT 'pending'
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN remediation_notes TEXT
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD COLUMN resolved_at TIMESTAMPTZ
    """)
    
    # ========================================================================
    # Step 2: Backfill with defaults for legacy data
    # ========================================================================
    
    op.execute("""
        UPDATE dead_events 
        SET event_type = 'unknown',
            error_type = 'legacy_error',
            error_message = 'Legacy dead event - details unavailable',
            retry_count = 0,
            remediation_status = 'pending'
        WHERE event_type IS NULL
    """)
    
    # ========================================================================
    # Step 3: Set NOT NULL constraints for required columns
    # ========================================================================
    
    op.execute("""
        ALTER TABLE dead_events 
        ALTER COLUMN event_type SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ALTER COLUMN error_type SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ALTER COLUMN error_message SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ALTER COLUMN retry_count SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ALTER COLUMN remediation_status SET NOT NULL
    """)
    
    # ========================================================================
    # Step 4: Add CHECK constraint on remediation_status
    # ========================================================================
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD CONSTRAINT ck_dead_events_remediation_status_valid 
        CHECK (remediation_status IN ('pending', 'in_progress', 'resolved', 'ignored'))
    """)
    
    op.execute("""
        ALTER TABLE dead_events 
        ADD CONSTRAINT ck_dead_events_retry_count_positive 
        CHECK (retry_count >= 0)
    """)
    
    # ========================================================================
    # Step 5: Create canonical index
    # ========================================================================
    
    op.execute("""
        CREATE INDEX idx_dead_events_remediation 
        ON dead_events (remediation_status, created_at DESC)
    """)
    
    # ========================================================================
    # Step 6: Add comments with INVARIANT tags
    # ========================================================================
    
    op.execute("""
        COMMENT ON COLUMN dead_events.event_type IS 
            'Type of event that failed processing. INVARIANT: processing_critical. Purpose: Enable event-type specific remediation workflows. Data class: Non-PII. Required for: B0.5 error handling, remediation routing.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.error_type IS 
            'Categorization of the error (e.g., validation_error, network_error, data_corruption). INVARIANT: processing_critical. Purpose: Enable error-type specific remediation and alerting. Data class: Non-PII. Required for: B0.5 error classification, alert routing.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.error_message IS 
            'Detailed error message describing what went wrong. INVARIANT: processing_critical. Purpose: Provide diagnostic information for remediation. Data class: Non-PII (may contain limited technical data). Required for: B0.5 error debugging, remediation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.error_traceback IS 
            'Stack trace of the error for debugging. INVARIANT: processing_critical. Purpose: Provide detailed technical context for engineering investigation. Data class: Non-PII. Required for: B0.5 error debugging.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.retry_count IS 
            'Number of times processing has been retried. INVARIANT: processing_critical. Purpose: Track retry attempts to prevent infinite loops. Data class: Non-PII. Required for: B0.5 retry logic, dead event detection.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.last_retry_at IS 
            'Timestamp of the last retry attempt. INVARIANT: processing_critical. Purpose: Track retry timing for backoff logic and monitoring. Data class: Non-PII. Required for: B0.5 exponential backoff, retry monitoring.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.remediation_status IS 
            'Status of the remediation effort (pending, in_progress, resolved, ignored). INVARIANT: processing_critical. Purpose: Track remediation workflow state. Data class: Non-PII. Required for: B0.5 remediation queue, SLA tracking.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.remediation_notes IS 
            'Notes on remediation actions taken by engineers. INVARIANT: processing_critical. Purpose: Document remediation history for knowledge base. Data class: Non-PII. Required for: B0.5 remediation documentation, postmortem analysis.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN dead_events.resolved_at IS 
            'Timestamp when the dead event was successfully resolved. INVARIANT: processing_critical. Purpose: Track resolution timing for SLA and metrics. Data class: Non-PII. Required for: B0.5 remediation SLA tracking, metrics.'
    """)
    
    # Add comments on constraints
    op.execute("""
        COMMENT ON CONSTRAINT ck_dead_events_remediation_status_valid ON dead_events IS 
            'Ensures remediation_status is a valid enum value. Purpose: Enforce remediation workflow integrity. Required for: B0.5 remediation queue.'
    """)
    
    op.execute("""
        COMMENT ON CONSTRAINT ck_dead_events_retry_count_positive ON dead_events IS 
            'Ensures retry_count is non-negative. Purpose: Prevent invalid retry counts. Required for: B0.5 retry logic.'
    """)
    
    # Add comment on index
    op.execute("""
        COMMENT ON INDEX idx_dead_events_remediation IS 
            'Optimizes remediation queue queries. Purpose: Enable fast lookup of events by remediation status. Required for: B0.5 remediation dashboard.'
    """)


def downgrade() -> None:
    """
    Remove retry tracking and remediation columns.
    
    WARNING: This will drop columns and all data in them.
    """
    
    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_dead_events_remediation")
    
    # Drop constraints
    op.execute("ALTER TABLE dead_events DROP CONSTRAINT IF EXISTS ck_dead_events_retry_count_positive")
    op.execute("ALTER TABLE dead_events DROP CONSTRAINT IF EXISTS ck_dead_events_remediation_status_valid")
    
    # Drop columns
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS resolved_at")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS remediation_notes")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS remediation_status")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS last_retry_at")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS retry_count")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS error_traceback")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS error_message")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS error_type")
    op.execute("ALTER TABLE dead_events DROP COLUMN IF EXISTS event_type")



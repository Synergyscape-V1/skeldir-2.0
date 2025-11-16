"""Realign attribution_events table with canonical schema

Revision ID: 202511151410
Revises: 202511151400
Create Date: 2025-11-15 14:10:00.000000

Phase 5 of B0.3 Schema Realignment Plan

This migration adds 10 BLOCKING columns required by the canonical schema:
1. idempotency_key - Single-column unique key for deduplication (replaces composite approach)
2. event_type - Event categorization (click, impression, purchase, etc.)
3. channel - Marketing channel associated with the event
4. campaign_id - Campaign identifier
5. conversion_value_cents - Monetary value of conversion
6. currency - ISO 4217 currency code
7. event_timestamp - Canonical timestamp field (replaces occurred_at semantically)
8. processed_at - When the event was processed
9. processing_status - Processing state (pending, processed, failed)
10. retry_count - Number of processing retries

Additionally:
- Makes session_id NOT NULL (was nullable)
- Adds CHECK constraint on processing_status
- Drops old composite idempotency indexes
- Adds canonical indexes for event_timestamp and processing_status

These changes are BLOCKING for:
- B0.4 Ingestion (requires idempotency_key, event_type, channel)
- B0.5 Workers (requires processing_status queue)
- B2.3 Currency (requires currency column)

Exit Gates:
- Migration applies cleanly
- All 10 columns exist with correct types and nullability
- idempotency_key UNIQUE constraint enforced
- session_id NOT NULL constraint enforced
- processing_status CHECK constraint enforced
- Old composite indexes dropped, canonical indexes created

References:
- Architecture Guide §3.1 (Attribution Events Table)
- db/schema/canonical_schema.sql (lines 41-88)
- db/schema/schema_gap_catalogue.md (Table 2, BLOCKING gaps)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151410'
down_revision: Union[str, None] = '202511151400'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Realign attribution_events table with canonical schema.
    
    Implementation strategy:
    1. Add all columns as nullable first
    2. Backfill data from existing columns where possible
    3. Set NOT NULL constraints after backfill
    4. Add UNIQUE and CHECK constraints
    5. Drop old composite idempotency indexes
    6. Add canonical indexes
    7. Add comments with INVARIANT tags
    """
    
    # ========================================================================
    # Step 1: Add new columns as nullable
    # ========================================================================
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN idempotency_key VARCHAR(255)
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN event_type VARCHAR(50)
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN channel VARCHAR(100)
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN campaign_id VARCHAR(255)
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN conversion_value_cents INTEGER
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN currency VARCHAR(3) DEFAULT 'USD'
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN event_timestamp TIMESTAMPTZ
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN processed_at TIMESTAMPTZ DEFAULT now()
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN processing_status VARCHAR(20) DEFAULT 'pending'
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD COLUMN retry_count INTEGER DEFAULT 0
    """)
    
    # ========================================================================
    # Step 2: Backfill data from existing columns
    # ========================================================================
    
    # Backfill idempotency_key from composite external_event_id/correlation_id
    op.execute("""
        UPDATE attribution_events 
        SET idempotency_key = COALESCE(
            tenant_id::text || ':ext:' || external_event_id,
            tenant_id::text || ':cor:' || correlation_id::text,
            tenant_id::text || ':id:' || id::text
        )
        WHERE idempotency_key IS NULL
    """)
    
    # Backfill event_timestamp from occurred_at
    op.execute("""
        UPDATE attribution_events 
        SET event_timestamp = occurred_at 
        WHERE event_timestamp IS NULL
    """)
    
    # Backfill conversion_value_cents from revenue_cents
    op.execute("""
        UPDATE attribution_events 
        SET conversion_value_cents = revenue_cents 
        WHERE conversion_value_cents IS NULL
    """)
    
    # Set default values for new categorical columns (to be populated by application)
    # Note: In production, these would be populated based on raw_payload analysis
    op.execute("""
        UPDATE attribution_events 
        SET event_type = 'unknown',
            channel = 'unknown',
            processing_status = 'processed'
        WHERE event_type IS NULL OR channel IS NULL
    """)
    
    # ========================================================================
    # Step 3: Set NOT NULL constraints after backfill
    # ========================================================================
    
    op.execute("""
        ALTER TABLE attribution_events 
        ALTER COLUMN idempotency_key SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ALTER COLUMN event_type SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ALTER COLUMN channel SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ALTER COLUMN event_timestamp SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ALTER COLUMN session_id SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ALTER COLUMN processing_status SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ALTER COLUMN retry_count SET NOT NULL
    """)
    
    # ========================================================================
    # Step 4: Add UNIQUE constraint and CHECK constraints
    # ========================================================================
    
    op.execute("""
        CREATE UNIQUE INDEX idx_events_idempotency 
        ON attribution_events (idempotency_key)
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD CONSTRAINT ck_attribution_events_processing_status_valid 
        CHECK (processing_status IN ('pending', 'processed', 'failed'))
    """)
    
    op.execute("""
        ALTER TABLE attribution_events 
        ADD CONSTRAINT ck_attribution_events_retry_count_positive 
        CHECK (retry_count >= 0)
    """)
    
    # ========================================================================
    # Step 5: Drop old composite idempotency indexes
    # ========================================================================
    
    op.execute("""
        DROP INDEX IF EXISTS idx_attribution_events_tenant_external_event_id
    """)
    
    op.execute("""
        DROP INDEX IF EXISTS idx_attribution_events_tenant_correlation_id
    """)
    
    # ========================================================================
    # Step 6: Add canonical indexes
    # ========================================================================
    
    op.execute("""
        CREATE INDEX idx_events_tenant_timestamp 
        ON attribution_events (tenant_id, event_timestamp DESC)
    """)
    
    op.execute("""
        CREATE INDEX idx_events_processing_status 
        ON attribution_events (processing_status, processed_at) 
        WHERE processing_status = 'pending'
    """)
    
    # ========================================================================
    # Step 7: Add comments with INVARIANT tags
    # ========================================================================
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.idempotency_key IS 
            'Unique key to prevent duplicate event ingestion. INVARIANT: idempotency_critical. Purpose: Ensure exactly-once event processing. Data class: Non-PII. Required for: B0.4 ingestion deduplication. Must be unique across all tenants.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.event_type IS 
            'Categorization of the event (click, impression, purchase, etc.). INVARIANT: idempotency_critical. Purpose: Enable event-type specific processing and analytics. Data class: Non-PII. Required for: B0.4 ingestion routing, B0.5 worker queue.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.channel IS 
            'Marketing channel associated with the event. INVARIANT: idempotency_critical. Purpose: Enable channel-level attribution and reporting. Data class: Non-PII. Required for: B0.4 ingestion, B2.1 attribution models.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.campaign_id IS 
            'Campaign identifier for attribution tracking. INVARIANT: analytics_important. Purpose: Link events to campaigns for attribution. Data class: Non-PII. Required for: B2.1 attribution models.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.conversion_value_cents IS 
            'Monetary value of the conversion event in cents. INVARIANT: financial_critical. Purpose: Track revenue associated with events. Data class: Non-PII. Required for: B2.1 attribution models, revenue allocation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.currency IS 
            'ISO 4217 currency code (e.g., USD, EUR). INVARIANT: financial_critical. Purpose: Support multi-currency revenue tracking. Data class: Non-PII. Required for: B2.3 currency conversion.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.event_timestamp IS 
            'Timestamp when the event occurred. INVARIANT: idempotency_critical. Purpose: Temporal ordering and time-series analysis. Data class: Non-PII. Required for: B0.5 event processing, B2.1 attribution models.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.processed_at IS 
            'Timestamp when the event was processed. INVARIANT: analytics_important. Purpose: Track processing latency and audit trail. Data class: Non-PII. Required for: B0.5 worker monitoring.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.processing_status IS 
            'Current processing status (pending, processed, failed). INVARIANT: idempotency_critical. Purpose: Enable worker queue and retry logic. Data class: Non-PII. Required for: B0.5 worker queue, error handling.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_events.retry_count IS 
            'Number of times processing has been retried. INVARIANT: analytics_important. Purpose: Track retry attempts for failed events. Data class: Non-PII. Required for: B0.5 retry logic, dead event handling.'
    """)
    
    # Add comments on indexes
    op.execute("""
        COMMENT ON INDEX idx_events_idempotency IS 
            'Ensures idempotency_key uniqueness for deduplication. Purpose: Prevent duplicate event ingestion. Required for: B0.4 ingestion.'
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_events_tenant_timestamp IS 
            'Optimizes tenant-scoped time-series queries. Purpose: Enable fast event retrieval by tenant and time. Required for: B2.1 attribution models.'
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_events_processing_status IS 
            'Partial index for pending event queue. Purpose: Enable fast worker queue queries. Required for: B0.5 worker queue.'
    """)


def downgrade() -> None:
    """
    Remove canonical columns and restore composite idempotency indexes.
    
    WARNING: This will drop columns and all data in them.
    """
    
    # Restore old composite indexes
    op.execute("""
        CREATE UNIQUE INDEX idx_attribution_events_tenant_external_event_id 
        ON attribution_events (tenant_id, external_event_id) 
        WHERE external_event_id IS NOT NULL
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX idx_attribution_events_tenant_correlation_id 
        ON attribution_events (tenant_id, correlation_id) 
        WHERE correlation_id IS NOT NULL AND external_event_id IS NULL
    """)
    
    # Drop canonical indexes
    op.execute("DROP INDEX IF EXISTS idx_events_processing_status")
    op.execute("DROP INDEX IF EXISTS idx_events_tenant_timestamp")
    op.execute("DROP INDEX IF EXISTS idx_events_idempotency")
    
    # Drop constraints
    op.execute("ALTER TABLE attribution_events DROP CONSTRAINT IF EXISTS ck_attribution_events_retry_count_positive")
    op.execute("ALTER TABLE attribution_events DROP CONSTRAINT IF EXISTS ck_attribution_events_processing_status_valid")
    
    # Restore session_id to nullable
    op.execute("ALTER TABLE attribution_events ALTER COLUMN session_id DROP NOT NULL")
    
    # Drop columns
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS retry_count")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS processing_status")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS processed_at")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS event_timestamp")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS conversion_value_cents")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS campaign_id")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS channel")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS event_type")
    op.execute("ALTER TABLE attribution_events DROP COLUMN IF EXISTS idempotency_key")



"""Realign revenue_ledger table with canonical schema

Revision ID: 202511151430
Revises: 202511151420
Create Date: 2025-11-15 14:30:00.000000

Phase 7 of B0.3 Schema Realignment Plan

This migration adds 9 BLOCKING columns required for revenue state machine:
1. transaction_id - Unique identifier from payment processor (NOT NULL UNIQUE)
2. order_id - Order identifier for transaction tracking
3. state - Current state (authorized, captured, refunded, chargeback)
4. previous_state - Previous state for audit trail
5. amount_cents - Transaction amount in original currency
6. currency - ISO 4217 currency code (NOT NULL)
7. verification_source - Source that verified this entry (NOT NULL)
8. verification_timestamp - When verification occurred (NOT NULL)
9. metadata - JSONB for FX rates and processor details

Additionally:
- Adds UNIQUE constraint on transaction_id
- Adds CHECK constraint on state enum
- Creates index on state for query performance
- Backfills from existing revenue_cents/is_verified/verified_at columns

These changes are BLOCKING for:
- B2.2 Webhook Idempotency (requires transaction_id)
- B2.3 Currency Conversion (requires currency, metadata)
- B2.4 Refund Tracking (requires state machine)

Exit Gates:
- Migration applies cleanly
- All 9 columns exist with correct types
- transaction_id UNIQUE constraint enforced
- state CHECK constraint enforced (reject 'invalid_state')
- Cannot insert NULL transaction_id, state, amount_cents, currency

References:
- Architecture Guide §3.1 (Revenue Ledger Table)
- db/schema/canonical_schema.sql (lines 137-183)
- db/schema/schema_gap_catalogue.md (Table 4, BLOCKING gaps)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151430'
down_revision: Union[str, None] = '202511151420'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Realign revenue_ledger table with canonical schema.
    
    Implementation strategy:
    1. Add all columns as nullable first
    2. Backfill from existing columns (revenue_cents, is_verified, verified_at)
    3. Set NOT NULL constraints for required columns
    4. Add UNIQUE constraint on transaction_id
    5. Add CHECK constraint on state enum
    6. Create indexes
    7. Add comments with INVARIANT tags
    """
    
    # ========================================================================
    # Step 1: Add new columns as nullable
    # ========================================================================
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN transaction_id VARCHAR(255)
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN order_id VARCHAR(255)
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN state VARCHAR(50)
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN previous_state VARCHAR(50)
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN amount_cents INTEGER
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN currency VARCHAR(3) DEFAULT 'USD'
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN verification_source VARCHAR(50)
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN verification_timestamp TIMESTAMPTZ
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD COLUMN metadata JSONB
    """)
    
    # ========================================================================
    # Step 2: Backfill data from existing columns
    # ========================================================================
    
    # Backfill transaction_id (generate from id if no external ID exists)
    op.execute("""
        UPDATE revenue_ledger 
        SET transaction_id = 'legacy_' || id::text
        WHERE transaction_id IS NULL
    """)
    
    # Backfill amount_cents from revenue_cents
    op.execute("""
        UPDATE revenue_ledger 
        SET amount_cents = revenue_cents
        WHERE amount_cents IS NULL AND revenue_cents IS NOT NULL
    """)
    
    # Backfill state from is_verified flag
    op.execute("""
        UPDATE revenue_ledger 
        SET state = CASE 
            WHEN is_verified = TRUE THEN 'captured'
            ELSE 'authorized'
        END
        WHERE state IS NULL
    """)
    
    # Backfill verification_source for legacy data
    op.execute("""
        UPDATE revenue_ledger 
        SET verification_source = 'legacy_migration'
        WHERE verification_source IS NULL
    """)
    
    # Backfill verification_timestamp from verified_at (or created_at as fallback)
    op.execute("""
        UPDATE revenue_ledger 
        SET verification_timestamp = COALESCE(verified_at, created_at, now())
        WHERE verification_timestamp IS NULL
    """)
    
    # Set default currency to USD
    op.execute("""
        UPDATE revenue_ledger 
        SET currency = 'USD'
        WHERE currency IS NULL
    """)
    
    # ========================================================================
    # Step 3: Set NOT NULL constraints for required columns
    # ========================================================================
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ALTER COLUMN transaction_id SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ALTER COLUMN state SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ALTER COLUMN amount_cents SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ALTER COLUMN currency SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ALTER COLUMN verification_source SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ALTER COLUMN verification_timestamp SET NOT NULL
    """)
    
    # ========================================================================
    # Step 4: Add UNIQUE constraint on transaction_id
    # ========================================================================
    
    op.execute("""
        CREATE UNIQUE INDEX idx_revenue_ledger_transaction_id 
        ON revenue_ledger (transaction_id)
    """)
    
    # ========================================================================
    # Step 5: Add CHECK constraint on state enum
    # ========================================================================
    
    op.execute("""
        ALTER TABLE revenue_ledger 
        ADD CONSTRAINT ck_revenue_ledger_state_valid 
        CHECK (state IN ('authorized', 'captured', 'refunded', 'chargeback'))
    """)
    
    # ========================================================================
    # Step 6: Create indexes
    # ========================================================================
    
    op.execute("""
        CREATE INDEX idx_revenue_ledger_state 
        ON revenue_ledger (state)
    """)
    
    op.execute("""
        CREATE INDEX idx_revenue_ledger_tenant_state 
        ON revenue_ledger (tenant_id, state, created_at DESC)
    """)
    
    # ========================================================================
    # Step 7: Add comments with INVARIANT tags
    # ========================================================================
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.transaction_id IS 
            'Unique identifier for the financial transaction from payment processor (e.g., Stripe payment intent ID). INVARIANT: financial_critical. Purpose: Enable webhook idempotency and transaction deduplication. Data class: Non-PII. Required for: B2.2 webhook processing, transaction tracking. Must be unique.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.order_id IS 
            'Order identifier associated with the transaction. INVARIANT: financial_critical. Purpose: Link revenue to orders for reconciliation. Data class: Non-PII. Required for: B2.4 order-level revenue tracking.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.state IS 
            'Current state of the revenue transaction (authorized, captured, refunded, chargeback). INVARIANT: financial_critical. Purpose: Track revenue lifecycle and support refund processing. Data class: Non-PII. Required for: B2.4 refund tracking, state machine enforcement. Must be valid enum value.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.previous_state IS 
            'Previous state of the revenue transaction for audit trail. INVARIANT: financial_critical. Purpose: Enable state transition tracking and audit. Data class: Non-PII. Required for: B2.4 revenue state audit trail.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.amount_cents IS 
            'Transaction amount in cents in its original currency. INVARIANT: financial_critical. Purpose: Store exact transaction amount without loss of precision. Data class: Non-PII. Required for: B2.2 revenue tracking, B2.3 currency conversion. Must not be NULL.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.currency IS 
            'ISO 4217 currency code of the transaction (e.g., USD, EUR, GBP). INVARIANT: financial_critical. Purpose: Support multi-currency revenue tracking and conversion. Data class: Non-PII. Required for: B2.3 currency conversion, international revenue reporting. Must not be NULL.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.verification_source IS 
            'Source that verified this ledger entry (e.g., Stripe, manual, reconciliation_run). INVARIANT: financial_critical. Purpose: Track verification provenance for audit. Data class: Non-PII. Required for: B2.4 reconciliation audit trail. Must not be NULL.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.verification_timestamp IS 
            'Timestamp when the ledger entry was verified. INVARIANT: financial_critical. Purpose: Track verification timing for audit and SLA monitoring. Data class: Non-PII. Required for: B2.4 reconciliation audit trail, verification latency tracking. Must not be NULL.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.metadata IS 
            'Additional metadata for the ledger entry (e.g., FX rates, processor details, refund reason). INVARIANT: analytics_important. Purpose: Store supplementary transaction data. Data class: Non-PII (may contain processor IDs). Required for: B2.3 FX rate tracking, B2.4 refund analysis.'
    """)
    
    # Add comments on constraints
    op.execute("""
        COMMENT ON CONSTRAINT ck_revenue_ledger_state_valid ON revenue_ledger IS 
            'Ensures state is a valid enum value. Purpose: Enforce state machine integrity. Required for: B2.4 refund tracking state machine.'
    """)
    
    # Add comments on indexes
    op.execute("""
        COMMENT ON INDEX idx_revenue_ledger_transaction_id IS 
            'Ensures transaction_id uniqueness for webhook idempotency. Purpose: Prevent duplicate ledger entries for the same transaction. Required for: B2.2 webhook deduplication.'
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_revenue_ledger_state IS 
            'Optimizes queries by state for refund processing. Purpose: Enable fast lookups of transactions by state. Required for: B2.4 refund processing queries.'
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_revenue_ledger_tenant_state IS 
            'Optimizes tenant-scoped state queries with temporal ordering. Purpose: Enable fast tenant revenue reporting by state. Required for: B2.4 tenant dashboards.'
    """)


def downgrade() -> None:
    """
    Remove canonical columns and constraints.
    
    WARNING: This will drop columns and all data in them.
    """
    
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_revenue_ledger_tenant_state")
    op.execute("DROP INDEX IF EXISTS idx_revenue_ledger_state")
    op.execute("DROP INDEX IF EXISTS idx_revenue_ledger_transaction_id")
    
    # Drop constraints
    op.execute("ALTER TABLE revenue_ledger DROP CONSTRAINT IF EXISTS ck_revenue_ledger_state_valid")
    
    # Drop columns
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS metadata")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS verification_timestamp")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS verification_source")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS amount_cents")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS previous_state")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS state")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS order_id")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS transaction_id")



"""Add statistical metadata fields to attribution_allocations

Revision ID: 202511151420
Revises: 202511151410
Create Date: 2025-11-15 14:20:00.000000

Phase 6 of B0.3 Schema Realignment Plan

This migration adds 9 HIGH-severity columns required for statistical attribution:
1. model_type - Attribution model classification (last_touch, linear, etc.)
2. confidence_score - Statistical confidence (0.0-1.0) with CHECK constraint
3. credible_interval_lower_cents - Bayesian credible interval lower bound
4. credible_interval_upper_cents - Bayesian credible interval upper bound
5. convergence_r_hat - R-hat statistic for MCMC convergence diagnostics
6. effective_sample_size - Effective sample size for MCMC diagnostics
7. verified - Verification flag for reconciliation
8. verification_source - Source of verification (manual, reconciliation_run, etc.)
9. verification_timestamp - When verification occurred

Additionally:
- Adds CHECK constraint for confidence_score bounds
- Creates canonical index with INCLUDE clause for performance
- Renames channel to channel_code for consistency (if not already done)

These changes are required for:
- B2.1 Statistical Attribution Models (Bayesian inference)
- B2.4 Revenue Verification & Reconciliation

Exit Gates:
- Migration applies cleanly
- All 9 columns exist with correct types
- confidence_score CHECK constraint enforced (reject 1.5, accept 0.5)
- Canonical index with INCLUDE clause exists

References:
- Architecture Guide §3.1 (Attribution Allocations Table)
- db/schema/canonical_schema.sql (lines 89-136)
- db/schema/schema_gap_catalogue.md (Table 3, HIGH gaps)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151420'
down_revision: Union[str, None] = '202511151410'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Add statistical metadata and verification columns to attribution_allocations.
    
    Implementation strategy:
    1. Add all columns as nullable first
    2. Backfill with default values where appropriate
    3. Set NOT NULL constraints for required columns
    4. Add CHECK constraint for confidence_score
    5. Create canonical index with INCLUDE clause
    6. Add comments with INVARIANT tags
    """
    
    # ========================================================================
    # Step 1: Add new columns as nullable
    # ========================================================================
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN model_type VARCHAR(50)
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN confidence_score NUMERIC(4,3)
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN credible_interval_lower_cents INTEGER
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN credible_interval_upper_cents INTEGER
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN convergence_r_hat NUMERIC(5,4)
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN effective_sample_size INTEGER
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN verified BOOLEAN DEFAULT FALSE
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN verification_source VARCHAR(50)
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD COLUMN verification_timestamp TIMESTAMPTZ
    """)
    
    # ========================================================================
    # Step 2: Backfill with defaults for required columns
    # ========================================================================
    
    # Set default model_type for existing rows
    op.execute("""
        UPDATE attribution_allocations 
        SET model_type = 'unknown'
        WHERE model_type IS NULL
    """)
    
    # Set default confidence_score from allocation_ratio if it exists
    op.execute("""
        UPDATE attribution_allocations 
        SET confidence_score = LEAST(COALESCE(allocation_ratio, 0.0), 1.0)::NUMERIC(4,3)
        WHERE confidence_score IS NULL
    """)
    
    # Set default verified to FALSE
    op.execute("""
        UPDATE attribution_allocations 
        SET verified = FALSE
        WHERE verified IS NULL
    """)
    
    # ========================================================================
    # Step 3: Set NOT NULL constraints for required columns
    # ========================================================================
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ALTER COLUMN model_type SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ALTER COLUMN confidence_score SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ALTER COLUMN verified SET NOT NULL
    """)
    
    # ========================================================================
    # Step 4: Add CHECK constraint for confidence_score
    # ========================================================================
    
    op.execute("""
        ALTER TABLE attribution_allocations 
        ADD CONSTRAINT ck_allocations_confidence_score 
        CHECK (confidence_score >= 0 AND confidence_score <= 1)
    """)
    
    # ========================================================================
    # Step 5: Create canonical index with INCLUDE clause
    # ========================================================================
    
    # Drop existing index if it exists (from earlier migrations)
    op.execute("""
        DROP INDEX IF EXISTS idx_allocations_channel_performance
    """)
    
    # Create new index with INCLUDE clause
    op.execute("""
        CREATE INDEX idx_allocations_channel_performance 
        ON attribution_allocations (tenant_id, channel_code, created_at DESC) 
        INCLUDE (allocated_revenue_cents, confidence_score)
    """)
    
    # ========================================================================
    # Step 6: Add comments with INVARIANT tags
    # ========================================================================
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.model_type IS 
            'Type of attribution model used (e.g., last_touch, linear, bayesian). INVARIANT: analytics_important. Purpose: Identify attribution methodology for model comparison. Data class: Non-PII. Required for: B2.1 attribution model selection and analysis.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.confidence_score IS 
            'Statistical confidence score of the allocation (0.0 to 1.0). INVARIANT: analytics_important. Purpose: Quantify uncertainty in attribution. Data class: Non-PII. Required for: B2.1 Bayesian attribution, confidence-weighted reporting. Must be between 0 and 1.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.credible_interval_lower_cents IS 
            'Lower bound of the credible interval for allocated revenue (Bayesian). INVARIANT: analytics_important. Purpose: Quantify uncertainty bounds for revenue allocation. Data class: Non-PII. Required for: B2.1 Bayesian attribution uncertainty quantification.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.credible_interval_upper_cents IS 
            'Upper bound of the credible interval for allocated revenue (Bayesian). INVARIANT: analytics_important. Purpose: Quantify uncertainty bounds for revenue allocation. Data class: Non-PII. Required for: B2.1 Bayesian attribution uncertainty quantification.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.convergence_r_hat IS 
            'R-hat statistic for MCMC convergence diagnostics (Gelman-Rubin). INVARIANT: analytics_important. Purpose: Validate MCMC chain convergence. Data class: Non-PII. Required for: B2.1 Bayesian model quality assurance. Values near 1.0 indicate convergence.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.effective_sample_size IS 
            'Effective sample size for MCMC diagnostics. INVARIANT: analytics_important. Purpose: Assess MCMC sampling efficiency. Data class: Non-PII. Required for: B2.1 Bayesian model quality assurance.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.verified IS 
            'Whether the allocation has been verified against ground truth. INVARIANT: analytics_important. Purpose: Flag allocations that have been reconciled. Data class: Non-PII. Required for: B2.4 revenue verification and reconciliation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.verification_source IS 
            'Source of verification (e.g., manual, reconciliation_run, stripe_webhook). INVARIANT: analytics_important. Purpose: Track verification provenance. Data class: Non-PII. Required for: B2.4 reconciliation audit trail.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.verification_timestamp IS 
            'Timestamp when the allocation was verified. INVARIANT: analytics_important. Purpose: Track verification timing. Data class: Non-PII. Required for: B2.4 reconciliation audit trail.'
    """)
    
    # Add comment on constraint
    op.execute("""
        COMMENT ON CONSTRAINT ck_allocations_confidence_score ON attribution_allocations IS 
            'Ensures confidence_score is between 0 and 1. Purpose: Enforce valid probability bounds. Required for: B2.1 statistical attribution.'
    """)
    
    # Add comment on index
    op.execute("""
        COMMENT ON INDEX idx_allocations_channel_performance IS 
            'Optimizes channel performance queries with included columns. Purpose: Enable fast channel-level analytics without table lookups. Required for: B2.1 attribution reporting.'
    """)


def downgrade() -> None:
    """
    Remove statistical metadata and verification columns.
    
    WARNING: This will drop columns and all data in them.
    """
    
    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_allocations_channel_performance")
    
    # Drop constraint
    op.execute("ALTER TABLE attribution_allocations DROP CONSTRAINT IF EXISTS ck_allocations_confidence_score")
    
    # Drop columns
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS verification_timestamp")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS verification_source")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS verified")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS effective_sample_size")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS convergence_r_hat")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS credible_interval_upper_cents")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS credible_interval_lower_cents")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS confidence_score")
    op.execute("ALTER TABLE attribution_allocations DROP COLUMN IF EXISTS model_type")



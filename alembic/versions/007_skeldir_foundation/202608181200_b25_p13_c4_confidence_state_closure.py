"""B2.5-P13 C4 confidence state and temporal authority closure.

Revision ID: 202608181200
Revises: 202608131200
Create Date: 2026-08-18 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202608181200"
down_revision = "202608131200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical rows intentionally remain unmodified. NOT VALID preserves those
    # honest unknowns while enforcing the complete state machine on every new or
    # subsequently updated row.
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            ADD COLUMN confidence_evidence_snapshot_hash varchar(64),
            ADD COLUMN source_read_started_at timestamptz,
            ADD COLUMN source_read_completed_at timestamptz;

        ALTER TABLE public.bayesian_model_fits
            ADD CONSTRAINT ck_bayesian_model_fits_confidence_evidence_hash_sha256
                CHECK (
                    confidence_evidence_snapshot_hash IS NULL
                    OR confidence_evidence_snapshot_hash ~ '^[a-f0-9]{64}$'
                ) NOT VALID,
            ADD CONSTRAINT ck_bayesian_model_fits_source_read_pair_order
                CHECK (
                    (source_read_started_at IS NULL AND source_read_completed_at IS NULL)
                    OR (
                        source_read_started_at IS NOT NULL
                        AND source_read_completed_at IS NOT NULL
                        AND source_read_completed_at >= source_read_started_at
                    )
                ) NOT VALID,
            ADD CONSTRAINT ck_bayesian_model_fits_confidence_evidence_tuple
                CHECK (
                    (
                        confidence_evidence_snapshot_hash IS NULL
                        AND confidence_deterministic_revenue_minor IS NULL
                        AND confidence_deterministic_row_count IS NULL
                        AND confidence_match_verdict_count IS NULL
                        AND confidence_currency_count IS NULL
                    )
                    OR (
                        confidence_evidence_snapshot_hash IS NOT NULL
                        AND confidence_deterministic_revenue_minor IS NOT NULL
                        AND confidence_deterministic_row_count IS NOT NULL
                        AND confidence_match_verdict_count IS NOT NULL
                        AND confidence_currency_count IS NOT NULL
                        AND confidence_evidence_snapshot_hash = source_snapshot_hash
                    )
                ) NOT VALID,
            ADD CONSTRAINT ck_bayesian_model_fits_confidence_classification_state
                CHECK (
                    (
                        confidence_bucket IS NULL
                        AND confidence_bucket_reason IS NULL
                        AND confidence_policy_version IS NULL
                        AND confidence_semantics_version IS NULL
                        AND confidence_classified_at IS NULL
                    )
                    OR (
                        confidence_bucket IS NOT NULL
                        AND confidence_bucket_reason IS NOT NULL
                        AND confidence_policy_version = 'b24-p10-confidence-policy-v1'
                        AND confidence_semantics_version = 'b24-p10-confidence-semantics-v1'
                        AND confidence_classified_at IS NOT NULL
                    )
                ) NOT VALID,
            ADD CONSTRAINT ck_bayesian_model_fits_available_confidence_complete
                CHECK (
                    confidence_bucket NOT IN ('low', 'medium', 'high')
                    OR (
                        status = 'succeeded'
                        AND data_completeness_status = 'complete'
                        AND fallback_applied = false
                        AND diagnostic_status = 'passed'
                        AND credible_interval_status = 'available'
                        AND artifact_ref IS NOT NULL
                        AND artifact_hash IS NOT NULL
                        AND confidence_evidence_snapshot_hash = source_snapshot_hash
                        AND confidence_deterministic_revenue_minor IS NOT NULL
                        AND confidence_deterministic_row_count IS NOT NULL
                        AND confidence_match_verdict_count IS NOT NULL
                        AND confidence_currency_count IS NOT NULL
                        AND confidence_currency_count <= 1
                        AND confidence_classified_at IS NOT NULL
                        AND confidence_classified_at >= source_read_completed_at
                        AND source_read_started_at IS NOT NULL
                        AND source_read_completed_at IS NOT NULL
                        AND source_read_completed_at >= source_read_started_at
                        AND (
                            (confidence_bucket = 'high' AND confidence_bucket_reason = 'narrow_interval')
                            OR (confidence_bucket = 'medium' AND confidence_bucket_reason = 'moderate_interval')
                            OR (confidence_bucket = 'low' AND confidence_bucket_reason = 'wide_interval')
                        )
                    )
                ) NOT VALID;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_available_confidence_complete, -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_confidence_classification_state, -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_confidence_evidence_tuple, -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_source_read_pair_order, -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_confidence_evidence_hash_sha256, -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
            DROP COLUMN IF EXISTS source_read_completed_at, -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
            DROP COLUMN IF EXISTS source_read_started_at, -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
            DROP COLUMN IF EXISTS confidence_evidence_snapshot_hash; -- # CI:DESTRUCTIVE_OK - Downgrade rollback; see ADR-016.
        """
    )

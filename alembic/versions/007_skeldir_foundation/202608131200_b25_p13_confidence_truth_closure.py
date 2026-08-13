"""B2.5-P13 confidence truth and durable freshness authority.

Revision ID: 202608131200
Revises: 202608081200
Create Date: 2026-08-13 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202608131200"
down_revision = "202608081200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deliberately do not backfill fit classifications. Historical fits were not
    # classified from frozen P6 context, and bayesian_model_fits is protected by
    # the B2.4 dispatch fence. NULL remains an honest, fail-closed
    # persisted_classification_missing state until a new governed fit is produced.
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            ADD COLUMN confidence_semantics_version varchar(64),
            ADD COLUMN confidence_deterministic_revenue_minor bigint,
            ADD COLUMN confidence_deterministic_row_count bigint,
            ADD COLUMN confidence_match_verdict_count bigint,
            ADD COLUMN confidence_currency_count integer,
            ADD COLUMN confidence_classified_at timestamptz;

        ALTER TABLE public.bayesian_model_fits
            ADD CONSTRAINT ck_bayesian_model_fits_confidence_row_count_nonnegative
                CHECK (
                    confidence_deterministic_row_count IS NULL
                    OR confidence_deterministic_row_count >= 0
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_confidence_verdict_count_nonnegative
                CHECK (
                    confidence_match_verdict_count IS NULL
                    OR confidence_match_verdict_count >= 0
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_confidence_currency_count_nonnegative
                CHECK (
                    confidence_currency_count IS NULL
                    OR confidence_currency_count >= 0
                );

        CREATE INDEX idx_b24_dirty_events_confidence_freshness
            ON public.b24_dirty_events (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                observed_at,
                source_snapshot_hash
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS public.idx_b24_dirty_events_confidence_freshness;
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_confidence_currency_count_nonnegative,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_confidence_verdict_count_nonnegative,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_confidence_row_count_nonnegative,
            DROP COLUMN IF EXISTS confidence_classified_at,
            DROP COLUMN IF EXISTS confidence_currency_count,
            DROP COLUMN IF EXISTS confidence_match_verdict_count,
            DROP COLUMN IF EXISTS confidence_deterministic_row_count,
            DROP COLUMN IF EXISTS confidence_deterministic_revenue_minor,
            DROP COLUMN IF EXISTS confidence_semantics_version;
        """
    )

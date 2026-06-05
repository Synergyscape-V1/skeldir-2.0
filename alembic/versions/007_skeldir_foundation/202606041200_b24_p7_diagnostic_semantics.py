"""B2.4-P7 diagnostic semantics and interval conditionality.

Revision ID: 202606041200
Revises: 202606031200
Create Date: 2026-06-04 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202606041200"
down_revision: Union[str, None] = "202606031200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            ADD COLUMN IF NOT EXISTS hdi_lower double precision,
            ADD COLUMN IF NOT EXISTS hdi_upper double precision,
            ADD COLUMN IF NOT EXISTS interval_shape jsonb NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS interval_element_count integer,
            ADD COLUMN IF NOT EXISTS interval_summary_bytes integer,
            ADD COLUMN IF NOT EXISTS diagnostic_status character varying(32)
                NOT NULL DEFAULT 'not_computed',
            ADD COLUMN IF NOT EXISTS diagnostic_failure_reason character varying(64),
            ADD COLUMN IF NOT EXISTS diagnostic_policy_version character varying(64),
            ADD COLUMN IF NOT EXISTS diagnostic_target_filter_version character varying(64),
            ADD COLUMN IF NOT EXISTS interval_policy_version character varying(64),
            ADD COLUMN IF NOT EXISTS diagnostics_computed_at timestamp with time zone
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_hdi_bounds_pair_order,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_interval_shape_array,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_interval_element_count_non_negative,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_interval_summary_bytes_non_negative,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_diagnostic_status,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_diagnostic_failure_reason,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_passed_has_no_diagnostic_failure,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_available_interval_requires_passed_diagnostics
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            ADD CONSTRAINT ck_bayesian_model_fits_hdi_bounds_pair_order
                CHECK (
                    (hdi_lower IS NULL AND hdi_upper IS NULL)
                    OR (
                        hdi_lower IS NOT NULL
                        AND hdi_upper IS NOT NULL
                        AND hdi_lower <= hdi_upper
                    )
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_interval_shape_array
                CHECK (jsonb_typeof(interval_shape) = 'array'),
            ADD CONSTRAINT ck_bayesian_model_fits_interval_element_count_non_negative
                CHECK (
                    interval_element_count IS NULL
                    OR interval_element_count >= 0
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_interval_summary_bytes_non_negative
                CHECK (
                    interval_summary_bytes IS NULL
                    OR interval_summary_bytes >= 0
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_diagnostic_status
                CHECK (
                    diagnostic_status IN (
                        'not_computed',
                        'passed',
                        'failed',
                        'error',
                        'unavailable'
                    )
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_diagnostic_failure_reason
                CHECK (
                    diagnostic_failure_reason IS NULL
                    OR diagnostic_failure_reason IN (
                        'bad_rhat',
                        'low_ess',
                        'divergence',
                        'nonfinite_diagnostic',
                        'invalid_diagnostic_summary',
                        'diagnostic_scope_too_large',
                        'interval_dimension_exceeded',
                        'interval_payload_too_large',
                        'diagnostics_failed',
                        'diagnostics_memory_exceeded',
                        'diagnostics_timeout',
                        'skipped_non_sampled'
                    )
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_passed_has_no_diagnostic_failure
                CHECK (
                    (
                        diagnostic_status = 'passed'
                        AND diagnostic_failure_reason IS NULL
                    )
                    OR diagnostic_status <> 'passed'
                ),
            ADD CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagnostics
                CHECK (
                    credible_interval_status <> 'available'
                    OR (
                        diagnostic_status = 'passed'
                        AND fallback_applied = false
                        AND r_hat_max IS NOT NULL
                        AND r_hat_max <= 1.01
                        AND ess_min IS NOT NULL
                        AND ess_min >= 400
                        AND divergence_count = 0
                        AND hdi_lower IS NOT NULL
                        AND hdi_upper IS NOT NULL
                        AND interval_element_count IS NOT NULL
                        AND interval_element_count > 0
                        AND diagnostic_policy_version IS NOT NULL
                        AND diagnostic_target_filter_version IS NOT NULL
                        AND interval_policy_version IS NOT NULL
                    )
                )
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.bayesian_model_fits.diagnostic_status IS
            'B2.4-P7 diagnostic validity state. Orthogonal to fit execution lifecycle status.';
        COMMENT ON COLUMN public.bayesian_model_fits.diagnostic_failure_reason IS
            'B2.4-P7 governed diagnostic or interval conditionality failure reason.';
        COMMENT ON COLUMN public.bayesian_model_fits.interval_shape IS
            'B2.4-P7 bounded interval shape metadata only; no posterior samples or trace arrays.';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_available_interval_requires_passed_diagnostics,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_passed_has_no_diagnostic_failure,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_diagnostic_failure_reason,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_diagnostic_status,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_interval_summary_bytes_non_negative,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_interval_element_count_non_negative,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_interval_shape_array,
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_hdi_bounds_pair_order
        """
    )
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS diagnostics_computed_at")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS interval_policy_version")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS diagnostic_target_filter_version")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS diagnostic_policy_version")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS diagnostic_failure_reason")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS diagnostic_status")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS interval_summary_bytes")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS interval_element_count")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS interval_shape")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS hdi_upper")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.
    op.execute("ALTER TABLE public.bayesian_model_fits DROP COLUMN IF EXISTS hdi_lower")  # CI:DESTRUCTIVE_OK - downgrade removes additive B2.4-P7 fields only.

"""B2.4-P6 fit execution intermediate states.

Revision ID: 202606021200
Revises: 202605281200
Create Date: 2026-06-02 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision: str = "202606021200"
down_revision: str | tuple[str, ...] | None = "202605281200"
branch_labels: tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


UP_STATUS = (
    "'pending', 'queued', 'running', 'persist_pending', "
    "'sampled_unvalidated', 'diagnostics_pending', 'succeeded', 'failed', "
    "'timeout', 'worker_lost', 'fallback_only', 'cancelled'"
)
DOWN_STATUS = (
    "'pending', 'queued', 'running', 'succeeded', 'failed', "
    "'timeout', 'worker_lost', 'fallback_only', 'cancelled'"
)

UP_FALLBACK_REASON = (
    "'source_window_empty', 'insufficient_data', 'insufficient_privacy_cohort', "
    "'input_too_large', 'feature_width_exceeded', 'source_window_too_large', "
    "'memory_bound_exceeded', 'graph_complexity_exceeded', "
    "'parameter_count_exceeded', 'hierarchy_width_exceeded', "
    "'compilation_memory_bound_exceeded', "
    "'cardinality_authority_missing', 'cardinality_authority_stale', "
    "'cardinality_authority_mismatch', "
    "'cardinality_authority_timeout', "
    "'cardinality_authority_build_failed', "
    "'source_profile_unavailable', "
    "'source_snapshot_mismatch', 'transport_rejected', "
    "'result_too_large', 'sampler_health_failed', "
    "'model_memory_exceeded', 'graph_compile_memory_exceeded', "
    "'policy_rejected', "
    "'timeout', 'worker_failure', 'no_convergence', "
    "'resource_bound_exceeded', 'source_unavailable', 'duplicate_fit_suppressed', "
    "'artifact_unavailable', 'storage_quota_exceeded'"
)
DOWN_FALLBACK_REASON = (
    "'source_window_empty', 'insufficient_data', 'insufficient_privacy_cohort', "
    "'input_too_large', 'feature_width_exceeded', 'source_window_too_large', "
    "'memory_bound_exceeded', 'graph_complexity_exceeded', "
    "'parameter_count_exceeded', 'hierarchy_width_exceeded', "
    "'compilation_memory_bound_exceeded', "
    "'cardinality_authority_missing', 'cardinality_authority_stale', "
    "'cardinality_authority_mismatch', "
    "'cardinality_authority_timeout', "
    "'cardinality_authority_build_failed', "
    "'source_profile_unavailable', "
    "'timeout', 'worker_failure', 'no_convergence', "
    "'resource_bound_exceeded', 'source_unavailable', 'duplicate_fit_suppressed', "
    "'artifact_unavailable', 'storage_quota_exceeded'"
)


def _replace_status_constraint(status_values: str) -> None:
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_status"
    )
    op.execute(
        f"""
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT ck_bayesian_model_fits_status
        CHECK (status IN ({status_values}))
        """
    )


def _replace_fallback_reason_constraint(reason_values: str) -> None:
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_fallback_reason"
    )
    op.execute(
        f"""
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT ck_bayesian_model_fits_fallback_reason
        CHECK (fallback_reason IS NULL OR fallback_reason IN ({reason_values}))
        """
    )


def upgrade() -> None:
    _replace_status_constraint(UP_STATUS)
    _replace_fallback_reason_constraint(UP_FALLBACK_REASON)


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.bayesian_model_fits
        SET status = 'failed',
            fallback_applied = true,
            fallback_reason = COALESCE(fallback_reason, 'worker_failure'),
            credible_interval_status = 'not_available',
            updated_at = now()
        WHERE status IN (
            'persist_pending',
            'sampled_unvalidated',
            'diagnostics_pending'
        )
        """
    )
    op.execute(
        """
        UPDATE public.bayesian_model_fits
        SET fallback_reason = 'worker_failure',
            updated_at = now()
        WHERE fallback_reason IN (
            'source_snapshot_mismatch',
            'transport_rejected',
            'result_too_large',
            'sampler_health_failed',
            'model_memory_exceeded',
            'graph_compile_memory_exceeded',
            'policy_rejected'
        )
        """
    )
    _replace_status_constraint(DOWN_STATUS)
    _replace_fallback_reason_constraint(DOWN_FALLBACK_REASON)

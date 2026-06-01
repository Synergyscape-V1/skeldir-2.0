"""B2.4-P5 runtime terminal statuses.

Revision ID: 202605281200
Revises: 202605271200
Create Date: 2026-05-28 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision: str = "202605281200"
down_revision: str | tuple[str, ...] | None = "202605271200"
branch_labels: tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


UP_STATUS = (
    "'pending', 'queued', 'running', 'succeeded', 'failed', "
    "'timeout', 'worker_lost', 'fallback_only', 'cancelled'"
)
DOWN_STATUS = (
    "'pending', 'queued', 'running', 'succeeded', 'failed', "
    "'fallback_only', 'cancelled'"
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


def upgrade() -> None:
    _replace_status_constraint(UP_STATUS)


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.bayesian_model_fits
        SET status = 'failed',
            fallback_applied = true,
            fallback_reason = COALESCE(fallback_reason, 'worker_failure'),
            credible_interval_status = 'not_available',
            updated_at = now()
        WHERE status IN ('timeout', 'worker_lost')
        """
    )
    _replace_status_constraint(DOWN_STATUS)

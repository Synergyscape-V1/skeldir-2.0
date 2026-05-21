"""B2.4-P2 sparse/source-window fallback reason constraints.

Revision ID: 202605211430
Revises: 202605211200
Create Date: 2026-05-21 14:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605211430"
down_revision: Union[str, None] = "202605211200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

P2_FALLBACK_REASONS = (
    "source_window_empty",
    "insufficient_data",
    "insufficient_privacy_cohort",
    "timeout",
    "worker_failure",
    "no_convergence",
    "resource_bound_exceeded",
    "source_unavailable",
    "duplicate_fit_suppressed",
    "artifact_unavailable",
    "storage_quota_exceeded",
)

P1_FALLBACK_REASONS = tuple(
    reason
    for reason in P2_FALLBACK_REASONS
    if reason not in {"source_window_empty", "insufficient_privacy_cohort"}
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _replace_constraint(values: tuple[str, ...]) -> None:
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_fallback_reason"
    )
    op.execute(
        f"""
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT ck_bayesian_model_fits_fallback_reason
        CHECK (
            fallback_reason IS NULL
            OR fallback_reason IN ({_quoted(values)})
        )
        """
    )


def upgrade() -> None:
    _replace_constraint(P2_FALLBACK_REASONS)


def downgrade() -> None:
    _replace_constraint(P1_FALLBACK_REASONS)

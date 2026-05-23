"""Add B2.4-P4 resource and graph fallback reasons.

Revision ID: 202605231200
Revises: 202605221430
Create Date: 2026-05-23 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605231200"
down_revision: Union[str, None] = "202605221430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

P4_FALLBACK_REASONS = (
    "source_window_empty",
    "insufficient_data",
    "insufficient_privacy_cohort",
    "input_too_large",
    "feature_width_exceeded",
    "source_window_too_large",
    "memory_bound_exceeded",
    "graph_complexity_exceeded",
    "parameter_count_exceeded",
    "hierarchy_width_exceeded",
    "compilation_memory_bound_exceeded",
    "timeout",
    "worker_failure",
    "no_convergence",
    "resource_bound_exceeded",
    "source_unavailable",
    "duplicate_fit_suppressed",
    "artifact_unavailable",
    "storage_quota_exceeded",
)

P3_FALLBACK_REASONS = tuple(
    reason
    for reason in P4_FALLBACK_REASONS
    if reason
    not in {
        "input_too_large",
        "feature_width_exceeded",
        "source_window_too_large",
        "memory_bound_exceeded",
        "graph_complexity_exceeded",
        "parameter_count_exceeded",
        "hierarchy_width_exceeded",
        "compilation_memory_bound_exceeded",
    }
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
    _replace_constraint(P4_FALLBACK_REASONS)


def downgrade() -> None:
    _replace_constraint(P3_FALLBACK_REASONS)

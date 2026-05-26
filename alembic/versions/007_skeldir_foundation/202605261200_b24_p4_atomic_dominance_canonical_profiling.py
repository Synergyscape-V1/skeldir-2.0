"""Enforce B2.4-P4 canonical profiling and atomic dominance statuses.

Revision ID: 202605261200
Revises: 202605251800
Create Date: 2026-05-26 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605261200"
down_revision: Union[str, None] = "202605251800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ACTIVE_EXECUTION_STATUSES = (
    "profiling",
    "profile_passed",
    "profile_rejected",
    "profile_superseded",
    "profile_timeout",
    "profile_failed",
    "claiming",
    "dispatch_pending",
    "dispatched",
    "running",
    "cancel_requested",
    "succeeded",
    "failed",
    "fallback_only",
    "cancelled",
    "stale_recovered",
)

LEGACY_ACTIVE_EXECUTION_STATUSES = (
    "claiming",
    "dispatch_pending",
    "dispatched",
    "running",
    "cancel_requested",
    "succeeded",
    "failed",
    "fallback_only",
    "cancelled",
    "stale_recovered",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _replace_active_execution_constraints(
    statuses: tuple[str, ...], *, allow_profile_without_fit: bool
) -> None:
    op.execute(
        "ALTER TABLE public.b24_active_execution_leases "
        "DROP CONSTRAINT IF EXISTS ck_b24_active_execution_status"
    )
    op.execute(
        "ALTER TABLE public.b24_active_execution_leases "
        "DROP CONSTRAINT IF EXISTS ck_b24_active_execution_active_fit_required"
    )
    op.execute(
        f"""
        ALTER TABLE public.b24_active_execution_leases
        ADD CONSTRAINT ck_b24_active_execution_status
        CHECK (status IN ({_quoted(statuses)}))
        """
    )
    fitless_statuses = (
        "'claiming'"
        if not allow_profile_without_fit
        else """
        'claiming',
        'profiling',
        'profile_passed',
        'profile_rejected',
        'profile_superseded',
        'profile_timeout',
        'profile_failed'
        """
    )
    op.execute(
        f"""
        ALTER TABLE public.b24_active_execution_leases
        ADD CONSTRAINT ck_b24_active_execution_active_fit_required
        CHECK (
            status IN ({fitless_statuses})
            OR fit_id IS NOT NULL
        )
        """
    )


def upgrade() -> None:
    _replace_active_execution_constraints(
        ACTIVE_EXECUTION_STATUSES, allow_profile_without_fit=True
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_active_execution_canonical_profiling
            ON public.b24_active_execution_leases (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                status,
                leased_until
            )
            WHERE status = 'profiling'
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_active_execution_canonical_profiling"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 index.
    _replace_active_execution_constraints(
        LEGACY_ACTIVE_EXECUTION_STATUSES, allow_profile_without_fit=False
    )

"""B2.3-P3 verdict persistence authority substrate correction.

Revision ID: 202605051200
Revises: 202604301030
Create Date: 2026-05-05 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605051200"
down_revision: Union[str, None] = "202604301030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.b23_revenue_events
            ADD COLUMN IF NOT EXISTS is_gross_capture_correction boolean NOT NULL DEFAULT false
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_revenue_events.is_gross_capture_correction IS
            'True only when the event corrects original gross capture authority; false for normal refunds, returns, chargebacks, and net adjustments.'
        """
    )

    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_ratio_consistency"  # CI:DESTRUCTIVE_OK - See B2.3-P3 evidence pack for authorized gross-basis correction.
    )
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_amount_consistency"  # CI:DESTRUCTIVE_OK - See B2.3-P3 evidence pack for authorized gross-basis correction.
    )

    op.execute(
        """
        UPDATE public.b23_match_verdicts
        SET
            discrepancy_amount_minor = abs(
                canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor
            ),
            discrepancy_ratio_bps = CASE
                WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                ELSE (
                    abs(canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor)
                    * 10000
                ) / canonical_expected_gross_amount_minor
            END,
            discrepancy_band = CASE
                WHEN abs(canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor) = 0 THEN 'exact'
                WHEN (
                    CASE
                        WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                        ELSE (
                            abs(canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor)
                            * 10000
                        ) / canonical_expected_gross_amount_minor
                    END
                ) <= 200 THEN 'within_tolerance'
                WHEN (
                    CASE
                        WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                        ELSE (
                            abs(canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor)
                            * 10000
                        ) / canonical_expected_gross_amount_minor
                    END
                ) <= 1000 THEN 'over_tolerance'
                ELSE 'severe_gap'
            END
        """
    )

    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_amount_consistency
            CHECK (
                discrepancy_amount_minor = abs(
                    canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor
                )
            )
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_ratio_consistency
            CHECK (
                discrepancy_ratio_bps = CASE
                    WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                    ELSE (
                        discrepancy_amount_minor * 10000
                    ) / canonical_expected_gross_amount_minor
                END
            )
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.discrepancy_amount_minor IS
            'Absolute attribution discrepancy in minor units, computed from expected gross versus captured gross only.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.discrepancy_ratio_bps IS
            'Absolute attribution discrepancy ratio in basis points, computed from expected gross versus captured gross only.'
        """
    )

    op.execute(
        """
        WITH ranked_open_exceptions AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY tenant_id, match_verdict_id
                    ORDER BY raised_at DESC, id DESC
                ) AS open_rank
            FROM public.b23_exception_records
            WHERE status IN ('open', 'acknowledged')
        )
        UPDATE public.b23_exception_records target
        SET
            status = 'resolved',
            resolution_code = 'system_duplicate_exception_closed',
            resolution_notes = 'Duplicate open exception closed before P3 idempotency index creation.',
            resolved_at = now(),
            updated_at = now()
        FROM ranked_open_exceptions ranked
        WHERE target.id = ranked.id
          AND ranked.open_rank > 1
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_b23_exception_records_one_open_per_verdict
            ON public.b23_exception_records (
                tenant_id,
                match_verdict_id
            )
            WHERE status IN ('open', 'acknowledged')
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_revenue_events_tenant_gross_capture_correction
            ON public.b23_revenue_events (
                tenant_id,
                match_verdict_id,
                is_gross_capture_correction,
                event_occurred_at DESC
            )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS public.uq_b23_exception_records_one_open_per_verdict"
    )
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b23_revenue_events_tenant_gross_capture_correction"
    )
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_ratio_consistency"  # CI:DESTRUCTIVE_OK - See B2.3-P3 evidence pack for authorized gross-basis correction.
    )
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_amount_consistency"  # CI:DESTRUCTIVE_OK - See B2.3-P3 evidence pack for authorized gross-basis correction.
    )
    op.execute(
        """
        UPDATE public.b23_match_verdicts
        SET
            discrepancy_amount_minor = abs(
                canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor
            ),
            discrepancy_ratio_bps = CASE
                WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                ELSE (
                    abs(canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor)
                    * 10000
                ) / canonical_expected_gross_amount_minor
            END
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_amount_consistency
            CHECK (
                discrepancy_amount_minor = abs(
                    canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor
                )
            )
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_ratio_consistency
            CHECK (
                discrepancy_ratio_bps = CASE
                    WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                    ELSE ((discrepancy_amount_minor * 10000) / canonical_expected_gross_amount_minor)
                END
            )
        """
    )
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP COLUMN IF EXISTS is_gross_capture_correction"  # CI:DESTRUCTIVE_OK - See B2.3-P3 evidence pack for authorized downgrade symmetry.
    )

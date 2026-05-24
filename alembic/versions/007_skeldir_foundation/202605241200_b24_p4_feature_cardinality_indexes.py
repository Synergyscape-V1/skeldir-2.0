"""Add B2.4-P4 feature cardinality indexes.

Revision ID: 202605241200
Revises: 202605231200
Create Date: 2026-05-24 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202605241200"
down_revision = "202605231200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p4_attribution_events_campaign_cardinality
            ON public.attribution_events (tenant_id, campaign_id, occurred_at, id)
            WHERE processing_status = 'processed'
              AND event_type = 'conversion'
              AND campaign_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p4_match_verdicts_provider_cardinality
            ON public.b23_match_verdicts (tenant_id, provider, last_transition_at, id)
            WHERE status IN ('matched_confirmed', 'adjusted')
              AND provider IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p4_revenue_events_provider_cardinality
            ON public.b23_revenue_events (tenant_id, provider, event_occurred_at, id)
            WHERE event_type IN (
                'payment_capture',
                'partial_refund',
                'full_refund',
                'chargeback_lost',
                'chargeback_won',
                'reversal'
            )
              AND provider IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p4_revenue_events_provider_cardinality"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 cardinality index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p4_match_verdicts_provider_cardinality"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 cardinality index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p4_attribution_events_campaign_cardinality"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 cardinality index.

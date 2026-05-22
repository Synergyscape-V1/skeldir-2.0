"""Add B2.4-P2 source stream safety indexes.

These partial indexes support the exact tenant/window/order predicates used by
the B2.4-P2 deterministic source snapshot streams.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605221200"
down_revision: Union[str, None] = "202605211430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p2_attribution_events_source_stream
            ON public.attribution_events (tenant_id, occurred_at ASC, id ASC)
            WHERE processing_status = 'processed'
              AND event_type = 'conversion'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p2_attribution_allocations_source_stream
            ON public.attribution_allocations (tenant_id, created_at ASC, id ASC)
            WHERE verified = true
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p2_match_verdicts_source_stream
            ON public.b23_match_verdicts (tenant_id, last_transition_at ASC, id ASC)
            WHERE status IN ('matched_confirmed', 'adjusted')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p2_revenue_events_source_stream
            ON public.b23_revenue_events (tenant_id, event_occurred_at ASC, id ASC)
            WHERE event_type IN (
                'payment_capture',
                'partial_refund',
                'full_refund',
                'chargeback_lost',
                'chargeback_won',
                'reversal'
            )
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p2_revenue_events_source_stream"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P2 source stream index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p2_match_verdicts_source_stream"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P2 source stream index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p2_attribution_allocations_source_stream"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P2 source stream index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p2_attribution_events_source_stream"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P2 source stream index.

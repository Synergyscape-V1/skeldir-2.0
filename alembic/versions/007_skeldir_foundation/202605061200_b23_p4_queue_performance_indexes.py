"""B2.3-P4 queue performance and telemetry access paths.

Revision ID: 202605061200
Revises: 202605051200
Create Date: 2026-05-06 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605061200"
down_revision: Union[str, None] = "202605051200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_p4_attribution_order_ref_expr
            ON public.attribution_events (
                tenant_id,
                ((raw_payload ->> 'order_id')),
                occurred_at DESC
            )
            WHERE raw_payload ? 'order_id'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_p4_verdict_webhook_identity
            ON public.b23_match_verdicts (
                tenant_id,
                webhook_ingress_identity_id
            )
            WHERE webhook_ingress_identity_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_p4_attribution_event_tenant_id
            ON public.attribution_events (
                tenant_id,
                id
            )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_p4_webhook_identity_claim
            ON public.webhook_ingress_identities (
                tenant_id,
                verified_commerce_ingress_state,
                event_timestamp ASC,
                id
            )
            WHERE verified_commerce_ingress_state = 'authenticity_verified'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_p4_match_rate_tenant_transition_status
            ON public.b23_match_verdicts (
                tenant_id,
                last_transition_at DESC,
                status
            )
            WHERE status IN (
                'matched_provisional',
                'matched_confirmed',
                'adjusted',
                'unmatched'
            )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_p4_webhook_failure_tenant_platform_time
            ON public.b23_webhook_ingestion_logs (
                tenant_id,
                provider,
                received_at DESC
            )
            WHERE ingestion_status = 'failed'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_p4_worker_dlq_open_status_failed_at
            ON public.worker_failed_jobs (
                status,
                tenant_id,
                failed_at DESC
            )
            WHERE status IN ('pending', 'in_progress')
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT ON TABLE public.attribution_events TO app_user;
                GRANT SELECT, INSERT, UPDATE ON TABLE public.attribution_commerce_identities TO app_user;
                GRANT SELECT, UPDATE ON TABLE public.webhook_ingress_identities TO app_user;
                GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_verdicts TO app_user;
                GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_exception_records TO app_user;
                GRANT SELECT ON TABLE public.b23_webhook_ingestion_logs TO app_user;
                GRANT SELECT ON TABLE public.worker_failed_jobs TO app_user;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.idx_b23_p4_worker_dlq_open_status_failed_at")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_p4_webhook_failure_tenant_platform_time")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_p4_match_rate_tenant_transition_status")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_p4_webhook_identity_claim")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_p4_attribution_event_tenant_id")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_p4_verdict_webhook_identity")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_p4_attribution_order_ref_expr")

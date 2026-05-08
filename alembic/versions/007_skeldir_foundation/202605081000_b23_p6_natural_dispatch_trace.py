"""B2.3-P6 natural webhook dispatch trace.

Revision ID: 202605081000
Revises: 202605071200
Create Date: 2026-05-08 10:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605081000"
down_revision: Union[str, None] = "202605071200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.b23_match_task_dispatches (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            webhook_ingress_identity_id uuid NOT NULL REFERENCES public.webhook_ingress_identities(id) ON DELETE CASCADE,
            task_id character varying(155) NOT NULL,
            task_name character varying(255) NOT NULL,
            queue character varying(100) NOT NULL,
            routing_key character varying(255) NOT NULL,
            correlation_id uuid NOT NULL,
            provider character varying(32) NOT NULL,
            provider_native_event_reference character varying(255) NOT NULL,
            provider_native_commerce_reference character varying(255) NOT NULL,
            normalized_commerce_reference_value character varying(255) NOT NULL,
            status character varying(32) DEFAULT 'dispatched' NOT NULL,
            dispatched_at timestamp with time zone DEFAULT now() NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b23_match_task_dispatches_pkey PRIMARY KEY (id),
            CONSTRAINT uq_b23_match_task_dispatches_tenant_ingress UNIQUE (tenant_id, webhook_ingress_identity_id),
            CONSTRAINT uq_b23_match_task_dispatches_task_id UNIQUE (task_id),
            CONSTRAINT ck_b23_match_task_dispatches_queue CHECK (queue = 'b23_match_engine'),
            CONSTRAINT ck_b23_match_task_dispatches_status CHECK (status IN ('dispatched'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_match_task_dispatches_tenant_reference
            ON public.b23_match_task_dispatches (
                tenant_id,
                provider,
                provider_native_event_reference,
                normalized_commerce_reference_value
            )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_match_task_dispatches_ingress
            ON public.b23_match_task_dispatches (webhook_ingress_identity_id)
        """
    )
    op.execute("ALTER TABLE public.b23_match_task_dispatches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.b23_match_task_dispatches FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b23_match_task_dispatches
        ON public.b23_match_task_dispatches
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b23_match_task_dispatches IS
            'B2.3-P6 durable lineage trace linking verified webhook ingress identities to naturally emitted b23_match_engine tasks.'
        """
    )
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_task_dispatches TO app_user
        """
    )
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_task_dispatches TO app_rw
        """
    )
    op.execute(
        """
        GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ro
        """
    )


def downgrade() -> None:
    op.execute("REVOKE ALL ON TABLE public.b23_match_task_dispatches FROM app_ro")
    op.execute("REVOKE ALL ON TABLE public.b23_match_task_dispatches FROM app_rw")
    op.execute("REVOKE ALL ON TABLE public.b23_match_task_dispatches FROM app_user")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_match_task_dispatches ON public.b23_match_task_dispatches"  # CI:DESTRUCTIVE_OK - reversible rollback for B2.3-P6 natural dispatch trace.
    )
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b23_match_task_dispatches_ingress"  # CI:DESTRUCTIVE_OK - reversible rollback for B2.3-P6 natural dispatch trace.
    )
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b23_match_task_dispatches_tenant_reference"  # CI:DESTRUCTIVE_OK - reversible rollback for B2.3-P6 natural dispatch trace.
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b23_match_task_dispatches"  # CI:DESTRUCTIVE_OK - reversible rollback for B2.3-P6 natural dispatch trace.
    )

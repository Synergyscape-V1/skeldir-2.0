"""B1.4-P3 terminal corrective: ephemeral order/click write-time resolution substrate.

Revision ID: 202603211810
Revises: 202603191730
Create Date: 2026-03-21 18:10:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603211810"
down_revision: Union[str, None] = "202603191730"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _grant_if_role_exists(role: str, grant_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{grant_sql}';
            END IF;
        END
        $$;
        """
    )


def _revoke_if_role_exists(role: str, revoke_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{revoke_sql}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.ephemeral_order_resolution (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            order_id text NOT NULL,
            session_id uuid NOT NULL,
            observed_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            source text NOT NULL DEFAULT 'ingestion_runtime',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_ephemeral_order_resolution_tenant_order
                UNIQUE (tenant_id, order_id),
            CONSTRAINT ck_ephemeral_order_resolution_expires_after_observed
                CHECK (expires_at > observed_at),
            CONSTRAINT ck_ephemeral_order_resolution_max_24h
                CHECK (expires_at <= observed_at + interval '24 hours')
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.ephemeral_order_resolution IS
            'B1.4-P3 terminal corrective ephemeral substrate: 24h order->session continuity cache for write-time session-local rebinding.'
        """
    )
    op.execute(
        """
        CREATE INDEX idx_ephemeral_order_resolution_tenant_expires
            ON public.ephemeral_order_resolution (tenant_id, expires_at ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_ephemeral_order_resolution_tenant_order
            ON public.ephemeral_order_resolution (tenant_id, order_id)
        """
    )

    op.execute(
        """
        CREATE TABLE public.ephemeral_click_resolution (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            click_id text NOT NULL,
            session_id uuid NOT NULL,
            observed_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            source text NOT NULL DEFAULT 'ingestion_runtime',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_ephemeral_click_resolution_tenant_click
                UNIQUE (tenant_id, click_id),
            CONSTRAINT ck_ephemeral_click_resolution_expires_after_observed
                CHECK (expires_at > observed_at),
            CONSTRAINT ck_ephemeral_click_resolution_max_24h
                CHECK (expires_at <= observed_at + interval '24 hours')
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.ephemeral_click_resolution IS
            'B1.4-P3 terminal corrective ephemeral substrate: 24h click->session continuity cache for write-time deterministic rebinding without durable click persistence.'
        """
    )
    op.execute(
        """
        CREATE INDEX idx_ephemeral_click_resolution_tenant_expires
            ON public.ephemeral_click_resolution (tenant_id, expires_at ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_ephemeral_click_resolution_tenant_click
            ON public.ephemeral_click_resolution (tenant_id, click_id)
        """
    )

    op.execute("ALTER TABLE public.ephemeral_order_resolution ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.ephemeral_order_resolution FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_ephemeral_order_resolution ON public.ephemeral_order_resolution"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_ephemeral_order_resolution ON public.ephemeral_order_resolution
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    op.execute("ALTER TABLE public.ephemeral_click_resolution ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.ephemeral_click_resolution FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_ephemeral_click_resolution ON public.ephemeral_click_resolution"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_ephemeral_click_resolution ON public.ephemeral_click_resolution
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.ephemeral_order_resolution TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.ephemeral_order_resolution TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.ephemeral_order_resolution TO app_ro",
    )
    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.ephemeral_click_resolution TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.ephemeral_click_resolution TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.ephemeral_click_resolution TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.ephemeral_click_resolution FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.ephemeral_click_resolution FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.ephemeral_click_resolution FROM app_user",
    )
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.ephemeral_order_resolution FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.ephemeral_order_resolution FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.ephemeral_order_resolution FROM app_user",
    )

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_ephemeral_click_resolution ON public.ephemeral_click_resolution"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_ephemeral_order_resolution ON public.ephemeral_order_resolution"
    )
    op.execute("DROP INDEX IF EXISTS public.idx_ephemeral_click_resolution_tenant_click")
    op.execute("DROP INDEX IF EXISTS public.idx_ephemeral_click_resolution_tenant_expires")
    op.execute("DROP TABLE IF EXISTS public.ephemeral_click_resolution")  # CI:DESTRUCTIVE_OK - rollback for B1.4-P3 terminal ephemeral click substrate
    op.execute("DROP INDEX IF EXISTS public.idx_ephemeral_order_resolution_tenant_order")
    op.execute("DROP INDEX IF EXISTS public.idx_ephemeral_order_resolution_tenant_expires")
    op.execute("DROP TABLE IF EXISTS public.ephemeral_order_resolution")  # CI:DESTRUCTIVE_OK - rollback for B1.4-P3 terminal ephemeral order substrate

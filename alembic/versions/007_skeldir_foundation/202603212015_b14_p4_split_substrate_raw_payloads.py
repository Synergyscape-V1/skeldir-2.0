"""B1.4-P4 split substrate: raw payload offloading for retention/deletion semantics.

Revision ID: 202603212015
Revises: 202603211810
Create Date: 2026-03-21 20:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603212015"
down_revision: Union[str, None] = "202603211810"
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
    # Convert session authority FK to a deferrable NO ACTION variant so privacy
    # erasure can perform delete+placeholder reinsertion in a single transaction
    # without mutating immutable attribution_events rows.
    op.execute(
        """
        ALTER TABLE public.attribution_events
            DROP CONSTRAINT IF EXISTS fk_attribution_events_session_authority
        """
    )
    op.execute(
        """
        ALTER TABLE public.attribution_events
            ADD CONSTRAINT fk_attribution_events_session_authority
            FOREIGN KEY (tenant_id, session_id)
            REFERENCES public.session_authority(tenant_id, session_id)
            ON DELETE NO ACTION
            DEFERRABLE INITIALLY DEFERRED
        """
    )

    op.execute(
        """
        CREATE TABLE public.raw_event_payloads (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            event_id uuid NOT NULL REFERENCES public.attribution_events(id) ON DELETE CASCADE,
            payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            ip_address varchar(64),
            user_agent varchar(1024),
            raw_headers jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_raw_event_payloads_tenant_event UNIQUE (tenant_id, event_id)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.raw_event_payloads IS
            'B1.4-P4 privacy-expirable raw telemetry substrate linked to immutable attribution_events ledger rows.'
        """
    )
    op.execute(
        """
        CREATE INDEX idx_raw_event_payloads_tenant_created
            ON public.raw_event_payloads (tenant_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_raw_event_payloads_event_id
            ON public.raw_event_payloads (event_id)
        """
    )

    op.execute("ALTER TABLE public.raw_event_payloads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.raw_event_payloads FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_raw_event_payloads ON public.raw_event_payloads"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_raw_event_payloads ON public.raw_event_payloads
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    # Backfill current durable raw payload envelopes into the dedicated expirable substrate.
    op.execute(
        """
        INSERT INTO public.raw_event_payloads (
            id,
            tenant_id,
            event_id,
            payload_json,
            ip_address,
            user_agent,
            raw_headers,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            e.tenant_id,
            e.id,
            COALESCE(e.raw_payload, '{}'::jsonb),
            NULL,
            NULL,
            NULL,
            e.created_at,
            e.updated_at
        FROM public.attribution_events e
        WHERE NOT EXISTS (
            SELECT 1
            FROM public.raw_event_payloads rep
            WHERE rep.event_id = e.id
              AND rep.tenant_id = e.tenant_id
        )
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, DELETE ON TABLE public.raw_event_payloads TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, DELETE ON TABLE public.raw_event_payloads TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.raw_event_payloads TO app_ro",
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.attribution_events
            DROP CONSTRAINT IF EXISTS fk_attribution_events_session_authority
        """
    )
    op.execute(
        """
        ALTER TABLE public.attribution_events
            ADD CONSTRAINT fk_attribution_events_session_authority
            FOREIGN KEY (tenant_id, session_id)
            REFERENCES public.session_authority(tenant_id, session_id)
            ON DELETE RESTRICT
        """
    )

    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.raw_event_payloads FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.raw_event_payloads FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.raw_event_payloads FROM app_user",
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_raw_event_payloads ON public.raw_event_payloads"
    )
    op.execute("DROP INDEX IF EXISTS public.idx_raw_event_payloads_event_id")
    op.execute("DROP INDEX IF EXISTS public.idx_raw_event_payloads_tenant_created")
    op.execute("DROP TABLE IF EXISTS public.raw_event_payloads")  # CI:DESTRUCTIVE_OK - rollback for B1.4-P4 split substrate table

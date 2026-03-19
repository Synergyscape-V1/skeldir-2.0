"""B1.4-P2: session authority substrate and event-session binding.

Revision ID: 202603191730
Revises: 202603181930
Create Date: 2026-03-19 17:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603191730"
down_revision: Union[str, None] = "202603181930"
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
        CREATE TABLE public.session_authority (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            session_id uuid NOT NULL,
            issued_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            invalidated_at timestamptz NULL,
            invalidation_reason text NULL,
            issued_by text NOT NULL DEFAULT 'ingestion_runtime',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_session_authority_tenant_session_id
                UNIQUE (tenant_id, session_id),
            CONSTRAINT ck_session_authority_expires_after_issued
                CHECK (expires_at > issued_at),
            CONSTRAINT ck_session_authority_max_24h
                CHECK (expires_at <= issued_at + interval '24 hours'),
            CONSTRAINT ck_session_authority_invalidation_after_issued
                CHECK (invalidated_at IS NULL OR invalidated_at >= issued_at)
        )
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.session_authority IS
            'B1.4-P2 authoritative tenant-scoped session substrate. Enforces bounded (<=24h) session lifecycle and stale-session invalidation.'
        """
    )

    op.execute(
        """
        CREATE INDEX idx_session_authority_tenant_expires
            ON public.session_authority (tenant_id, expires_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_session_authority_tenant_last_seen
            ON public.session_authority (tenant_id, last_seen_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_session_authority_active
            ON public.session_authority (tenant_id, session_id, expires_at DESC)
            WHERE invalidated_at IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO public.session_authority
        (
            tenant_id,
            session_id,
            issued_at,
            expires_at,
            last_seen_at,
            invalidated_at,
            invalidation_reason,
            issued_by,
            created_at,
            updated_at
        )
        SELECT
            seed.tenant_id,
            seed.session_id,
            now(),
            now() + interval '24 hours',
            now(),
            NULL,
            NULL,
            'migration_backfill',
            now(),
            now()
        FROM (
            SELECT DISTINCT tenant_id, session_id
            FROM public.attribution_events
            WHERE session_id IS NOT NULL
        ) AS seed
        ON CONFLICT (tenant_id, session_id) DO NOTHING
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_bind_session_authority_from_event()
        RETURNS trigger AS $$
        DECLARE
            authority_now timestamptz;
        BEGIN
            authority_now := now();
            IF NEW.session_id IS NULL THEN
                NEW.session_id := gen_random_uuid();
            END IF;

            INSERT INTO public.session_authority
            (
                tenant_id,
                session_id,
                issued_at,
                expires_at,
                last_seen_at,
                invalidated_at,
                invalidation_reason,
                issued_by,
                created_at,
                updated_at
            )
            VALUES
            (
                NEW.tenant_id,
                NEW.session_id,
                authority_now,
                authority_now + interval '24 hours',
                authority_now,
                NULL,
                NULL,
                'attribution_event_insert',
                authority_now,
                authority_now
            )
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET
                last_seen_at = GREATEST(public.session_authority.last_seen_at, EXCLUDED.last_seen_at),
                updated_at = EXCLUDED.updated_at;

            IF EXISTS (
                SELECT 1
                FROM public.session_authority sa
                WHERE sa.tenant_id = NEW.tenant_id
                  AND sa.session_id = NEW.session_id
                  AND (sa.invalidated_at IS NOT NULL OR sa.expires_at <= authority_now)
            ) THEN
                RAISE EXCEPTION
                    'session authority violation: stale or invalidated session_id on attribution_events insert';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_bind_session_authority_from_event ON public.attribution_events
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_bind_session_authority_from_event
            BEFORE INSERT ON public.attribution_events
            FOR EACH ROW
            EXECUTE FUNCTION public.fn_bind_session_authority_from_event()
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_attribution_events_session_authority'
            ) THEN
                ALTER TABLE ONLY public.attribution_events
                    ADD CONSTRAINT fk_attribution_events_session_authority
                    FOREIGN KEY (tenant_id, session_id)
                    REFERENCES public.session_authority(tenant_id, session_id)
                    ON DELETE RESTRICT;
            END IF;
        END
        $$;
        """
    )

    op.execute("ALTER TABLE public.session_authority ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.session_authority FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.session_authority")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON public.session_authority
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.session_authority TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.session_authority TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.session_authority TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.session_authority FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.session_authority FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.session_authority FROM app_user",
    )

    op.execute(
        """
        ALTER TABLE ONLY public.attribution_events
            DROP CONSTRAINT IF EXISTS fk_attribution_events_session_authority
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_bind_session_authority_from_event ON public.attribution_events
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.fn_bind_session_authority_from_event()")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.session_authority")
    op.execute("DROP INDEX IF EXISTS public.idx_session_authority_active")
    op.execute("DROP INDEX IF EXISTS public.idx_session_authority_tenant_last_seen")
    op.execute("DROP INDEX IF EXISTS public.idx_session_authority_tenant_expires")
    op.execute("DROP TABLE IF EXISTS public.session_authority")  # CI:DESTRUCTIVE_OK - rollback for B1.4-P2 session authority substrate

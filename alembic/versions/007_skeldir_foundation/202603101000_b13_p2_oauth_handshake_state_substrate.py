"""B1.3-P2: transient OAuth handshake state substrate.

Revision ID: 202603101000
Revises: 202603031300
Create Date: 2026-03-10 10:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603101000"
down_revision: Union[str, None] = "202603031300"
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
        CREATE TABLE public.oauth_handshake_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            platform text NOT NULL,
            state_nonce_hash text NOT NULL,
            encrypted_pkce_verifier bytea NULL,
            pkce_key_id text NULL,
            pkce_code_challenge text NULL,
            pkce_code_challenge_method text NULL,
            redirect_uri text NULL,
            provider_session_metadata jsonb NULL,
            status text NOT NULL DEFAULT 'pending',
            terminal_reason text NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz NULL,
            gc_after timestamptz NOT NULL,
            CONSTRAINT uq_oauth_handshake_sessions_tenant_state_hash
                UNIQUE (tenant_id, state_nonce_hash),
            CONSTRAINT ck_oauth_handshake_sessions_status_valid
                CHECK (status IN ('pending', 'consumed', 'expired', 'aborted')),
            CONSTRAINT ck_oauth_handshake_sessions_consumed_shape
                CHECK (
                    (status = 'consumed' AND consumed_at IS NOT NULL) OR
                    (status <> 'consumed' AND consumed_at IS NULL)
                ),
            CONSTRAINT ck_oauth_handshake_sessions_pkce_key_binding
                CHECK (
                    (encrypted_pkce_verifier IS NULL AND pkce_key_id IS NULL) OR
                    (encrypted_pkce_verifier IS NOT NULL AND pkce_key_id IS NOT NULL)
                ),
            CONSTRAINT ck_oauth_handshake_sessions_pkce_method
                CHECK (
                    pkce_code_challenge_method IS NULL OR
                    pkce_code_challenge_method IN ('S256', 'plain')
                ),
            CONSTRAINT ck_oauth_handshake_sessions_gc_after_window
                CHECK (gc_after >= created_at)
        )
        """
    )

    op.execute(
        """
        COMMENT ON TABLE public.oauth_handshake_sessions IS
            'Tenant-scoped transient OAuth handshake substrate. Stores short-lived state nonce hash and optional encrypted PKCE verifier only for authorize/callback lifecycle control.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.oauth_handshake_sessions.state_nonce_hash IS
            'SHA-256 hash of callback state nonce. Raw nonce is never persisted.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.oauth_handshake_sessions.gc_after IS
            'Timestamp after which terminal handshake rows are eligible for bounded garbage collection.'
        """
    )

    op.execute(
        """
        CREATE INDEX idx_oauth_handshake_sessions_tenant_platform_user_created
            ON public.oauth_handshake_sessions (tenant_id, platform, user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_oauth_handshake_sessions_tenant_state_lookup
            ON public.oauth_handshake_sessions (tenant_id, state_nonce_hash, status)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_oauth_handshake_sessions_expires_at
            ON public.oauth_handshake_sessions (expires_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_oauth_handshake_sessions_gc_after
            ON public.oauth_handshake_sessions (gc_after ASC)
        """
    )

    op.execute("ALTER TABLE public.oauth_handshake_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.oauth_handshake_sessions FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.oauth_handshake_sessions")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON public.oauth_handshake_sessions
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        COMMENT ON POLICY tenant_isolation_policy ON public.oauth_handshake_sessions IS
            'RLS policy enforcing tenant isolation for transient OAuth handshake state.'
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.oauth_handshake_sessions TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.oauth_handshake_sessions TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.oauth_handshake_sessions TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.oauth_handshake_sessions FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.oauth_handshake_sessions FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.oauth_handshake_sessions FROM app_user",
    )

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.oauth_handshake_sessions")
    op.execute("DROP INDEX IF EXISTS public.idx_oauth_handshake_sessions_gc_after")  # CI:DESTRUCTIVE_OK - rollback for transient handshake GC index
    op.execute("DROP INDEX IF EXISTS public.idx_oauth_handshake_sessions_expires_at")  # CI:DESTRUCTIVE_OK - rollback for transient handshake expiry index
    op.execute("DROP INDEX IF EXISTS public.idx_oauth_handshake_sessions_tenant_state_lookup")  # CI:DESTRUCTIVE_OK - rollback for transient handshake lookup index
    op.execute("DROP INDEX IF EXISTS public.idx_oauth_handshake_sessions_tenant_platform_user_created")  # CI:DESTRUCTIVE_OK - rollback for transient handshake access index
    op.execute("DROP TABLE IF EXISTS public.oauth_handshake_sessions")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P2 handshake substrate

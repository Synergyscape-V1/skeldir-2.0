"""B1.2-P4: token issuance + refresh lifecycle substrate.

Revision ID: 202603021130
Revises: 202603011930
Create Date: 2026-03-02 11:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603021130"
down_revision: Union[str, None] = "202603011930"
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
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS password_hash text")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth.lookup_user_auth_by_login_hash(p_login_identifier_hash text)
        RETURNS TABLE(user_id uuid, is_active boolean, auth_provider text, password_hash text)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
            SELECT
                u.id AS user_id,
                u.is_active,
                u.auth_provider,
                u.password_hash
            FROM public.users AS u
            WHERE u.login_identifier_hash = p_login_identifier_hash
            LIMIT 1
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION auth.lookup_user_auth_by_login_hash(text) FROM PUBLIC")
    _grant_if_role_exists("app_user", "GRANT EXECUTE ON FUNCTION auth.lookup_user_auth_by_login_hash(text) TO app_user")
    _grant_if_role_exists("app_rw", "GRANT EXECUTE ON FUNCTION auth.lookup_user_auth_by_login_hash(text) TO app_rw")
    _grant_if_role_exists("app_ro", "GRANT EXECUTE ON FUNCTION auth.lookup_user_auth_by_login_hash(text) TO app_ro")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.auth_refresh_tokens (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            family_id uuid NOT NULL,
            token_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            rotated_at timestamptz NULL,
            replaced_by_id uuid NULL REFERENCES public.auth_refresh_tokens(id) ON DELETE SET NULL,
            revoked_at timestamptz NULL,
            last_used_at timestamptz NULL,
            CONSTRAINT ck_auth_refresh_tokens_hash_not_empty
                CHECK (length(trim(token_hash)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_tenant_created_at
        ON public.auth_refresh_tokens (tenant_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_tenant_user_created_at
        ON public.auth_refresh_tokens (tenant_id, user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_family_created_at
        ON public.auth_refresh_tokens (family_id, created_at DESC)
        """
    )

    op.execute("ALTER TABLE public.auth_refresh_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.auth_refresh_tokens FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.auth_refresh_tokens")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON public.auth_refresh_tokens
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        COMMENT ON POLICY tenant_isolation_policy ON public.auth_refresh_tokens IS
            'RLS policy enforcing tenant isolation for refresh token lifecycle state.'
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.auth_refresh_tokens TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.auth_refresh_tokens TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.auth_refresh_tokens FROM app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.auth_refresh_tokens FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.auth_refresh_tokens FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.auth_refresh_tokens FROM app_user",
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.auth_refresh_tokens")
    op.execute("DROP INDEX IF EXISTS public.idx_auth_refresh_tokens_family_created_at")  # CI:DESTRUCTIVE_OK - rollback for B1.2-P4 substrate removal
    op.execute("DROP INDEX IF EXISTS public.idx_auth_refresh_tokens_tenant_user_created_at")  # CI:DESTRUCTIVE_OK - rollback for B1.2-P4 substrate removal
    op.execute("DROP INDEX IF EXISTS public.idx_auth_refresh_tokens_tenant_created_at")  # CI:DESTRUCTIVE_OK - rollback for B1.2-P4 substrate removal
    op.execute("DROP TABLE IF EXISTS public.auth_refresh_tokens")  # CI:DESTRUCTIVE_OK - rollback for B1.2-P4 substrate removal

    _revoke_if_role_exists(
        "app_ro",
        "REVOKE EXECUTE ON FUNCTION auth.lookup_user_auth_by_login_hash(text) FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE EXECUTE ON FUNCTION auth.lookup_user_auth_by_login_hash(text) FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE EXECUTE ON FUNCTION auth.lookup_user_auth_by_login_hash(text) FROM app_user",
    )
    op.execute("DROP FUNCTION IF EXISTS auth.lookup_user_auth_by_login_hash(text)")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth.lookup_user_by_login_hash(p_login_identifier_hash text)
        RETURNS TABLE(user_id uuid, is_active boolean, auth_provider text)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
            SELECT
                u.id AS user_id,
                u.is_active,
                u.auth_provider
            FROM public.users AS u
            WHERE u.login_identifier_hash = p_login_identifier_hash
            LIMIT 1
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION auth.lookup_user_by_login_hash(text) FROM PUBLIC")
    _grant_if_role_exists("app_user", "GRANT EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) TO app_user")
    _grant_if_role_exists("app_rw", "GRANT EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) TO app_rw")
    _grant_if_role_exists("app_ro", "GRANT EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) TO app_ro")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS password_hash")  # CI:DESTRUCTIVE_OK - rollback for B1.2-P4 users auth field

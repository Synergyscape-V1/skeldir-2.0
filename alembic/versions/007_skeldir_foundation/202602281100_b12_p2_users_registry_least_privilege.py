"""B1.2-P2 corrective: users registry least-privilege and tenantless lookup boundary.

Revision ID: 202602281100
Revises: 202602271430
Create Date: 2026-02-28 11:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202602281100"
down_revision: Union[str, None] = "202602271430"
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
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    # Eliminate direct users-table enumerability from broad runtime roles.
    _revoke_if_role_exists("app_ro", "REVOKE ALL ON TABLE public.users FROM app_ro")
    _revoke_if_role_exists("app_rw", "REVOKE ALL ON TABLE public.users FROM app_rw")
    _revoke_if_role_exists(
        "app_user", "REVOKE ALL ON TABLE public.users FROM app_user"
    )
    _grant_if_role_exists(
        "app_user", "GRANT SELECT, UPDATE ON TABLE public.users TO app_user"
    )

    op.execute("ALTER TABLE public.users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.users FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS users_self_select_policy ON public.users")
    op.execute("DROP POLICY IF EXISTS users_self_update_policy ON public.users")
    op.execute(
        """
        CREATE POLICY users_self_select_policy ON public.users
            FOR SELECT
            USING (id = current_setting('app.current_user_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY users_self_update_policy ON public.users
            FOR UPDATE
            USING (id = current_setting('app.current_user_id', true)::uuid)
            WITH CHECK (id = current_setting('app.current_user_id', true)::uuid)
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth.lookup_user_by_login_hash(login_identifier_hash text)
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
            WHERE u.login_identifier_hash = lookup_user_by_login_hash.login_identifier_hash
            LIMIT 1
        $$;
        """
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION auth.lookup_user_by_login_hash(text) FROM PUBLIC
        """
    )
    _grant_if_role_exists("app_user", "GRANT USAGE ON SCHEMA auth TO app_user")
    _grant_if_role_exists("app_rw", "GRANT USAGE ON SCHEMA auth TO app_rw")
    _grant_if_role_exists("app_ro", "GRANT USAGE ON SCHEMA auth TO app_ro")
    _grant_if_role_exists(
        "app_user",
        "GRANT EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE EXECUTE ON FUNCTION auth.lookup_user_by_login_hash(text) FROM app_user",
    )
    _revoke_if_role_exists("app_ro", "REVOKE USAGE ON SCHEMA auth FROM app_ro")
    _revoke_if_role_exists("app_rw", "REVOKE USAGE ON SCHEMA auth FROM app_rw")
    _revoke_if_role_exists("app_user", "REVOKE USAGE ON SCHEMA auth FROM app_user")

    op.execute("DROP FUNCTION IF EXISTS auth.lookup_user_by_login_hash(text)")
    op.execute("DROP POLICY IF EXISTS users_self_update_policy ON public.users")
    op.execute("DROP POLICY IF EXISTS users_self_select_policy ON public.users")
    op.execute("ALTER TABLE public.users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.users DISABLE ROW LEVEL SECURITY")

    _revoke_if_role_exists("app_ro", "REVOKE ALL ON TABLE public.users FROM app_ro")
    _revoke_if_role_exists("app_rw", "REVOKE ALL ON TABLE public.users FROM app_rw")
    _revoke_if_role_exists(
        "app_user", "REVOKE ALL ON TABLE public.users FROM app_user"
    )
    _grant_if_role_exists("app_user", "GRANT SELECT, INSERT, UPDATE ON TABLE public.users TO app_user")
    _grant_if_role_exists("app_rw", "GRANT SELECT, INSERT, UPDATE ON TABLE public.users TO app_rw")
    _grant_if_role_exists("app_ro", "GRANT SELECT ON TABLE public.users TO app_ro")

    op.execute("DROP SCHEMA IF EXISTS auth")

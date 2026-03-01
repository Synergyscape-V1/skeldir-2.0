"""B1.2-P2 corrective v4: harden lookup function execution context.

Revision ID: 202602282000
Revises: 202602281430
Create Date: 2026-02-28 20:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202602282000"
down_revision: Union[str, None] = "202602281430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auth_lookup_executor') THEN
                CREATE ROLE auth_lookup_executor NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT;
            ELSE
                ALTER ROLE auth_lookup_executor NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT;
            END IF;
        END
        $$;
        """
    )

    op.execute("REVOKE ALL ON TABLE public.users FROM auth_lookup_executor")
    op.execute("GRANT SELECT ON TABLE public.users TO auth_lookup_executor")

    op.execute("DROP POLICY IF EXISTS users_lookup_executor_select_policy ON public.users")
    op.execute(
        """
        CREATE POLICY users_lookup_executor_select_policy ON public.users
            FOR SELECT
            TO auth_lookup_executor
            USING (true)
        """
    )

    op.execute(
        """
        ALTER FUNCTION auth.lookup_user_by_login_hash(text)
            OWNER TO auth_lookup_executor
        """
    )
    op.execute(
        """
        ALTER FUNCTION auth.lookup_user_by_login_hash(text)
            SET row_security = on
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER FUNCTION auth.lookup_user_by_login_hash(text)
            RESET row_security
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            EXECUTE format(
                'ALTER FUNCTION auth.lookup_user_by_login_hash(text) OWNER TO %I',
                current_user
            );
        END
        $$;
        """
    )
    op.execute("DROP POLICY IF EXISTS users_lookup_executor_select_policy ON public.users")
    op.execute("REVOKE ALL ON TABLE public.users FROM auth_lookup_executor")

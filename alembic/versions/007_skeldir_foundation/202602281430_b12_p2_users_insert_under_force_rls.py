"""B1.2-P2 corrective v3: users INSERT viability under FORCE RLS.

Revision ID: 202602281430
Revises: 202602281100
Create Date: 2026-02-28 14:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202602281430"
down_revision: Union[str, None] = "202602281100"
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
    _grant_if_role_exists(
        "app_user",
        "GRANT INSERT ON TABLE public.users TO app_user",
    )

    op.execute("DROP POLICY IF EXISTS users_provision_insert_policy ON public.users")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                EXECUTE $sql$
                    CREATE POLICY users_provision_insert_policy ON public.users
                        FOR INSERT
                        TO app_user
                        WITH CHECK (
                            id IS NOT NULL
                            AND length(trim(login_identifier_hash)) > 0
                            AND auth_provider = ANY (
                                ARRAY[
                                    'password'::text,
                                    'oauth_google'::text,
                                    'oauth_microsoft'::text,
                                    'oauth_github'::text,
                                    'sso'::text
                                ]
                            )
                        )
                $sql$;
            ELSE
                EXECUTE $sql$
                    CREATE POLICY users_provision_insert_policy ON public.users
                        FOR INSERT
                        WITH CHECK (
                            id IS NOT NULL
                            AND length(trim(login_identifier_hash)) > 0
                            AND auth_provider = ANY (
                                ARRAY[
                                    'password'::text,
                                    'oauth_google'::text,
                                    'oauth_microsoft'::text,
                                    'oauth_github'::text,
                                    'sso'::text
                                ]
                            )
                        )
                $sql$;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS users_provision_insert_policy ON public.users")
    _revoke_if_role_exists(
        "app_user",
        "REVOKE INSERT ON TABLE public.users FROM app_user",
    )

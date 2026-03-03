"""B1.2-P5: denylist + tokens_invalid_before revocation substrate.

Revision ID: 202603031300
Revises: 202602141530
Create Date: 2026-03-03 13:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603031300"
down_revision: Union[str, None] = "202602141530"
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
        CREATE TABLE IF NOT EXISTS public.auth_access_token_denylist (
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            jti uuid NOT NULL,
            revoked_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            reason text NOT NULL DEFAULT 'logout',
            CONSTRAINT pk_auth_access_token_denylist PRIMARY KEY (tenant_id, user_id, jti),
            CONSTRAINT ck_auth_access_token_denylist_reason_not_empty
                CHECK (length(trim(reason)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_access_token_denylist_jti
            ON public.auth_access_token_denylist (jti)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_access_token_denylist_tenant_user_revoked_at
            ON public.auth_access_token_denylist (tenant_id, user_id, revoked_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_access_token_denylist_expires_at
            ON public.auth_access_token_denylist (expires_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.auth_user_token_cutoffs (
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            tokens_invalid_before timestamptz NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            updated_by_user_id uuid NULL,
            CONSTRAINT pk_auth_user_token_cutoffs PRIMARY KEY (tenant_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_auth_user_token_cutoffs_tenant_user
            ON public.auth_user_token_cutoffs (tenant_id, user_id)
        """
    )

    for table_name in ("auth_access_token_denylist", "auth_user_token_cutoffs"):
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON public.{table_name}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON public.{table_name}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.auth_access_token_denylist TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.auth_access_token_denylist TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.auth_access_token_denylist FROM app_ro",
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.auth_user_token_cutoffs TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.auth_user_token_cutoffs TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.auth_user_token_cutoffs FROM app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.auth_user_token_cutoffs FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.auth_user_token_cutoffs FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.auth_user_token_cutoffs FROM app_user",
    )
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.auth_access_token_denylist FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.auth_access_token_denylist FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.auth_access_token_denylist FROM app_user",
    )

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.auth_user_token_cutoffs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.auth_access_token_denylist")
    op.execute("DROP INDEX IF EXISTS public.idx_auth_user_token_cutoffs_tenant_user")  # CI:DESTRUCTIVE_OK - rollback of B1.2-P5 kill-switch substrate
    op.execute("DROP TABLE IF EXISTS public.auth_user_token_cutoffs")  # CI:DESTRUCTIVE_OK - rollback of B1.2-P5 kill-switch substrate
    op.execute("DROP INDEX IF EXISTS public.idx_auth_access_token_denylist_expires_at")  # CI:DESTRUCTIVE_OK - rollback of B1.2-P5 denylist substrate
    op.execute("DROP INDEX IF EXISTS public.idx_auth_access_token_denylist_tenant_user_revoked_at")  # CI:DESTRUCTIVE_OK - rollback of B1.2-P5 denylist substrate
    op.execute("DROP INDEX IF EXISTS public.idx_auth_access_token_denylist_jti")  # CI:DESTRUCTIVE_OK - rollback of B1.2-P5 denylist substrate
    op.execute("DROP TABLE IF EXISTS public.auth_access_token_denylist")  # CI:DESTRUCTIVE_OK - rollback of B1.2-P5 denylist substrate

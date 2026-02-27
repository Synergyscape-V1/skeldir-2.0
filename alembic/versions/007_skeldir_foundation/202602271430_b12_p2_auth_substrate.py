"""B1.2-P2: Privacy-safe auth substrate (users, memberships, roles).

Revision ID: 202602271430
Revises: 202602221700
Create Date: 2026-02-27 14:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202602271430"
down_revision: Union[str, None] = "202602221700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _grant_if_role_exists(role: str, privileges: str, table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'GRANT {privileges} ON TABLE {table_name} TO {role}';
            END IF;
        END
        $$;
        """
    )


def _revoke_if_role_exists(role: str, table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'REVOKE ALL ON TABLE {table_name} FROM {role}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            login_identifier_hash text NOT NULL UNIQUE,
            external_subject_hash text,
            auth_provider text NOT NULL DEFAULT 'password',
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_users_auth_provider_valid
                CHECK (auth_provider IN ('password', 'oauth_google', 'oauth_microsoft', 'oauth_github', 'sso')),
            CONSTRAINT ck_users_login_identifier_hash_not_empty
                CHECK (length(trim(login_identifier_hash)) > 0)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE public.roles (
            code text PRIMARY KEY,
            description text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_roles_code_lowercase CHECK (code = lower(code)),
            CONSTRAINT ck_roles_code_not_empty CHECK (length(trim(code)) > 0)
        );
        """
    )
    op.execute(
        """
        INSERT INTO public.roles (code, description)
        VALUES
            ('admin', 'Tenant administrator'),
            ('manager', 'Tenant manager'),
            ('viewer', 'Read-only tenant user')
        ON CONFLICT (code) DO UPDATE
            SET description = EXCLUDED.description;
        """
    )
    op.execute(
        """
        CREATE TABLE public.tenant_memberships (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            membership_status text NOT NULL DEFAULT 'active',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_tenant_memberships_tenant_user UNIQUE (tenant_id, user_id),
            CONSTRAINT uq_tenant_memberships_id_tenant UNIQUE (id, tenant_id),
            CONSTRAINT ck_tenant_memberships_status_valid
                CHECK (membership_status IN ('active', 'revoked'))
        );
        """
    )
    op.execute(
        """
        CREATE TABLE public.tenant_membership_roles (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            membership_id uuid NOT NULL,
            role_code text NOT NULL REFERENCES public.roles(code) ON DELETE RESTRICT,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_tenant_membership_roles_membership_tenant
                FOREIGN KEY (membership_id, tenant_id)
                REFERENCES public.tenant_memberships(id, tenant_id)
                ON DELETE CASCADE,
            CONSTRAINT uq_tenant_membership_roles_membership_role
                UNIQUE (membership_id, role_code)
        );
        """
    )

    op.execute(
        """
        CREATE INDEX idx_tenant_memberships_tenant_created_at
            ON public.tenant_memberships (tenant_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tenant_memberships_user_created_at
            ON public.tenant_memberships (user_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tenant_membership_roles_tenant_created_at
            ON public.tenant_membership_roles (tenant_id, created_at DESC);
        """
    )

    for table_name in ("tenant_memberships", "tenant_membership_roles"):
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON public.{table_name}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
            """
        )
        op.execute(
            f"""
            COMMENT ON POLICY tenant_isolation_policy ON public.{table_name} IS
                'RLS policy enforcing tenant isolation for auth substrate. Requires app.current_tenant_id.';
            """
        )

    _grant_if_role_exists("app_user", "SELECT", "public.roles")
    _grant_if_role_exists("app_rw", "SELECT", "public.roles")
    _grant_if_role_exists("app_ro", "SELECT", "public.roles")

    _grant_if_role_exists("app_user", "SELECT, INSERT, UPDATE", "public.users")
    _grant_if_role_exists("app_rw", "SELECT, INSERT, UPDATE", "public.users")
    _grant_if_role_exists("app_ro", "SELECT", "public.users")

    _grant_if_role_exists(
        "app_user",
        "SELECT, INSERT, UPDATE, DELETE",
        "public.tenant_memberships",
    )
    _grant_if_role_exists(
        "app_rw",
        "SELECT, INSERT, UPDATE, DELETE",
        "public.tenant_memberships",
    )
    _grant_if_role_exists("app_ro", "SELECT", "public.tenant_memberships")

    _grant_if_role_exists(
        "app_user",
        "SELECT, INSERT, UPDATE, DELETE",
        "public.tenant_membership_roles",
    )
    _grant_if_role_exists(
        "app_rw",
        "SELECT, INSERT, UPDATE, DELETE",
        "public.tenant_membership_roles",
    )
    _grant_if_role_exists("app_ro", "SELECT", "public.tenant_membership_roles")


def downgrade() -> None:
    for table_name in (
        "public.tenant_membership_roles",
        "public.tenant_memberships",
        "public.users",
        "public.roles",
    ):
        _revoke_if_role_exists("app_ro", table_name)
        _revoke_if_role_exists("app_rw", table_name)
        _revoke_if_role_exists("app_user", table_name)

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy ON public.tenant_membership_roles"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy ON public.tenant_memberships"
    )

    op.execute(
        "DROP TABLE IF EXISTS public.tenant_membership_roles"
    )  # CI:DESTRUCTIVE_OK - downgrade rollback for B1.2-P2 auth substrate
    op.execute(
        "DROP TABLE IF EXISTS public.tenant_memberships"
    )  # CI:DESTRUCTIVE_OK - downgrade rollback for B1.2-P2 auth substrate
    op.execute(
        "DROP TABLE IF EXISTS public.users"
    )  # CI:DESTRUCTIVE_OK - downgrade rollback for B1.2-P2 auth substrate
    op.execute(
        "DROP TABLE IF EXISTS public.roles"
    )  # CI:DESTRUCTIVE_OK - downgrade rollback for B1.2-P2 auth substrate

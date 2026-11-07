"""Supported signup and single-membership login lookup.

Revision ID: 202611070001
Revises: 202610280001
Create Date: 2026-11-07 00:01:00
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = "202611070001"
down_revision = "202610280001"
branch_labels = None
depends_on = None

REGISTER_SIGNATURE = "auth.register_business_account(text, text, text)"
LOOKUP_SIGNATURE = "auth.lookup_single_active_tenant(uuid)"


def _require_role(role: str, *, bypass_rls: bool = False) -> None:
    row = (
        op.get_bind()
        .execute(
            text("SELECT rolbypassrls FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise RuntimeError(f"required_role_missing:{role}")
    if bypass_rls and not bool(row["rolbypassrls"]):
        raise RuntimeError(f"required_role_missing_bypassrls:{role}")


def _grant_execute_only_app_user(signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(
        f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
        f" WHERE rolname = 'app_user') THEN EXECUTE 'GRANT EXECUTE ON"
        f" FUNCTION {signature} TO app_user'; END IF; END $$;"
    )


def upgrade() -> None:
    _require_role("app_account_provisioner", bypass_rls=True)
    _require_role("app_auth_lookup", bypass_rls=True)
    _require_role("app_user")

    op.execute("GRANT USAGE ON SCHEMA auth TO app_account_provisioner")
    op.execute(
        "GRANT SELECT (code) ON TABLE public.roles"
        " TO app_account_provisioner"
    )
    op.execute(
        "GRANT INSERT (id, name, notification_email, api_key_hash)"
        " ON TABLE public.tenants TO app_account_provisioner"
    )
    op.execute(
        "GRANT INSERT (id, login_identifier_hash, password_hash,"
        " auth_provider, is_active) ON TABLE public.users"
        " TO app_account_provisioner"
    )
    op.execute(
        "GRANT INSERT (id, tenant_id, user_id, membership_status)"
        " ON TABLE public.tenant_memberships TO app_account_provisioner"
    )
    op.execute(
        "GRANT INSERT (id, tenant_id, membership_id, role_code)"
        " ON TABLE public.tenant_membership_roles TO app_account_provisioner"
    )
    op.execute(
        "GRANT SELECT (user_id, tenant_id, membership_status)"
        " ON TABLE public.tenant_memberships TO app_auth_lookup"
    )
    # Signup is the account authority boundary. The historical pre-auth
    # provisioning grant let app_user insert an identity directly, bypassing
    # this operation's duplicate/atomicity law. Revoke the direct relation
    # INSERT; the definer operation owns the only remaining insert path.
    op.execute("REVOKE INSERT ON TABLE public.users FROM app_user")
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
        " WHERE rolname = 'app_rw') THEN EXECUTE"
        " 'REVOKE INSERT ON TABLE public.users FROM app_rw';"
        " END IF; END $$;"
    )

    op.execute(
        """
CREATE OR REPLACE FUNCTION auth.register_business_account(
    p_login_identifier_hash text,
    p_password_hash text,
    p_workspace_name text
)
RETURNS TABLE (user_id uuid, tenant_id uuid)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $function$
DECLARE
    _tenant_id uuid := gen_random_uuid();
    _user_id uuid := gen_random_uuid();
    _membership_id uuid := gen_random_uuid();
    _workspace_name text := btrim(p_workspace_name);
BEGIN
    IF p_login_identifier_hash IS NULL
       OR btrim(p_login_identifier_hash) = '' THEN
        RAISE EXCEPTION 'register_login_identifier_required'
            USING ERRCODE = '22023';
    END IF;
    IF p_password_hash IS NULL OR btrim(p_password_hash) = '' THEN
        RAISE EXCEPTION 'register_password_hash_required'
            USING ERRCODE = '22023';
    END IF;
    IF _workspace_name IS NULL OR _workspace_name = '' THEN
        RAISE EXCEPTION 'register_workspace_name_required'
            USING ERRCODE = '22023';
    END IF;
    PERFORM 1 FROM public.roles WHERE code = 'admin';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'register_admin_role_missing'
            USING ERRCODE = '23503';
    END IF;

    INSERT INTO public.tenants (
        id,
        name,
        notification_email,
        api_key_hash
    ) VALUES (
        _tenant_id,
        _workspace_name,
        'unavailable@skeldir.invalid',
        encode(digest(gen_random_bytes(32), 'sha256'), 'hex')
    );
    INSERT INTO public.users (
        id,
        login_identifier_hash,
        password_hash,
        auth_provider,
        is_active
    ) VALUES (
        _user_id,
        p_login_identifier_hash,
        p_password_hash,
        'password',
        true
    );
    INSERT INTO public.tenant_memberships (
        id,
        tenant_id,
        user_id,
        membership_status
    ) VALUES (
        _membership_id,
        _tenant_id,
        _user_id,
        'active'
    );
    INSERT INTO public.tenant_membership_roles (
        id,
        tenant_id,
        membership_id,
        role_code
    ) VALUES (
        gen_random_uuid(),
        _tenant_id,
        _membership_id,
        'admin'
    );

    RETURN QUERY SELECT _user_id, _tenant_id;
END
$function$
        """
    )
    op.execute(f"ALTER FUNCTION {REGISTER_SIGNATURE} OWNER TO app_account_provisioner")
    _grant_execute_only_app_user(REGISTER_SIGNATURE)

    op.execute(
        """
CREATE OR REPLACE FUNCTION auth.lookup_single_active_tenant(
    p_user_id uuid
)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $function$
    SELECT membership.tenant_id
      FROM public.tenant_memberships AS membership
     WHERE membership.user_id = p_user_id
       AND membership.membership_status = 'active'
       AND (
           SELECT count(*)
             FROM public.tenant_memberships AS active_membership
            WHERE active_membership.user_id = p_user_id
              AND active_membership.membership_status = 'active'
       ) = 1
     LIMIT 1
$function$
        """
    )
    op.execute(f"ALTER FUNCTION {LOOKUP_SIGNATURE} OWNER TO app_auth_lookup")
    _grant_execute_only_app_user(LOOKUP_SIGNATURE)

    # Follow the existing lookup convention: the migration principal may
    # reach the owner transiently through app_account_provisioner, but no
    # direct app_auth_lookup membership is retained.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM pg_auth_members m
                  JOIN pg_roles r ON r.oid = m.roleid
                  JOIN pg_roles u ON u.oid = m.member
                 WHERE r.rolname = 'app_auth_lookup'
                   AND u.rolname = current_user
            ) THEN
                EXECUTE 'REVOKE app_auth_lookup FROM ' || quote_ident(current_user);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Restore the predecessor account-write posture exactly.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
        " WHERE rolname = 'app_user') THEN EXECUTE"
        " 'GRANT INSERT ON TABLE public.users TO app_user';"
        " END IF; END $$;"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {REGISTER_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {REGISTER_SIGNATURE} FROM app_user")
    op.execute(f"REVOKE ALL ON FUNCTION {LOOKUP_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {LOOKUP_SIGNATURE} FROM app_user")
    op.execute(f"DROP FUNCTION IF EXISTS {REGISTER_SIGNATURE}")
    op.execute(f"DROP FUNCTION IF EXISTS {LOOKUP_SIGNATURE}")

    op.execute(
        "REVOKE SELECT (user_id, tenant_id, membership_status)"
        " ON TABLE public.tenant_memberships FROM app_auth_lookup"
    )
    op.execute(
        "REVOKE INSERT (id, tenant_id, membership_id, role_code)"
        " ON TABLE public.tenant_membership_roles FROM app_account_provisioner"
    )
    op.execute(
        "REVOKE INSERT (id, tenant_id, user_id, membership_status)"
        " ON TABLE public.tenant_memberships FROM app_account_provisioner"
    )
    op.execute(
        "REVOKE INSERT (id, login_identifier_hash, password_hash,"
        " auth_provider, is_active) ON TABLE public.users"
        " FROM app_account_provisioner"
    )
    op.execute(
        "REVOKE INSERT (id, name, notification_email, api_key_hash)"
        " ON TABLE public.tenants FROM app_account_provisioner"
    )
    op.execute(
        "REVOKE SELECT (code) ON TABLE public.roles"
        " FROM app_account_provisioner"
    )
    op.execute("REVOKE USAGE ON SCHEMA auth FROM app_account_provisioner")

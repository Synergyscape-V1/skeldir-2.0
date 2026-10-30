#!/usr/bin/env python3
"""Verify or establish the role prerequisites for the XXV migrations.

The XXV migrations grant and transfer ownership; they do not silently skip a
missing role. This preflight is the deployment-side consumer of that law:

* ``app_auth_lookup`` is a NOLOGIN BYPASSRLS owner role. It is created here
  when the migration principal has CREATEROLE, or the run fails visibly.
* Every runtime role the migration grants to must already exist. Production
  login roles must be LOGIN; this script never invents passwords.
* The migration principal must be able to own the auth-lookup functions.

Run before ``alembic upgrade head`` with the production migration DSN.
"""

from __future__ import annotations

import argparse
import sys

import psycopg2
from psycopg2 import sql


AUTH_LOOKUP_ROLE = "app_auth_lookup"
REQUIRED_RUNTIME_ROLES = (
    "app_user",
    "app_ingress",
    "app_worker",
    "app_trust_issuer",
    "app_relay",
    "app_ro",
)
REQUIRED_LOGIN_ROLES = (
    "app_user",
    "app_ingress",
    "app_worker",
    "app_trust_issuer",
    "app_relay",
)


def _role_row(cursor, role: str) -> tuple[bool, bool, bool] | None:
    cursor.execute(
        "SELECT rolcanlogin, rolbypassrls, rolsuper FROM pg_roles"
        " WHERE rolname = %s",
        (role,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return bool(row[0]), bool(row[1]), bool(row[2])


def _ensure_auth_lookup(cursor, errors: list[str]) -> None:
    row = _role_row(cursor, AUTH_LOOKUP_ROLE)
    if row is None:
        try:
            cursor.execute(
                sql.SQL("CREATE ROLE {} NOLOGIN BYPASSRLS").format(
                    sql.Identifier(AUTH_LOOKUP_ROLE)
                )
            )
        except psycopg2.Error as exc:
            errors.append(
                f"cannot_create_{AUTH_LOOKUP_ROLE}:{exc.__class__.__name__}"
            )
            return
        row = _role_row(cursor, AUTH_LOOKUP_ROLE)
    if row is None:
        errors.append(f"missing_{AUTH_LOOKUP_ROLE}")
        return
    can_login, bypass_rls, _ = row
    if can_login:
        errors.append(f"{AUTH_LOOKUP_ROLE}_must_be_nologin")
    if not bypass_rls:
        errors.append(f"{AUTH_LOOKUP_ROLE}_must_bypass_rls")


def _ensure_migration_can_own(cursor, errors: list[str]) -> None:
    cursor.execute(
        "SELECT rolsuper OR pg_has_role("
        "current_user, %s, 'member'"
        ") FROM pg_roles WHERE rolname = current_user",
        (AUTH_LOOKUP_ROLE,),
    )
    row = cursor.fetchone()
    if row is not None and bool(row[0]):
        return
    cursor.execute("SELECT current_user")
    current_user = str(cursor.fetchone()[0])
    try:
        cursor.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(AUTH_LOOKUP_ROLE),
                sql.Identifier(current_user),
            )
        )
    except psycopg2.Error as exc:
        errors.append(
            "migration_owner_cannot_inherit_app_auth_lookup:"
            f"{exc.__class__.__name__}"
        )
        return
    cursor.execute(
        "SELECT pg_has_role(current_user, %s, 'member')",
        (AUTH_LOOKUP_ROLE,),
    )
    row = cursor.fetchone()
    if row is None or not bool(row[0]):
        errors.append("migration_owner_cannot_inherit_app_auth_lookup")


def _check_runtime_roles(
    cursor, *, require_login: bool, errors: list[str]
) -> None:
    for role in REQUIRED_RUNTIME_ROLES:
        row = _role_row(cursor, role)
        if row is None:
            errors.append(f"missing_runtime_role:{role}")
            continue
        can_login, _, _ = row
        if require_login and role in REQUIRED_LOGIN_ROLES and not can_login:
            errors.append(f"runtime_role_not_login:{role}")


def _check_post_migration(cursor, errors: list[str]) -> None:
    for function_name in (
        "lookup_user_auth_by_login_hash",
        "lookup_user_by_login_hash",
    ):
        cursor.execute(
            "SELECT pg_get_userbyid(p.proowner)"
            " FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'auth' AND p.proname = %s",
            (function_name,),
        )
        row = cursor.fetchone()
        if row is None:
            errors.append(f"missing_auth_lookup_function:{function_name}")
        elif str(row[0]) != AUTH_LOOKUP_ROLE:
            errors.append(f"auth_lookup_function_owner_mismatch:{function_name}")
        cursor.execute(
            "SELECT has_function_privilege("
            "'app_user', p.oid, 'EXECUTE')"
            " FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'auth' AND p.proname = %s",
            (function_name,),
        )
        row = cursor.fetchone()
        if row is None or not bool(row[0]):
            errors.append(f"app_user_lacks_execute:{function_name}")
    cursor.execute(
        "SELECT has_table_privilege('app_auth_lookup',"
        " 'public.users', 'SELECT')"
    )
    row = cursor.fetchone()
    if row is None or not bool(row[0]):
        errors.append("app_auth_lookup_lacks_users_select")
    for role in REQUIRED_RUNTIME_ROLES:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s",
            (role,),
        )
        row = cursor.fetchone()
        if row is None:
            continue
        if bool(row[0]):
            errors.append(f"runtime_role_is_superuser:{role}")
        if bool(row[1]):
            errors.append(f"runtime_role_bypasses_rls:{role}")


def _check_runtime_login(dsn: str, expected_role: str, errors: list[str]) -> None:
    try:
        conn = psycopg2.connect(dsn, connect_timeout=10)
    except psycopg2.Error as exc:
        errors.append(f"runtime_login_failed:{exc.__class__.__name__}")
        return
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            row = cursor.fetchone()
            if row is None:
                errors.append("runtime_login_current_user_unreadable")
            else:
                current_user, is_super, bypass_rls = row
                if str(current_user) != expected_role:
                    errors.append(f"runtime_login_wrong_role:{current_user}")
                if bool(is_super):
                    errors.append("runtime_login_is_superuser")
                if bool(bypass_rls):
                    errors.append("runtime_login_bypasses_rls")
    except psycopg2.Error as exc:
        errors.append(f"runtime_login_query_failed:{exc.__class__.__name__}")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument(
        "--require-login-runtime-roles",
        action="store_true",
        help="Production mode: require every runtime login role to be LOGIN.",
    )
    parser.add_argument(
        "--post-migration",
        action="store_true",
        help="Verify ownership/grants created by the XXV migrations.",
    )
    parser.add_argument(
        "--runtime-dsn",
        help="Real runtime login DSN used to prove current_user and RLS.",
    )
    parser.add_argument(
        "--expected-runtime-role",
        default="app_user",
        help="Expected current_user for --runtime-dsn.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    try:
        conn = psycopg2.connect(args.dsn, connect_timeout=10)
    except psycopg2.Error as exc:
        print(f"B26_MIGRATION_ROLE_PREREQ_FAIL: connect:{exc.__class__.__name__}")
        return 1

    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            _ensure_auth_lookup(cursor, errors)
            _ensure_migration_can_own(cursor, errors)
            _check_runtime_roles(
                cursor,
                require_login=args.require_login_runtime_roles,
                errors=errors,
            )
            if args.post_migration:
                _check_post_migration(cursor, errors)
            if args.post_migration and not args.runtime_dsn:
                errors.append("runtime_login_proof_missing")
            cursor.execute(
                "SELECT rolname, rolcanlogin, rolbypassrls FROM pg_roles"
                " WHERE rolname = ANY(%s) ORDER BY rolname",
                (list(REQUIRED_RUNTIME_ROLES) + [AUTH_LOOKUP_ROLE],),
            )
            for row in cursor.fetchall():
                print(f"role={row[0]} login={row[1]} bypassrls={row[2]}")
    except psycopg2.Error as exc:
        errors.append(f"prerequisite_query_failed:{exc.__class__.__name__}")
    finally:
        conn.close()

    if args.post_migration and args.runtime_dsn:
        _check_runtime_login(
            args.runtime_dsn, args.expected_runtime_role, errors
        )

    if errors:
        print("B26_MIGRATION_ROLE_PREREQ_FAIL")
        for error in errors:
            print(error)
        return 1
    print("B26_MIGRATION_ROLE_PREREQ_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

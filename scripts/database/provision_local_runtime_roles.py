"""Provision the local-development PostgreSQL role graph.

Production deployments establish roles through the governed preflight and
fail closed when a runtime login role is absent. The local containerized topology needs an
explicit, idempotent bootstrap because migrations now require the auth lookup
role to exist instead of silently skipping its grants.
"""

from __future__ import annotations

import os

import psycopg2
from psycopg2 import sql


_ROLES: tuple[tuple[str, str], ...] = (
    ("app_auth_lookup", "NOLOGIN BYPASSRLS"),
    ("app_account_provisioner", "NOLOGIN BYPASSRLS"),
    ("app_ingress", "LOGIN PASSWORD 'app_ingress'"),
    ("app_worker", "LOGIN PASSWORD 'app_worker'"),
    ("app_relay", "LOGIN PASSWORD 'app_relay'"),
    ("app_beat", "LOGIN PASSWORD 'app_beat'"),
    ("app_trust_issuer", "LOGIN PASSWORD 'app_trust_issuer'"),
    ("app_trust_signer", "LOGIN PASSWORD 'app_trust_signer'"),
    ("app_dispatch_publisher", "LOGIN PASSWORD 'app_dispatch_publisher'"),
)


def main() -> None:
    dsn = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("MIGRATION_DATABASE_URL is required")
    connection = psycopg2.connect(dsn)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            for name, attributes in _ROLES:
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
                if cursor.fetchone() is not None:
                    continue
                cursor.execute(
                    sql.SQL("CREATE ROLE {} " + attributes).format(sql.Identifier(name))
                )
            cursor.execute(
                "SELECT current_user, r.rolsuper FROM pg_roles AS r"
                " WHERE r.rolname = current_user"
            )
            current = cursor.fetchone()
            current_user = str(current[0])
            is_superuser = bool(current[1])

            def has_membership(role_name: str, member_name: str) -> bool:
                cursor.execute(
                    "SELECT EXISTS ("
                    " SELECT 1 FROM pg_auth_members m"
                    " JOIN pg_roles r ON r.oid = m.roleid"
                    " JOIN pg_roles u ON u.oid = m.member"
                    " WHERE r.rolname = %s AND u.rolname = %s)",
                    (role_name, member_name),
                )
                return bool(cursor.fetchone()[0])

            def has_admin(role_name: str, member_name: str) -> bool:
                cursor.execute(
                    "SELECT m.admin_option FROM pg_auth_members m"
                    " JOIN pg_roles r ON r.oid = m.roleid"
                    " JOIN pg_roles u ON u.oid = m.member"
                    " WHERE r.rolname = %s AND u.rolname = %s",
                    (role_name, member_name),
                )
                row = cursor.fetchone()
                return bool(row[0]) if row else False

            cursor.execute(
                """
                SELECT p.proname, pg_get_userbyid(p.proowner)
                  FROM pg_proc AS p
                  JOIN pg_namespace AS n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'auth'
                   AND p.oid::regprocedure::text IN (
                       'auth.register_business_account(text,text,text)',
                       'auth.lookup_single_active_tenant(uuid)'
                   )
                """
            )
            owners = {
                str(name): str(owner) for name, owner in cursor.fetchall()
            }
            ownership_transfer_needed = not (
                owners.get("register_business_account")
                == "app_account_provisioner"
                and owners.get("lookup_single_active_tenant")
                == "app_auth_lookup"
            )
            temporary_edges = (
                has_membership("app_auth_lookup", "app_account_provisioner")
                or has_membership("app_account_provisioner", current_user)
                or has_membership("app_auth_lookup", current_user)
            )
            if not ownership_transfer_needed and not temporary_edges:
                return

            if ownership_transfer_needed or has_membership(
                "app_auth_lookup", "app_account_provisioner"
            ):
                if (
                    ownership_transfer_needed
                    or not has_admin(
                        "app_auth_lookup", "app_account_provisioner"
                    )
                ):
                    cursor.execute(
                        sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                            sql.Identifier("app_auth_lookup"),
                            sql.Identifier("app_account_provisioner"),
                        )
                    )
            if not is_superuser:
                if ownership_transfer_needed or has_membership(
                    "app_account_provisioner", current_user
                ):
                    if (
                        ownership_transfer_needed
                        or not has_admin(
                            "app_account_provisioner", current_user
                        )
                    ):
                        cursor.execute(
                            sql.SQL(
                                "GRANT {} TO {} WITH ADMIN OPTION"
                            ).format(
                                sql.Identifier("app_account_provisioner"),
                                sql.Identifier(current_user),
                            )
                        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

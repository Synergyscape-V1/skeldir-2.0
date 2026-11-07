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
            cursor.execute("SELECT current_user")
            current_user = str(cursor.fetchone()[0])
            for role_name, member_name in (
                ("app_auth_lookup", "app_account_provisioner"),
                ("app_account_provisioner", current_user),
            ):
                cursor.execute(
                    "SELECT pg_has_role(%s, %s, 'member')",
                    (member_name, role_name),
                )
                if not bool(cursor.fetchone()[0]):
                    cursor.execute(
                        sql.SQL("GRANT {} TO {}").format(
                            sql.Identifier(role_name),
                            sql.Identifier(member_name),
                        )
                    )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

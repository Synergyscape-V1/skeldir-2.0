"""Provision the local-development PostgreSQL role graph.

Production deployments establish roles through the governed preflight and
fail closed when a runtime login role is absent. The local containerized topology needs an
explicit, idempotent bootstrap because migrations now require the auth lookup
role to exist instead of silently skipping its grants.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from psycopg2 import sql


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCOUNT_PREREQUISITE_REVISION = "202611070001"

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


def _account_construction_applied(cursor) -> bool:
    cursor.execute("SELECT to_regclass('public.alembic_version')")
    if cursor.fetchone()[0] is None:
        return False
    cursor.execute("SELECT version_num FROM public.alembic_version")
    heads = tuple(str(row[0]) for row in cursor.fetchall())
    if not heads:
        return False
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    return any(
        revision.revision == _ACCOUNT_PREREQUISITE_REVISION
        for revision in script.iterate_revisions(heads, "base")
    )


def _account_owners(cursor) -> dict[str, str]:
    cursor.execute(
        "SELECT to_regprocedure(%s)::oid, to_regprocedure(%s)::oid",
        (
            "auth.register_business_account(text,text,text)",
            "auth.lookup_single_active_tenant(uuid)",
        ),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("account_function_lookup_unavailable")
    owners: dict[str, str] = {}
    for name, oid in zip(
        ("register_business_account", "lookup_single_active_tenant"), row
    ):
        if oid is None:
            raise RuntimeError(f"account_function_metadata_unavailable:{name}")
        cursor.execute(
            "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = %s",
            (oid,),
        )
        owner = cursor.fetchone()
        if owner is None:
            raise RuntimeError(f"account_function_metadata_unavailable:{name}")
        owners[name] = str(owner[0])
    return owners


def main() -> None:
    dsn = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("MIGRATION_DATABASE_URL is required")
    connection = psycopg2.connect(dsn)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            if _account_construction_applied(cursor):
                owners = _account_owners(cursor)
                if owners["register_business_account"] != "app_account_provisioner":
                    raise RuntimeError(
                        "account_function_owner_unexpected:"
                        "register_business_account"
                    )
                if owners["lookup_single_active_tenant"] != "app_auth_lookup":
                    raise RuntimeError(
                        "account_function_owner_unexpected:"
                        "lookup_single_active_tenant"
                    )
                # Fully constructed current authority: do not create any
                # temporary edge, including when an unexpected edge survives.
                return

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

            cursor.execute(
                sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                    sql.Identifier("app_auth_lookup"),
                    sql.Identifier("app_account_provisioner"),
                )
            )
            if not is_superuser:
                cursor.execute(
                    sql.SQL("GRANT {} TO {} WITH ADMIN OPTION").format(
                        sql.Identifier("app_account_provisioner"),
                        sql.Identifier(current_user),
                    )
                )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

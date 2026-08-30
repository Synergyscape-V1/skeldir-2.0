#!/usr/bin/env python3
"""Prepare a least-privilege runtime/migration authority database boundary.

Provisioning is monotonic with respect to security hardening. A later
invocation may create missing required authority; it may never silently
reintroduce authority the migration history deliberately removed. Formally:

    effective_runtime_privileges(after reprovision)
        subset-of
    governed_runtime_privileges(at migration head)

The governed runtime set is a function of the applied migration head, not a
constant. Migrations authored below revision 202512301930 transfer
materialized-view ownership to the runtime principal, which PostgreSQL permits
only while that principal can create in ``public``; at or above that revision
CREATE is exactly the authority the migration history removed. Provisioning
therefore grants CREATE only while the chain still requires it and revokes it
once the hardening revision has been applied, reading the revision graph rather
than the live privilege so a database whose hardening was undone out of band is
re-hardened instead of mistaken for a virgin cluster.

A fresh install, an incremental upgrade through the hardening revision, and a
reprovision of an already-migrated database consequently converge on one
least-privilege state. A post-condition assertion fails the process closed if
they ever do not.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import psycopg2
from psycopg2 import sql


# Authority the runtime principal may hold on schema ``public`` after any legal
# provisioning history. Schema authorship belongs to the migration principal.
GOVERNED_RUNTIME_SCHEMA_PRIVILEGES = ("USAGE",)
FORBIDDEN_RUNTIME_SCHEMA_PRIVILEGES = ("CREATE",)

# The revision that deliberately removed runtime CREATE on schema ``public``.
# Migrations authored before it transfer materialized-view ownership to the
# runtime principal, which PostgreSQL only permits while that principal can
# create in the schema. The governed runtime privilege set is therefore a
# function of the applied head, not a constant: CREATE is required strictly
# below this revision and forbidden at or above it.
RUNTIME_SCHEMA_HARDENING_REVISION = "202512301930"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class AuthorityExpansionError(RuntimeError):
    """Provisioning would have left the runtime principal over-privileged."""


@dataclass(frozen=True)
class AuthorityConfig:
    admin_dsn: str
    database_name: str
    runtime_user: str
    runtime_password: str
    migration_user: str
    migration_password: str
    app_rw_role: str
    app_ro_role: str
    worker_user: str
    worker_password: str
    publisher_user: str
    publisher_password: str
    trust_issuer_user: str = "app_trust_issuer"
    trust_issuer_password: str = "app_trust_issuer"
    rotate_existing_credentials: bool = False


def _parse_args() -> AuthorityConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Create/normalize runtime and migration principals for schema authority separation."
        )
    )
    parser.add_argument(
        "--admin-dsn", required=True, help="Superuser/admin PostgreSQL DSN."
    )
    parser.add_argument("--database-name", required=True, help="Target database name.")
    parser.add_argument("--runtime-user", default="app_user")
    parser.add_argument("--runtime-password", default="app_user")
    parser.add_argument("--migration-user", default="migration_owner")
    parser.add_argument("--migration-password", default="migration_owner")
    parser.add_argument("--app-rw-role", default="app_rw")
    parser.add_argument("--app-ro-role", default="app_ro")
    parser.add_argument("--worker-user", default="app_worker")
    parser.add_argument("--worker-password", default="app_worker")
    parser.add_argument("--publisher-user", default="app_dispatch_publisher")
    parser.add_argument("--publisher-password", default="app_dispatch_publisher")
    parser.add_argument("--trust-issuer-user", default="app_trust_issuer")
    parser.add_argument("--trust-issuer-password", default="app_trust_issuer")
    parser.add_argument(
        "--rotate-existing-credentials",
        action="store_true",
        help=(
            "Reset passwords on roles that already exist. Off by default so a "
            "redeploy cannot silently rotate live credentials onto bootstrap "
            "defaults, which would collapse the API/worker credential custody "
            "the worker authority boundary depends on."
        ),
    )
    args = parser.parse_args()
    return AuthorityConfig(
        admin_dsn=args.admin_dsn,
        database_name=args.database_name,
        runtime_user=args.runtime_user,
        runtime_password=args.runtime_password,
        migration_user=args.migration_user,
        migration_password=args.migration_password,
        app_rw_role=args.app_rw_role,
        app_ro_role=args.app_ro_role,
        worker_user=args.worker_user,
        worker_password=args.worker_password,
        publisher_user=args.publisher_user,
        publisher_password=args.publisher_password,
        trust_issuer_user=args.trust_issuer_user,
        trust_issuer_password=args.trust_issuer_password,
        rotate_existing_credentials=bool(args.rotate_existing_credentials),
    )


def _role_exists(cursor, role_name: str) -> bool:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role_name,))
    return cursor.fetchone() is not None


def _database_exists(cursor, database_name: str) -> bool:
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
    return cursor.fetchone() is not None


def _create_or_alter_login_role(
    cursor, role_name: str, password: str, *, rotate_existing: bool
) -> None:
    if _role_exists(cursor, role_name):
        # Ensure the capability, not the secret. Rewriting the password of a
        # role that already exists would let a routine redeploy rotate a live
        # credential onto a bootstrap default and collapse the API/worker
        # custody separation; that requires an explicit operator decision.
        cursor.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN").format(sql.Identifier(role_name))
        )
        if rotate_existing:
            cursor.execute(
                sql.SQL("ALTER ROLE {} WITH PASSWORD %s").format(
                    sql.Identifier(role_name)
                ),
                (password,),
            )
        return
    cursor.execute(
        sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
            sql.Identifier(role_name)
        ),
        (password,),
    )


def _create_nologin_role_if_missing(cursor, role_name: str) -> None:
    if _role_exists(cursor, role_name):
        return
    cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role_name)))


def _ensure_role_membership(cursor, *, role_name: str, member_name: str) -> None:
    cursor.execute(
        """
        SELECT 1
        FROM pg_auth_members m
        JOIN pg_roles role_ref ON role_ref.oid = m.roleid
        JOIN pg_roles member_ref ON member_ref.oid = m.member
        WHERE role_ref.rolname = %s
          AND member_ref.rolname = %s
        """,
        (role_name, member_name),
    )
    if cursor.fetchone() is not None:
        return
    cursor.execute(
        sql.SQL("GRANT {} TO {}").format(
            sql.Identifier(role_name),
            sql.Identifier(member_name),
        )
    )


def _prepare_authority_surface(config: AuthorityConfig) -> bool:
    admin_conn = psycopg2.connect(config.admin_dsn)
    try:
        admin_conn.autocommit = True
        with admin_conn.cursor() as cursor:
            rotate = config.rotate_existing_credentials
            _create_or_alter_login_role(
                cursor,
                config.runtime_user,
                config.runtime_password,
                rotate_existing=rotate,
            )
            _create_or_alter_login_role(
                cursor,
                config.migration_user,
                config.migration_password,
                rotate_existing=rotate,
            )
            _create_nologin_role_if_missing(cursor, config.app_rw_role)
            _create_nologin_role_if_missing(cursor, config.app_ro_role)
            _create_or_alter_login_role(
                cursor,
                config.worker_user,
                config.worker_password,
                rotate_existing=rotate,
            )
            # Cross-tenant dispatch visibility is a separate credential-custody
            # boundary.  This login is intentionally not a member of app_rw,
            # app_ro, app_user, or app_worker.
            _create_or_alter_login_role(
                cursor,
                config.publisher_user,
                config.publisher_password,
                rotate_existing=rotate,
            )
            # B2.5-P13 Corrective XVI. Recording a completed issuance is the
            # act of asserting that a private key physically produced a
            # signature. That authority is narrowed to its own login principal
            # so that the ordinary runtime DSN -- the credential most exposed to
            # leak, insider use, or a compromise elsewhere in the application --
            # physically cannot manufacture completed-issuance history. Like the
            # dispatch publisher, this login is deliberately not a member of
            # app_rw, app_ro, app_user, or app_worker: its only table privilege
            # is granted by the C16 migration, on trust_access_log alone.
            _create_or_alter_login_role(
                cursor,
                config.trust_issuer_user,
                config.trust_issuer_password,
                rotate_existing=rotate,
            )
            # The migration principal must be a member of the worker role:
            # PostgreSQL requires membership in a role to transfer object
            # ownership to it, and the planner's SECURITY DEFINER functions must
            # be owned by app_worker. This is a governed exception, not an
            # oversight -- see docs/architecture/b25_p13_c7_authority_topology.md.
            # It is bounded by custody rather than by NOINHERIT: PostgreSQL 15
            # has no per-membership INHERIT option, and a role-wide NOINHERIT
            # would strip this principal of the pg_database_owner authority it
            # needs to migrate at all. The migration DSN is therefore never
            # issued to an API or worker process, which the C7 topology gate
            # asserts against every in-scope executable topology.

            if not _database_exists(cursor, config.database_name):
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(config.database_name),
                        sql.Identifier(config.migration_user),
                    )
                )
            else:
                cursor.execute(
                    sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                        sql.Identifier(config.database_name),
                        sql.Identifier(config.migration_user),
                    )
                )

            _ensure_role_membership(
                cursor,
                role_name=config.runtime_user,
                member_name=config.migration_user,
            )
            _ensure_role_membership(
                cursor,
                role_name=config.worker_user,
                member_name=config.migration_user,
            )
            _ensure_role_membership(
                cursor,
                role_name=config.app_rw_role,
                member_name=config.runtime_user,
            )
            _ensure_role_membership(
                cursor,
                role_name=config.app_ro_role,
                member_name=config.runtime_user,
            )
            _ensure_role_membership(
                cursor,
                role_name=config.app_rw_role,
                member_name=config.worker_user,
            )
            _ensure_role_membership(
                cursor,
                role_name=config.app_ro_role,
                member_name=config.worker_user,
            )
    finally:
        admin_conn.close()

    db_admin_dsn = (
        f"postgresql://{config.migration_user}:{config.migration_password}"
        f"@{_host_port_fragment(config.admin_dsn)}/{config.database_name}"
    )
    db_conn = psycopg2.connect(db_admin_dsn)
    try:
        db_conn.autocommit = True
        with db_conn.cursor() as cursor:
            # Schema authorship belongs to the migration principal alone.
            cursor.execute(
                sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(
                    sql.Identifier(config.migration_user)
                )
            )
            # The runtime principal consumes the schema. It received
            # GRANT ALL unconditionally, which meant every reprovision handed
            # back CREATE on public -- silently undoing migration 202512301930
            # and reopening the object-shadowing surface the SECURITY DEFINER
            # planner functions depend on being closed.
            #
            # The governed runtime set is now a function of the applied head.
            # Below the hardening revision CREATE is a genuine prerequisite of
            # the migration chain itself; at or above it CREATE is revoked, so
            # a reprovision of an already-migrated database converges on the
            # hardened state rather than away from it.
            for privilege in GOVERNED_RUNTIME_SCHEMA_PRIVILEGES:
                cursor.execute(
                    sql.SQL("GRANT {} ON SCHEMA public TO {}").format(
                        sql.SQL(privilege),
                        sql.Identifier(config.runtime_user),
                    )
                )
            hardened = _runtime_schema_hardening_applied(cursor)
            for privilege in FORBIDDEN_RUNTIME_SCHEMA_PRIVILEGES:
                if hardened:
                    cursor.execute(
                        sql.SQL("REVOKE {} ON SCHEMA public FROM {}").format(
                            sql.SQL(privilege),
                            sql.Identifier(config.runtime_user),
                        )
                    )
                    # Mirror migration 202512301930: the implicit PUBLIC grant
                    # is an authority path into the runtime principal too.
                    cursor.execute(
                        sql.SQL("REVOKE {} ON SCHEMA public FROM PUBLIC").format(
                            sql.SQL(privilege)
                        )
                    )
                else:
                    cursor.execute(
                        sql.SQL("GRANT {} ON SCHEMA public TO {}").format(
                            sql.SQL(privilege),
                            sql.Identifier(config.runtime_user),
                        )
                    )
            cursor.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT SELECT, INSERT ON TABLES TO {}"
                ).format(
                    sql.Identifier(config.migration_user),
                    sql.Identifier(config.runtime_user),
                )
            )
            _assert_runtime_authority_not_expanded(cursor, config, hardened=hardened)
            return hardened
    finally:
        db_conn.close()


def _applied_migration_heads(cursor) -> tuple[str, ...]:
    cursor.execute("SELECT to_regclass('public.alembic_version')")
    if cursor.fetchone()[0] is None:
        return ()
    cursor.execute("SELECT version_num FROM public.alembic_version")
    return tuple(str(row[0]) for row in cursor.fetchall())


def _runtime_schema_hardening_applied(cursor) -> bool:
    """Has the migration history already removed runtime CREATE authority?

    Answered from the revision graph rather than from the live privilege, so a
    database whose hardening was undone out of band is still recognised as
    hardened and gets re-hardened instead of being mistaken for a virgin
    cluster that legitimately needs CREATE.
    """

    heads = _applied_migration_heads(cursor)
    if not heads:
        return False

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPOSITORY_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    for revision in script.iterate_revisions(heads, "base"):
        if revision.revision == RUNTIME_SCHEMA_HARDENING_REVISION:
            return True
    return False


def _assert_runtime_authority_not_expanded(
    cursor, config: AuthorityConfig, *, hardened: bool
) -> None:
    """Fail closed if provisioning left the runtime above its governed set."""

    if hardened:
        for privilege in FORBIDDEN_RUNTIME_SCHEMA_PRIVILEGES:
            cursor.execute(
                "SELECT has_schema_privilege(%s, 'public', %s)",
                (config.runtime_user, privilege),
            )
            if bool(cursor.fetchone()[0]):
                raise AuthorityExpansionError(
                    "runtime_authority_expansion:"
                    f"{config.runtime_user}:public:{privilege}"
                )
    for privilege in GOVERNED_RUNTIME_SCHEMA_PRIVILEGES:
        cursor.execute(
            "SELECT has_schema_privilege(%s, 'public', %s)",
            (config.runtime_user, privilege),
        )
        if not bool(cursor.fetchone()[0]):
            raise AuthorityExpansionError(
                f"runtime_authority_missing:{config.runtime_user}:public:{privilege}"
            )


def _host_port_fragment(admin_dsn: str) -> str:
    # admin_dsn is expected to be a standard postgresql:// URL for CI/local bootstrap.
    # Split once at @ and / to preserve explicit host:port.
    if "@" not in admin_dsn:
        return "127.0.0.1:5432"
    host_part = admin_dsn.split("@", 1)[1]
    if "/" in host_part:
        return host_part.split("/", 1)[0]
    return host_part


def main() -> int:
    config = _parse_args()
    if config.runtime_user == config.migration_user:
        raise RuntimeError(
            "runtime_user and migration_user must be distinct principals"
        )
    try:
        hardened = _prepare_authority_surface(config)
    except AuthorityExpansionError as exc:
        # An out-of-band grant that provisioning cannot revoke -- for example
        # one issued by a superuser -- must never be reported as a normal
        # provisioning success. Fail closed and name the exact privilege.
        print(f"migration_authority_boundary_failed:{exc}")
        return 1
    print("migration_authority_boundary_prepared")
    print(f"database={config.database_name}")
    print(f"runtime_user={config.runtime_user}")
    print(f"migration_user={config.migration_user}")
    print(f"worker_user={config.worker_user}")
    print(f"publisher_user={config.publisher_user}")
    print("runtime_schema_privileges=" + ",".join(GOVERNED_RUNTIME_SCHEMA_PRIVILEGES))
    print(f"runtime_schema_hardening_applied={str(hardened).lower()}")
    print(
        "runtime_schema_privileges_revoked="
        + (",".join(FORBIDDEN_RUNTIME_SCHEMA_PRIVILEGES) if hardened else "")
    )
    print("authority_monotonic=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Alembic environment configuration for Skeldir database migrations.

This module configures Alembic to use environment variables for database connection.
No hardcoded credentials are allowed.
"""

from logging.config import fileConfig
import os
import sys
from pathlib import Path
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import text
from alembic import context

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.control_plane import (
    _fetch_value_from_aws,
    resolve_aws_path_for_key,
    resolve_control_plane_env,
    should_enable_control_plane,
)
from app.core.managed_settings_contract import MANAGED_SETTINGS_CONTRACT

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolve migration URL through control-plane in stage/prod, fail-closed on absence.
ci_mode = os.environ.get("CI", "").lower() == "true"
environment = (os.environ.get("ENVIRONMENT") or "").strip().lower()

migration_database_url = os.environ.get("MIGRATION_DATABASE_URL")
if should_enable_control_plane():
    canonical_env = resolve_control_plane_env(os.environ.get("ENVIRONMENT"))
    contract = MANAGED_SETTINGS_CONTRACT["MIGRATION_DATABASE_URL"]
    path = resolve_aws_path_for_key(key="MIGRATION_DATABASE_URL", canonical_env=canonical_env)
    migration_database_url = _fetch_value_from_aws(contract, path)

if environment in {"stage", "prod"}:
    if not should_enable_control_plane():
        raise ValueError(
            "SKELDIR_CONTROL_PLANE_ENABLED=1 is required for stage/prod migrations."
        )
    if not migration_database_url:
        raise ValueError("MIGRATION_DATABASE_URL must resolve from control-plane in stage/prod.")

if ci_mode and not migration_database_url:
    raise ValueError(
        "MIGRATION_DATABASE_URL is required in CI for strict migration/runtime identity separation."
    )

database_url = migration_database_url
if not database_url and environment in {"local", "dev", "ci", ""}:
    database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise ValueError(
        "MIGRATION_DATABASE_URL is required. "
        "In local/dev/ci only, fallback to DATABASE_URL is allowed."
    )
if "postgresql+asyncpg://" in database_url:
    raise ValueError(
        "Async driver detected in DATABASE_URL/MIGRATION_DATABASE_URL "
        "(postgresql+asyncpg://). Alembic requires a sync driver "
        "(postgresql://user:password@host:port/dbname)."
    )

# Override sqlalchemy.url with environment variable
config.set_main_option("sqlalchemy.url", database_url)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _account_owner_state(connection) -> bool:
    """Return whether the pre-account transfer graph is needed.

    Account authority is inferred from the actual function OIDs and owners.
    An applied account-construction revision with missing or unexpected
    metadata is an explicit failure, never a virgin database.
    """
    applied = connection.execute(
        text("SELECT to_regclass('public.alembic_version')")
    ).scalar()
    if applied is None:
        return True

    heads = tuple(
        str(row[0])
        for row in connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).fetchall()
    )
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(config)
    account_applied = any(
        revision.revision == "202611070001"
        for revision in script.iterate_revisions(heads, "base")
    ) if heads else False
    if not account_applied:
        return True

    rows = connection.execute(
        text(
            "SELECT to_regprocedure(:register)::oid,"
            " to_regprocedure(:lookup)::oid"
        ),
        {
            "register": "auth.register_business_account(text,text,text)",
            "lookup": "auth.lookup_single_active_tenant(uuid)",
        },
    ).fetchone()
    if rows is None:
        raise RuntimeError("account_function_lookup_unavailable")
    names = ("register_business_account", "lookup_single_active_tenant")
    owners: dict[str, str] = {}
    for name, oid in zip(names, rows):
        if oid is None:
            raise RuntimeError(f"account_function_metadata_unavailable:{name}")
        owner = connection.execute(
            text(
                "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = :oid"
            ),
            {"oid": oid},
        ).scalar()
        if owner is None:
            raise RuntimeError(f"account_function_metadata_unavailable:{name}")
        owners[name] = str(owner)
    if owners["register_business_account"] != "app_account_provisioner":
        raise RuntimeError(
            "account_function_owner_unexpected:register_business_account"
        )
    if owners["lookup_single_active_tenant"] != "app_auth_lookup":
        raise RuntimeError(
            "account_function_owner_unexpected:lookup_single_active_tenant"
        )
    return False


def _provision_ci_migration_roles(connection) -> None:
    """Create CI-only role placeholders before the migration chain runs.

    Production deployments use the explicit preflight/provisioner and fail if
    a runtime login role is absent. CI lanes that migrate with an admin
    principal need the full role graph before the earliest grant-bearing
    migration, otherwise a later-created role would miss governed grants.
    The placeholders are NOLOGIN; workflows that need a login provision it
    themselves before this step.
    """
    if not ci_mode:
        return
    ownership_transfer_needed = _account_owner_state(connection)
    if not ownership_transfer_needed:
        return
    roles = (
        ("app_auth_lookup", "NOLOGIN BYPASSRLS"),
        ("app_account_provisioner", "NOLOGIN BYPASSRLS"),
        ("app_user", "NOLOGIN"),
        ("app_ingress", "NOLOGIN"),
        ("app_worker", "NOLOGIN"),
        ("app_trust_issuer", "NOLOGIN"),
        ("app_ro", "NOLOGIN"),
        ("app_relay", "NOLOGIN"),
    )
    for role, attributes in roles:
        exists = connection.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": role},
        ).scalar()
        if not exists:
            connection.execute(
                text(f'CREATE ROLE "{role}" {attributes}')
            )
    cleanup_grants_needed = True

    current = connection.execute(
        text(
            "SELECT current_user, r.rolsuper FROM pg_roles AS r"
            " WHERE r.rolname = current_user"
        )
    ).fetchone()
    current_role = str(current[0]) if current else ""
    is_superuser = bool(current[1]) if current else False

    def _has_membership(role: str, member: str) -> bool:
        return bool(
            connection.execute(
                text(
                    "SELECT EXISTS ("
                    " SELECT 1 FROM pg_auth_members m"
                    " JOIN pg_roles r ON r.oid = m.roleid"
                    " JOIN pg_roles u ON u.oid = m.member"
                    " WHERE r.rolname = :role AND u.rolname = :member)"
                ),
                {"role": role, "member": member},
            ).scalar()
        )

    def _has_admin(role: str, member: str) -> bool:
        return bool(
            connection.execute(
                text(
                    "SELECT m.admin_option FROM pg_auth_members m"
                    " JOIN pg_roles r ON r.oid = m.roleid"
                    " JOIN pg_roles u ON u.oid = m.member"
                    " WHERE r.rolname = :role AND u.rolname = :member"
                ),
                {"role": role, "member": member},
            ).scalar()
        )

    lookup_admin = is_superuser or _has_admin("app_auth_lookup", current_role)
    if (
        not is_superuser
        and current_role
        and current_role != "app_auth_lookup"
        and not _has_membership("app_auth_lookup", current_role)
    ):
        connection.execute(
            text(
                'GRANT "app_auth_lookup" TO '
                f'"{current_role}" WITH ADMIN OPTION'
            )
        )
        lookup_admin = True

    if (
        (is_superuser or lookup_admin)
        and _has_membership("app_auth_lookup", "app_account_provisioner")
        and not _has_admin("app_auth_lookup", "app_account_provisioner")
    ):
        connection.execute(
            text(
                'GRANT "app_auth_lookup" TO "app_account_provisioner"'
                ' WITH ADMIN OPTION'
            )
        )
    elif (
        ownership_transfer_needed
        and (is_superuser or lookup_admin)
        and not _has_membership("app_auth_lookup", "app_account_provisioner")
    ):
        connection.execute(
            text(
                'GRANT "app_auth_lookup" TO "app_account_provisioner"'
                ' WITH ADMIN OPTION'
            )
        )

    if not is_superuser and current_role:
        if _has_membership("app_account_provisioner", current_role):
            if not _has_admin("app_account_provisioner", current_role):
                connection.execute(
                    text(
                        'GRANT "app_account_provisioner" TO '
                        f'"{current_role}" WITH ADMIN OPTION'
                    )
                )
        elif ownership_transfer_needed:
            connection.execute(
                text(
                    'GRANT "app_account_provisioner" TO '
                    f'"{current_role}" WITH ADMIN OPTION'
                )
            )


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _provision_ci_migration_roles(connection)
        connection.commit()
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()





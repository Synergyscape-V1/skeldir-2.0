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
    roles = (
        ("app_auth_lookup", "NOLOGIN BYPASSRLS"),
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
    # CI lanes migrate as a role that may not yet inherit the lookup owner.
    # The XXV owner-transfer migration requires that inheritance; grant it
    # here for the CI placeholder only. Production uses the governed preflight
    # and never relies on this branch.
    current_role = connection.execute(text("SELECT current_user")).scalar()
    if current_role and current_role != "app_auth_lookup":
        connection.execute(
            text(
                'GRANT "app_auth_lookup" TO '
                f'"{current_role}"'
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





"""Sync database engine factory for Bayesian worker DB paths."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from app.bayesian.db_topology import resolve_bayesian_worker_db_topology_policy
from app.core.secrets import get_database_url
from app.db.dsn import to_sync_postgres_dsn


def runtime_sync_database_url() -> str:
    """Return the runtime database URL normalized for sync SQLAlchemy drivers."""

    return to_sync_postgres_dsn(get_database_url())


def assert_bayesian_worker_engine_nonpooled(engine: Engine) -> None:
    """Fail closed if a Bayesian worker engine can reuse physical connections."""

    if not isinstance(engine.pool, NullPool):
        raise RuntimeError("bayesian_worker_engine_must_use_nullpool")


def create_bayesian_worker_engine(database_url: str | None = None) -> Engine:
    """Create a disposable-connection sync engine for Bayesian worker tasks."""

    resolved_database_url = database_url or runtime_sync_database_url()
    resolve_bayesian_worker_db_topology_policy(resolved_database_url)
    engine = create_engine(
        resolved_database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    assert_bayesian_worker_engine_nonpooled(engine)
    return engine


def create_dispatch_publisher_engine(database_url: str | None = None) -> Engine:
    """Create the dedicated global-dispatch engine and verify DSN custody."""

    raw_url = database_url or os.getenv("B24_DISPATCH_PUBLISHER_DATABASE_URL", "")
    if not raw_url:
        raise RuntimeError("dispatch_publisher_database_url_missing")
    parsed = make_url(raw_url)
    if parsed.username != "app_dispatch_publisher":
        raise RuntimeError("dispatch_publisher_database_principal_mismatch")
    resolved = to_sync_postgres_dsn(raw_url)
    resolve_bayesian_worker_db_topology_policy(resolved)
    engine = create_engine(
        resolved,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    assert_bayesian_worker_engine_nonpooled(engine)
    return engine

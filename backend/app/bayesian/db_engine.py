"""Sync database engine factory for Bayesian worker DB paths."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
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

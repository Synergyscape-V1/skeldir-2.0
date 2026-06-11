"""Sync database engine factory for Bayesian worker DB paths."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from app.bayesian.db_topology import resolve_bayesian_worker_db_topology_policy
from app.core.secrets import get_database_url


def runtime_sync_database_url() -> str:
    """Return the runtime database URL normalized for sync SQLAlchemy drivers."""

    raw_url = get_database_url()
    parsed = make_url(raw_url)
    query = dict(parsed.query)
    query.pop("channel_binding", None)
    parsed = parsed.set(query=query)
    driver = parsed.drivername
    if driver.startswith("postgresql+"):
        driver = "postgresql"
    parsed = parsed.set(drivername=driver)
    dsn_parts = [f"{driver}://"]
    if parsed.username:
        dsn_parts.append(parsed.username)
        if parsed.password:
            dsn_parts.append(":")
            dsn_parts.append(parsed.password)
        dsn_parts.append("@")
    dsn_parts.append(parsed.host or "localhost")
    if parsed.port:
        dsn_parts.append(f":{parsed.port}")
    if parsed.database:
        dsn_parts.append(f"/{parsed.database}")
    return "".join(dsn_parts)


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

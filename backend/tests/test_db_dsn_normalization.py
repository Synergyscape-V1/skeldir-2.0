from __future__ import annotations

import pytest

from app.db.dsn import to_asyncpg_postgres_dsn, to_sync_postgres_dsn


def test_to_sync_postgres_dsn_normalizes_asyncpg_scheme() -> None:
    dsn = "postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir"
    assert to_sync_postgres_dsn(dsn) == "postgresql://app_user:app_user@127.0.0.1:5432/skeldir"


def test_to_asyncpg_postgres_dsn_normalizes_sync_scheme() -> None:
    dsn = "postgresql://app_user:app_user@127.0.0.1:5432/skeldir"
    assert (
        to_asyncpg_postgres_dsn(dsn)
        == "postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir"
    )


def test_dsn_normalization_rejects_non_postgres_scheme() -> None:
    with pytest.raises(ValueError, match="Unsupported PostgreSQL DSN scheme"):
        to_sync_postgres_dsn("sqlite:///tmp/test.db")

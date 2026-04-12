"""
Canonical PostgreSQL DSN normalization helpers.

These helpers provide a single authority surface for runtime/test tooling that
must move between async (SQLAlchemy asyncpg) and sync (Alembic/psycopg2)
connection schemes without changing credentials or host/database targets.
"""

from __future__ import annotations


def to_sync_postgres_dsn(dsn: str) -> str:
    """Normalize a PostgreSQL DSN to a sync driver form."""
    value = (dsn or "").strip()
    if not value:
        raise ValueError("DSN must be a non-empty PostgreSQL URL")
    if value.startswith("postgresql+asyncpg://"):
        return value.replace("postgresql+asyncpg://", "postgresql://", 1)
    if value.startswith("postgresql+psycopg2://"):
        return value.replace("postgresql+psycopg2://", "postgresql://", 1)
    if value.startswith("postgresql://"):
        return value
    raise ValueError(f"Unsupported PostgreSQL DSN scheme: {value.split('://', 1)[0]}")


def to_asyncpg_postgres_dsn(dsn: str) -> str:
    """Normalize a PostgreSQL DSN to an asyncpg driver form."""
    value = (dsn or "").strip()
    if not value:
        raise ValueError("DSN must be a non-empty PostgreSQL URL")
    if value.startswith("postgresql+asyncpg://"):
        return value
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    if value.startswith("postgresql+psycopg2://"):
        return value.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    raise ValueError(f"Unsupported PostgreSQL DSN scheme: {value.split('://', 1)[0]}")

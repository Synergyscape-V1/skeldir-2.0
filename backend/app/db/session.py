"""
Async database session management with tenant-aware RLS context.

This module exposes a pooled SQLAlchemy async engine and a session factory that
applies the `app.current_tenant_id` session variable required for PostgreSQL
row-level security enforcement.
"""

from __future__ import annotations

import os
import ssl
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.identity import resolve_user_id


# Normalize DSN to ensure asyncpg driver is used and map unsupported parameters to connect_args.
def _build_async_database_url_and_args() -> tuple[str, dict]:
    raw_url = settings.DATABASE_URL.unicode_string()
    parsed = urlsplit(raw_url)
    query_params = dict(parse_qsl(parsed.query))

    ssl_mode = query_params.pop("sslmode", None)
    channel_binding = query_params.pop("channel_binding", None)

    sanitized = urlunsplit(
        parsed._replace(query=urlencode(query_params))
    )
    if sanitized.startswith("postgresql://"):
        sanitized = sanitized.replace("postgresql://", "postgresql+asyncpg://", 1)

    connect_args: dict = {}
    if ssl_mode:
        # asyncpg expects an SSL context rather than sslmode keyword.
        connect_args["ssl"] = ssl.create_default_context()
    if channel_binding:
        connect_args.setdefault("server_settings", {})["channel_binding"] = channel_binding

    return sanitized, connect_args


_ASYNC_DATABASE_URL, _CONNECT_ARGS = _build_async_database_url_and_args()
_FORCE_POOLING = os.getenv("DATABASE_FORCE_POOLING", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_USE_NULL_POOL = (
    os.getenv("TESTING") == "1" or settings.ENVIRONMENT.lower() == "test"
) and not _FORCE_POOLING

engine_kwargs = {
    "connect_args": _CONNECT_ARGS,
    "pool_pre_ping": True,
    "echo": False,
}

if _USE_NULL_POOL:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

# Engine is configured for asyncpg with explicit pool sizing controls.
engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    **engine_kwargs,
)

# Factory for tenant-scoped async sessions.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_session(
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async session with tenant context set for RLS enforcement.

    The session variables `app.current_tenant_id` and `app.current_user_id` are
    set before yielding the session so all subsequent queries evaluate row-level
    policies correctly.
    Session lifecycle is managed automatically with rollback on exception and
    closure on exit.
    """
    async with AsyncSessionLocal() as session:
        resolved_user_id = resolve_user_id(user_id)
        await session.execute(
            text(
                "SELECT set_config('app.current_tenant_id', :tenant_id, false)"
            ),
            {"tenant_id": str(tenant_id)},
        )
        await session.execute(
            text(
                "SELECT set_config('app.current_user_id', :user_id, false)"
            ),
            {"user_id": str(resolved_user_id)},
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def validate_database_connection() -> None:
    """
    Execute a lightweight connectivity check against the database.

    Intended for startup health checks; raises SQLAlchemyError on failure.
    """
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Re-raise to allow caller to handle/log as appropriate.
        raise


async def set_tenant_guc_async(
    session: AsyncConnection | AsyncSession, tenant_id: UUID, local: bool = True
) -> None:
    """
    Async helper to set tenant context (app.current_tenant_id) on an existing session/connection.

    Args:
        session: AsyncSession/AsyncConnection to mutate
        tenant_id: UUID tenant context value
        local: use SET LOCAL (transaction-scoped) when True; otherwise session-scoped
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, :is_local)"),
        {"tenant_id": str(tenant_id), "is_local": local},
    )


async def set_user_guc_async(
    session: AsyncConnection | AsyncSession, user_id: UUID, local: bool = True
) -> None:
    """
    Async helper to set user context (app.current_user_id) on an existing session/connection.
    """
    await session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, :is_local)"),
        {"user_id": str(user_id), "is_local": local},
    )


def set_tenant_guc_sync(
    session: Connection, tenant_id: UUID, local: bool = True
) -> None:
    """
    Sync helper to set tenant context (app.current_tenant_id) on an existing sync connection.

    This avoids running async DB calls through ad-hoc event loops when executing in
    synchronous contexts (e.g., Celery worker threads).
    """
    session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, :is_local)"),
        {"tenant_id": str(tenant_id), "is_local": local},
    )


def set_user_guc_sync(
    session: Connection, user_id: UUID, local: bool = True
) -> None:
    """
    Sync helper to set user context (app.current_user_id) on an existing sync connection.
    """
    session.execute(
        text("SELECT set_config('app.current_user_id', :user_id, :is_local)"),
        {"user_id": str(user_id), "is_local": local},
    )


# Backwards-compatible alias for existing async callers.
async def set_tenant_guc(session: AsyncSession, tenant_id: UUID, local: bool = True) -> None:
    await set_tenant_guc_async(session, tenant_id, local)


async def set_user_guc(session: AsyncSession, user_id: UUID, local: bool = True) -> None:
    await set_user_guc_async(session, user_id, local)

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

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SyncSession

from app.core.config import settings
from app.core.identity import resolve_user_id
from app.core.secrets import get_database_url
from app.observability.context import get_tenant_id, get_user_id

_SESSION_INFO_TENANT_ID = "_skeldir_tenant_id"
_SESSION_INFO_USER_ID = "_skeldir_user_id"

# Mutation toggles used by CI negative controls.
_MUTATION_FORCE_SESSION_SCOPED = "SKELDIR_B12_FORCE_SESSION_SCOPED_GUC"
_MUTATION_DISABLE_TX_ENVELOPE = "SKELDIR_B12_DISABLE_TRANSACTION_ENVELOPE"
_MUTATION_DISABLE_AFTER_BEGIN_BINDING = "SKELDIR_B12_DISABLE_AFTER_BEGIN_GUC_BINDING"


# Normalize DSN to ensure asyncpg driver is used and map unsupported parameters to connect_args.
def _build_async_database_url_and_args() -> tuple[str, dict]:
    raw_url = get_database_url()
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


def _resolve_guc_value(session: SyncSession, key: str, context_value: str | None) -> str | None:
    value = session.info.get(key)
    if value is not None:
        return str(value)
    if context_value:
        return str(context_value)
    return None


@event.listens_for(AsyncSession.sync_session_class, "after_begin")
def _bind_rls_context_after_begin(session: SyncSession, transaction, connection) -> None:
    if os.getenv(_MUTATION_DISABLE_AFTER_BEGIN_BINDING) == "1":
        return

    tenant_id = _resolve_guc_value(session, _SESSION_INFO_TENANT_ID, get_tenant_id())
    user_id = _resolve_guc_value(session, _SESSION_INFO_USER_ID, get_user_id())
    if tenant_id is None and user_id is None:
        return

    is_local = os.getenv(_MUTATION_FORCE_SESSION_SCOPED) != "1"
    if tenant_id is not None:
        connection.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, :is_local)"),
            {"tenant_id": tenant_id, "is_local": is_local},
        )
    if user_id is not None:
        connection.execute(
            text("SELECT set_config('app.current_user_id', :user_id, :is_local)"),
            {"user_id": user_id, "is_local": is_local},
        )


@asynccontextmanager
async def get_session(
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async session with tenant context set for RLS enforcement.

    Tenant/user GUC binding is event-driven and executes after BEGIN on the same
    connection that runs subsequent SQL. This guarantees transaction-local scope.
    """
    async with AsyncSessionLocal() as session:
        resolved_user_id = resolve_user_id(user_id)
        session.info[_SESSION_INFO_TENANT_ID] = str(tenant_id)
        session.info[_SESSION_INFO_USER_ID] = str(resolved_user_id)

        if os.getenv(_MUTATION_DISABLE_TX_ENVELOPE) == "1":
            # Intentional unsafe path for CI mutation tests.
            yield session
            return

        async with session.begin():
            yield session


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

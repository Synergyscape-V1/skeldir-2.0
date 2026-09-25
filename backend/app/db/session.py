"""
Async database session management with tenant-aware RLS context.

This module exposes a pooled SQLAlchemy async engine and a session factory that
applies the `app.current_tenant_id` session variable required for PostgreSQL
row-level security enforcement.
"""

from __future__ import annotations

import contextvars as _ctxvars
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
_SESSION_INFO_B23_TIMEOUTS = "_skeldir_b23_timeouts"

# Mutation toggles used by CI negative controls.
_MUTATION_FORCE_SESSION_SCOPED = "SKELDIR_B12_FORCE_SESSION_SCOPED_GUC"
_MUTATION_DISABLE_TX_ENVELOPE = "SKELDIR_B12_DISABLE_TRANSACTION_ENVELOPE"
_MUTATION_DISABLE_AFTER_BEGIN_BINDING = "SKELDIR_B12_DISABLE_AFTER_BEGIN_GUC_BINDING"


class MissingTenantContextError(RuntimeError):
    """Raised when domain DB access is attempted without tenant RLS context."""


def assert_tenant_context_present(tenant_id: UUID | str | None) -> None:
    """Fail visibly before tenant-scoped domain logic can consume raw RLS zero rows."""
    if tenant_id is None or str(tenant_id).strip() == "":
        raise MissingTenantContextError("tenant context is required for tenant-scoped database access")


# Normalize DSN to ensure asyncpg driver is used and map unsupported parameters to connect_args.
def _build_async_database_url_and_args(raw_url: str | None = None) -> tuple[str, dict]:
    raw_url = raw_url or get_database_url()
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
    if os.getenv("SKELDIR_ASYNCPG_DISABLE_STATEMENT_CACHE", "0") == "1":
        connect_args["statement_cache_size"] = 0

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
    engine_kwargs["pool_timeout"] = settings.DATABASE_POOL_TIMEOUT_SECONDS

# Engine is configured for asyncpg with explicit pool sizing controls.
engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    **engine_kwargs,
)

# B2.6-P2 Corrective III: the B2.3 pool may run under a dedicated worker
# credential (least privilege: API issues dispatch authority as app_user,
# the worker authors verdicts as app_worker). Unset preserves the exact
# historical behavior (worker pool shares the application DSN), so
# production topology without the variable is byte-for-byte unaffected.
#
# B2.6-P2 Corrective IV: the deployed worker_b23 process sets
# SKELDIR_B23_REQUIRE_WORKER_DSN=1 (Procfile). Under that flag an unset
# B23_WORKER_DATABASE_URL fails closed at import with a legible error
# instead of silently inheriting the producer DSN (which would hand the
# consumer full authority-mint capability while breaking every verdict
# write). No other process sets the flag, so historical defaults elsewhere
# are unaffected.
_B23_WORKER_DATABASE_URL = os.getenv("B23_WORKER_DATABASE_URL", "").strip()
if os.getenv("SKELDIR_B23_REQUIRE_WORKER_DSN", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
} and not _B23_WORKER_DATABASE_URL:
    raise RuntimeError(
        "b23_worker_dsn_required:"
        " SKELDIR_B23_REQUIRE_WORKER_DSN is set but B23_WORKER_DATABASE_URL is empty;"
        " the B2.3 worker must not inherit the producer DSN"
    )
if _B23_WORKER_DATABASE_URL:
    _B23_ASYNC_DATABASE_URL, _B23_CONNECT_ARGS = _build_async_database_url_and_args(
        _B23_WORKER_DATABASE_URL
    )
else:
    _B23_ASYNC_DATABASE_URL, _B23_CONNECT_ARGS = _ASYNC_DATABASE_URL, _CONNECT_ARGS

b23_engine = create_async_engine(
    _B23_ASYNC_DATABASE_URL,
    connect_args=_B23_CONNECT_ARGS,
    pool_pre_ping=True,
    echo=False,
    pool_size=settings.B23_DATABASE_POOL_SIZE,
    max_overflow=settings.B23_DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.B23_DATABASE_POOL_TIMEOUT_SECONDS,
)

# Factory for tenant-scoped async sessions.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

B23AsyncSessionLocal = async_sessionmaker(
    bind=b23_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# B2.6-P2 Corrective XI: dedicated authenticated-ingress pool. Only the
# API ingress boundary mounts B26_P2_INGRESS_DATABASE_URL; the engine is
# absent everywhere else (get_ingress_session fails closed). The
# after_begin RLS binding below applies to these sessions through the
# shared AsyncSession event listener, keyed off session.info tenant.
_B26_P2_INGRESS_DATABASE_URL = os.getenv("B26_P2_INGRESS_DATABASE_URL", "").strip()
if _B26_P2_INGRESS_DATABASE_URL:
    _INGRESS_ASYNC_DATABASE_URL, _INGRESS_CONNECT_ARGS = (
        _build_async_database_url_and_args(_B26_P2_INGRESS_DATABASE_URL)
    )
    # Mirror the application pool discipline exactly (including the
    # test NullPool convention): pooled connections must never migrate
    # across event loops, or post-commit finalizers reuse a connection
    # bound to a closed loop.
    _ingress_engine_kwargs: dict = {
        "connect_args": _INGRESS_CONNECT_ARGS,
        "pool_pre_ping": True,
        "echo": False,
    }
    if _USE_NULL_POOL:
        _ingress_engine_kwargs["poolclass"] = NullPool
    else:
        _ingress_engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
        _ingress_engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
        _ingress_engine_kwargs["pool_timeout"] = (
            settings.DATABASE_POOL_TIMEOUT_SECONDS
        )
    ingress_engine = create_async_engine(
        _INGRESS_ASYNC_DATABASE_URL,
        **_ingress_engine_kwargs,
    )
    IngressAsyncSessionLocal = async_sessionmaker(
        bind=ingress_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
else:
    ingress_engine = None
    IngressAsyncSessionLocal = None


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
    if session.info.get(_SESSION_INFO_B23_TIMEOUTS) is True:
        connection.execute(
            text(
                f"SET LOCAL statement_timeout = '{int(settings.B23_DATABASE_STATEMENT_TIMEOUT_MS)}ms'"
            ),
        )
        connection.execute(
            text(f"SET LOCAL lock_timeout = '{int(settings.B23_DATABASE_LOCK_TIMEOUT_MS)}ms'"),
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
    assert_tenant_context_present(tenant_id)
    async with AsyncSessionLocal() as session:
        resolved_user_id = resolve_user_id(user_id)
        session.info[_SESSION_INFO_TENANT_ID] = str(tenant_id)
        session.info[_SESSION_INFO_USER_ID] = str(resolved_user_id)

        if os.getenv(_MUTATION_DISABLE_TX_ENVELOPE) != "1":
            await session.begin()
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


@asynccontextmanager
async def get_b23_session(
    tenant_id: UUID,
    user_id: UUID | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a tenant-scoped B2.3 session backed by the dedicated B2.3 DB pool.

    Batch and transition workers use this pool so adjacent app workloads cannot
    consume every application DB connection before B2.3 can fail fast or proceed.
    """
    assert_tenant_context_present(tenant_id)
    async with B23AsyncSessionLocal() as session:
        resolved_user_id = resolve_user_id(user_id)
        session.info[_SESSION_INFO_TENANT_ID] = str(tenant_id)
        session.info[_SESSION_INFO_USER_ID] = str(resolved_user_id)
        session.info[_SESSION_INFO_B23_TIMEOUTS] = True

        if os.getenv(_MUTATION_DISABLE_TX_ENVELOPE) != "1":
            await session.begin()
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


class IngressBoundaryError(RuntimeError):
    """Raised when non-authentication code attempts ingress capability."""


# B2.6-P2 Corrective XII (Blocker B): the ingress capability is bound to
# the actual authentication execution boundary, not to the process. The
# HMAC-verified webhook path sets this context immediately after a
# successful provider-signature verification; get_ingress_session
# requires it. An unrelated API route or a generic worker process never
# holds the token, so the session is unavailable at the process level,
# not merely unused by convention. Context-local: never crosses tasks.
_ingress_auth_boundary: _ctxvars.ContextVar[bool] = _ctxvars.ContextVar(
    "b26_p2_ingress_auth_boundary", default=False
)


def enter_ingress_auth_boundary() -> None:
    """Mark the current task as the authentication execution boundary."""
    _ingress_auth_boundary.set(True)


def exit_ingress_auth_boundary() -> None:
    """Leave the authentication execution boundary."""
    _ingress_auth_boundary.set(False)


@asynccontextmanager
async def _ingress_boundary() -> AsyncGenerator[None, None]:
    """Scoped authentication-execution-boundary marker.

    B2.6-P2 Corrective XII: the post-commit finalizer runs downstream
    of a successful HMAC verification in the same task; this scopes
    the ingress-session capability to that dynamic extent.
    """
    enter_ingress_auth_boundary()
    try:
        yield
    finally:
        exit_ingress_auth_boundary()


def _require_ingress_auth_boundary() -> None:
    if _ingress_auth_boundary.get() is not True:
        raise IngressBoundaryError(
            "b26_p2_ingress_out_of_boundary: ingress capability is"
            " available only inside the provider-authentication"
            " execution boundary"
        )


def assert_worker_ingress_isolation() -> None:
    """Fail closed when a non-ingress worker inherits the ingress DSN.

    B2.6-P2 Corrective XII: the ingress credential must not exist in a
    generic worker/relay/beat/B2.3 process environment. Called at worker
    startup; raises instead of serving with a smuggled capability.
    """
    if os.getenv("B26_P2_INGRESS_DATABASE_URL", "").strip():
        raise RuntimeError(
            "b26_p2_ingress_credential_in_worker: B26_P2_INGRESS_DATABASE_URL"
            " must not be present in worker/relay/beat/B2.3 environments"
        )


def ingress_credential_mounted() -> bool:
    """True when this process was given the ingress credential."""
    return bool(os.getenv("B26_P2_INGRESS_DATABASE_URL", "").strip())


_SANITIZED_INGRESS_DSN: str | None = None


def sanitize_worker_ingress_environment() -> bool:
    """Drop a smuggled ingress credential string from this process.

    B2.6-P2 Corrective XII: worker/relay/beat/B2.3 startup calls this
    before serving. When the credential string was inherited through a
    shared environment, it is removed from ``os.environ`` so worker
    code cannot read and redial it; the saved value is restored on
    worker shutdown (in-process test workers share their process with
    the API boundary, which legitimately keeps the credential).
    Deliberately scoped to the environment only: already-constructed
    pools are left intact, and spending the pool additionally requires
    the authentication-boundary token (never set here) while the
    database denies every non-ingress principal regardless. Returns
    True when sanitization occurred (callers log CRITICAL). Governed
    topologies blank the variable outright, where this is a no-op.
    """
    global _SANITIZED_INGRESS_DSN
    current = os.getenv("B26_P2_INGRESS_DATABASE_URL", "").strip()
    if not current:
        return False
    if _SANITIZED_INGRESS_DSN is None:
        _SANITIZED_INGRESS_DSN = os.environ.get("B26_P2_INGRESS_DATABASE_URL")
    os.environ.pop("B26_P2_INGRESS_DATABASE_URL", None)
    return True


def restore_worker_ingress_environment() -> bool:
    """Restore a credential string sanitized at worker startup.

    Fires on worker shutdown: real worker processes exit, making this
    a no-op in production, while in-process test workers return the
    shared process to its prior state. Returns True when restored.
    """
    global _SANITIZED_INGRESS_DSN
    if _SANITIZED_INGRESS_DSN is None:
        return False
    os.environ["B26_P2_INGRESS_DATABASE_URL"] = _SANITIZED_INGRESS_DSN
    _SANITIZED_INGRESS_DSN = None
    return True


@asynccontextmanager
async def get_ingress_session(
    tenant_id: UUID,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a tenant-scoped session backed by the dedicated ingress pool.

    B2.6-P2 Corrective XI: only the authenticated-ingress boundary holds
    the ingress credential, so only it can author authenticity_verified
    and record witnesses. Fails closed when the DSN is not mounted.

    B2.6-P2 Corrective XII: additionally requires the caller to be the
    actual authentication execution boundary (HMAC verification just
    ran in this task). Unrelated in-process code without that context
    cannot obtain the session.
    """
    _require_ingress_auth_boundary()
    if IngressAsyncSessionLocal is None:
        raise RuntimeError(
            "b26_p2_ingress_credential_unavailable: verified arrival"
            " requires B26_P2_INGRESS_DATABASE_URL"
        )
    assert_tenant_context_present(tenant_id)
    async with IngressAsyncSessionLocal() as session:
        session.info[_SESSION_INFO_TENANT_ID] = str(tenant_id)
        if os.getenv(_MUTATION_DISABLE_TX_ENVELOPE) != "1":
            await session.begin()
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


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

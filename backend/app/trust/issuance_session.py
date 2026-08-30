"""Dedicated database custody for issuance-consequence transitions.

B2.5-P13 Corrective XVI (XVI-B).

Recording that an issuance completed is the act of asserting that a private key
physically produced a signature. Audit 58's Finding 2 established that shape
constraints alone cannot carry that assertion: the ordinary ``app_user`` runtime
principal could turn a structurally plausible row into authoritative completed
history, because any principal able to write the row can also write correctly
shaped bytes.

The database therefore narrows the transition authority to one dedicated login
principal, ``app_trust_issuer`` (see the C16 migration's
``trust_access_log_issuance_authority_guard`` trigger, which keys on
``session_user`` -- a value ``SET ROLE`` cannot forge). This module is the
application half of that boundary: the only place that opens a connection under
that principal, and the only session factory the issuance-state writes in
``app.trust.audit`` may use.

If ``TRUST_ISSUANCE_DATABASE_URL`` is not configured, this module deliberately
falls back to the ordinary runtime DSN. That is not a bypass: against a
provisioned schema the trigger then refuses every consequence-bearing
transition, so the deployment fails closed and loudly rather than silently
issuing with ordinary authority.
"""

from __future__ import annotations

import os
import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.secrets import get_database_url

TRUST_ISSUANCE_DATABASE_URL_ENV = "TRUST_ISSUANCE_DATABASE_URL"
TRUST_ISSUANCE_PRINCIPAL = "app_trust_issuer"

_issuance_engine = None
_issuance_session_factory: async_sessionmaker[AsyncSession] | None = None


def trust_issuance_database_url() -> str:
    """Resolve the DSN the issuance principal connects with."""
    configured = os.getenv(TRUST_ISSUANCE_DATABASE_URL_ENV, "").strip()
    return configured or get_database_url()


def trust_issuance_custody_is_separated() -> bool:
    """Report whether issuance authority has its own DSN in this process."""
    return bool(os.getenv(TRUST_ISSUANCE_DATABASE_URL_ENV, "").strip())


def _to_async_dsn(raw_url: str) -> tuple[str, dict]:
    parsed = urlsplit(raw_url)
    query_params = dict(parse_qsl(parsed.query))
    ssl_mode = query_params.pop("sslmode", None)
    channel_binding = query_params.pop("channel_binding", None)
    sanitized = urlunsplit(parsed._replace(query=urlencode(query_params)))
    if sanitized.startswith("postgresql://"):
        sanitized = sanitized.replace("postgresql://", "postgresql+asyncpg://", 1)

    connect_args: dict = {}
    if ssl_mode:
        connect_args["ssl"] = ssl.create_default_context()
    if channel_binding:
        connect_args.setdefault("server_settings", {})[
            "channel_binding"
        ] = channel_binding
    if os.getenv("SKELDIR_ASYNCPG_DISABLE_STATEMENT_CACHE", "0") == "1":
        connect_args["statement_cache_size"] = 0
    return sanitized, connect_args


def trust_issuance_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide issuance session factory, building it once.

    Construction is lazy so that a test or CI job can set
    ``TRUST_ISSUANCE_DATABASE_URL`` after import, and so that a process which
    never issues never opens a connection under the issuance principal.
    """
    global _issuance_engine, _issuance_session_factory

    resolved_url = trust_issuance_database_url()
    if (
        _issuance_session_factory is not None
        and getattr(_issuance_session_factory, "_skeldir_source_dsn", None)
        == resolved_url
    ):
        return _issuance_session_factory

    async_url, connect_args = _to_async_dsn(resolved_url)
    force_pooling = os.getenv("DATABASE_FORCE_POOLING", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    use_null_pool = (
        os.getenv("TESTING") == "1" or settings.ENVIRONMENT.lower() == "test"
    ) and not force_pooling

    engine_kwargs: dict = {
        "connect_args": connect_args,
        "pool_pre_ping": True,
        "echo": False,
    }
    if use_null_pool:
        engine_kwargs["poolclass"] = NullPool
    else:
        # Issuance writes are short, serial, and rare relative to reads, so this
        # custody boundary intentionally holds a small pool of its own rather
        # than borrowing the API pool's sizing.
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 5
        engine_kwargs["pool_timeout"] = settings.DATABASE_POOL_TIMEOUT_SECONDS

    if _issuance_engine is not None:
        _issuance_engine.sync_engine.dispose()

    _issuance_engine = create_async_engine(async_url, **engine_kwargs)
    factory = async_sessionmaker(
        bind=_issuance_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    factory._skeldir_source_dsn = resolved_url  # type: ignore[attr-defined]
    _issuance_session_factory = factory
    return factory


async def dispose_trust_issuance_engine() -> None:
    """Release the issuance engine's connections (test and shutdown paths)."""
    global _issuance_engine, _issuance_session_factory
    if _issuance_engine is not None:
        await _issuance_engine.dispose()
    _issuance_engine = None
    _issuance_session_factory = None

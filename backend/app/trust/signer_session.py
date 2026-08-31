"""Dedicated database custody for signer-produced consequence evidence."""

from __future__ import annotations

import os
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.trust.issuance_session import _build_session_factory


TRUST_SIGNER_DATABASE_URL_ENV = "TRUST_SIGNER_DATABASE_URL"
TRUST_SIGNER_PRINCIPAL = "app_trust_signer"

_signer_engine = None
_signer_session_factory: async_sessionmaker[AsyncSession] | None = None


def trust_signer_database_url() -> str:
    """Resolve the DSN held only by the governed signing consequence path."""
    configured = os.getenv(TRUST_SIGNER_DATABASE_URL_ENV, "").strip()
    if not configured:
        raise RuntimeError("trust_signer_database_url_required")
    return configured


def trust_signer_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return signer custody only to the audit persistence boundary."""
    caller = sys._getframe(1).f_globals.get("__name__", "")
    if caller != "app.trust.audit":
        raise RuntimeError(
            f"trust_signer_session_untrusted_caller:{caller or 'unknown'}"
        )

    global _signer_engine, _signer_session_factory
    resolved_url = trust_signer_database_url()
    if (
        _signer_session_factory is not None
        and getattr(_signer_session_factory, "_skeldir_source_dsn", None)
        == resolved_url
    ):
        return _signer_session_factory
    _signer_engine, _signer_session_factory = _build_session_factory(
        resolved_url,
        previous_engine=_signer_engine,
    )
    return _signer_session_factory


async def dispose_trust_signer_engine() -> None:
    """Release signer-custody connections in tests and shutdown paths."""
    global _signer_engine, _signer_session_factory
    if _signer_engine is not None:
        await _signer_engine.dispose()
    _signer_engine = None
    _signer_session_factory = None

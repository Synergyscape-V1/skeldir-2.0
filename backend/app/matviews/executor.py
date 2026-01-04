"""
Unified materialized view refresh executor.

Enforces registry validation, xact-scoped advisory locks, and standardized
RefreshResult telemetry for all refresh paths.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.url import make_url
from sqlalchemy.sql.compiler import IdentifierPreparer

from app.core.pg_locks import RefreshLockKey, build_refresh_lock_key, try_acquire_refresh_xact_lock
from app.db.session import engine, set_tenant_guc
from app.matviews import registry

logger = logging.getLogger(__name__)
_IDENTIFIER_PREPARER = IdentifierPreparer(postgresql.dialect())
_PUBLIC_SCHEMA = _IDENTIFIER_PREPARER.quote_schema("public")


class RefreshOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    SKIPPED_LOCK_HELD = "SKIPPED_LOCK_HELD"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RefreshResult:
    view_name: str
    tenant_id: Optional[UUID]
    correlation_id: Optional[str]
    outcome: RefreshOutcome
    started_at: datetime
    duration_ms: int
    error_type: Optional[str]
    error_message: Optional[str]
    lock_key_debug: Optional[RefreshLockKey]

    def to_log_dict(self) -> dict:
        return {
            "view_name": self.view_name,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "correlation_id": self.correlation_id,
            "outcome": self.outcome.value,
            "started_at": self.started_at.isoformat(),
            "duration_ms": self.duration_ms,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "lock_key_debug": self.lock_key_debug.as_dict() if self.lock_key_debug else None,
        }


def _qualified_matview_identifier(view_name: str) -> str:
    registry.get_entry(view_name)
    quoted_view = _IDENTIFIER_PREPARER.quote(view_name)
    return f"{_PUBLIC_SCHEMA}.{quoted_view}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _build_sync_dsn() -> str:
    from app.core.config import settings
    url = make_url(settings.DATABASE_URL.unicode_string())
    query = dict(url.query)
    query.pop("channel_binding", None)
    url = url.set(query=query)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")

    dsn_parts = ["postgresql://"]
    if url.username:
        dsn_parts.append(url.username)
        if url.password:
            dsn_parts.append(":")
            dsn_parts.append(url.password)
        dsn_parts.append("@")
    dsn_parts.append(url.host or "localhost")
    if url.port:
        dsn_parts.append(f":{url.port}")
    if url.database:
        dsn_parts.append(f"/{url.database}")
    return "".join(dsn_parts)


def _topological_order(entries: Iterable[registry.MatviewRegistryEntry]) -> list[registry.MatviewRegistryEntry]:
    graph = {entry.name: set(entry.dependencies) for entry in entries}
    ordered: list[registry.MatviewRegistryEntry] = []
    registry_map = {entry.name: entry for entry in entries}

    while graph:
        ready = sorted(name for name, deps in graph.items() if not deps)
        if not ready:
            cycle = ",".join(sorted(graph.keys()))
            raise ValueError(f"Matview registry dependency cycle: {cycle}")
        for name in ready:
            ordered.append(registry_map[name])
            graph.pop(name, None)
            for deps in graph.values():
                deps.discard(name)

    return ordered


async def refresh_single_async(
    view_name: str,
    tenant_id: Optional[UUID],
    correlation_id: Optional[str] = None,
) -> RefreshResult:
    """
    Refresh a single materialized view with registry validation and xact lock.
    """
    entry = registry.get_entry(view_name)
    started_at = _now_utc()
    lock_key: Optional[RefreshLockKey] = None

    try:
        qualified_view = _qualified_matview_identifier(view_name)
        async with engine.begin() as conn:
            if tenant_id:
                await set_tenant_guc(conn, tenant_id, local=True)

            acquired, lock_key = await try_acquire_refresh_xact_lock(conn, view_name, tenant_id)
            if not acquired:
                return RefreshResult(
                    view_name=view_name,
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    outcome=RefreshOutcome.SKIPPED_LOCK_HELD,
                    started_at=started_at,
                    duration_ms=int((_now_utc() - started_at).total_seconds() * 1000),
                    error_type=None,
                    error_message=None,
                    lock_key_debug=lock_key,
                )

            if entry.refresh_fn:
                result = entry.refresh_fn()
                if asyncio.iscoroutine(result):
                    await result
            else:
                if not entry.refresh_sql:
                    raise ValueError(f"View '{view_name}' missing refresh_sql")
                refresh_sql = entry.refresh_sql.format(qualified_name=qualified_view)
                await conn.execute(text(refresh_sql))

        duration_ms = int((_now_utc() - started_at).total_seconds() * 1000)
        return RefreshResult(
            view_name=view_name,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            outcome=RefreshOutcome.SUCCESS,
            started_at=started_at,
            duration_ms=duration_ms,
            error_type=None,
            error_message=None,
            lock_key_debug=lock_key,
        )
    except Exception as exc:
        duration_ms = int((_now_utc() - started_at).total_seconds() * 1000)
        logger.error(
            "matview_refresh_executor_failed",
            exc_info=exc,
            extra={
                "view_name": view_name,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "correlation_id": correlation_id,
            },
        )
        return RefreshResult(
            view_name=view_name,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            outcome=RefreshOutcome.FAILED,
            started_at=started_at,
            duration_ms=duration_ms,
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            lock_key_debug=lock_key,
        )


def refresh_single(
    view_name: str,
    tenant_id: Optional[UUID],
    correlation_id: Optional[str] = None,
) -> RefreshResult:
    """
    Synchronous wrapper for refresh_single_async.
    """
    import psycopg2

    entry = registry.get_entry(view_name)
    started_at = _now_utc()
    lock_key: Optional[RefreshLockKey] = None

    try:
        qualified_view = _qualified_matview_identifier(view_name)
        dsn = _build_sync_dsn()
        conn = psycopg2.connect(dsn)
        try:
            cur = conn.cursor()
            if tenant_id:
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (str(tenant_id),),
                )
            cur.execute(
                "SELECT set_config('app.execution_context', 'worker', true)"
            )

            lock_key = build_refresh_lock_key(view_name, tenant_id)
            cur.execute(
                "SELECT pg_try_advisory_xact_lock(%s, %s)",
                (lock_key.view_key, lock_key.tenant_key),
            )
            acquired = bool(cur.fetchone()[0])
            if not acquired:
                conn.rollback()
                return RefreshResult(
                    view_name=view_name,
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    outcome=RefreshOutcome.SKIPPED_LOCK_HELD,
                    started_at=started_at,
                    duration_ms=int((_now_utc() - started_at).total_seconds() * 1000),
                    error_type=None,
                    error_message=None,
                    lock_key_debug=lock_key,
                )

            if entry.refresh_fn:
                result = entry.refresh_fn()
                if asyncio.iscoroutine(result):
                    raise RuntimeError("refresh_fn returned coroutine in sync executor")
            else:
                if not entry.refresh_sql:
                    raise ValueError(f"View '{view_name}' missing refresh_sql")
                refresh_sql = entry.refresh_sql.format(qualified_name=qualified_view)
                cur.execute(refresh_sql)

            conn.commit()
        finally:
            conn.close()

        duration_ms = int((_now_utc() - started_at).total_seconds() * 1000)
        return RefreshResult(
            view_name=view_name,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            outcome=RefreshOutcome.SUCCESS,
            started_at=started_at,
            duration_ms=duration_ms,
            error_type=None,
            error_message=None,
            lock_key_debug=lock_key,
        )
    except Exception as exc:
        duration_ms = int((_now_utc() - started_at).total_seconds() * 1000)
        logger.error(
            "matview_refresh_executor_failed",
            exc_info=exc,
            extra={
                "view_name": view_name,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "correlation_id": correlation_id,
            },
        )
        return RefreshResult(
            view_name=view_name,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            outcome=RefreshOutcome.FAILED,
            started_at=started_at,
            duration_ms=duration_ms,
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            lock_key_debug=lock_key,
        )


async def refresh_all_for_tenant_async(
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
) -> list[RefreshResult]:
    entries = _topological_order(registry.list_entries())
    results: list[RefreshResult] = []
    for entry in entries:
        results.append(await refresh_single_async(entry.name, tenant_id, correlation_id))
    return results


def refresh_all_for_tenant(
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
) -> list[RefreshResult]:
    """
    Synchronous wrapper to refresh all matviews for a tenant.
    """
    entries = _topological_order(registry.list_entries())
    results: list[RefreshResult] = []
    for entry in entries:
        results.append(refresh_single(entry.name, tenant_id, correlation_id))
    return results

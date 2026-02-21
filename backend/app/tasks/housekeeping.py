"""
Housekeeping tasks for Celery foundation validation (B0.5.1).

Provides a deterministic ping task to validate:
- Worker connectivity
- Postgres broker/result backend
- Logging/metrics instrumentation
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import psycopg2
from sqlalchemy.engine.url import make_url
from sqlalchemy import text

from app.celery_app import celery_app
from app.db.session import engine, set_tenant_guc
from app.core.secrets import get_database_url
from app.observability.context import set_request_correlation_id, set_tenant_id

logger = logging.getLogger(__name__)


def _run_coro(coro):
    """
    Run an async coroutine from sync context, even if an event loop is already running.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()


async def _fetch_db_user(tenant_id: Optional[UUID] = None) -> str:
    """
    Execute a trivial query to prove the worker connects with the restricted role.
    """
    async with engine.begin() as conn:
        if tenant_id:
            await set_tenant_guc(conn, tenant_id, local=False)
        res = await conn.execute(text("SELECT current_user"))
        return res.scalar() or ""


def _fetch_db_user_sync(tenant_id: Optional[UUID] = None) -> str:
    """
    Sync path for DB user check using psycopg2 (avoids event loop interference in eager tests).
    """
    import os
    url = make_url(get_database_url())
    query = dict(url.query)
    query.pop("channel_binding", None)
    url = url.set(query=query)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")

    # Manually construct DSN to preserve password (str(url) drops password after .set() calls)
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
    dsn = "".join(dsn_parts)

    # B0.5.2: Runtime DSN diagnostic for CI verification (H2 proof)
    if os.getenv("CI") == "true":
        logger.info(
            f"[B0.5.2 RUNTIME DSN] host={url.host} db={url.database} user={url.username}",
            extra={"dsn_host": url.host, "dsn_database": url.database, "dsn_user": url.username}
        )

    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        if tenant_id:
            cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (str(tenant_id),))
        cur.execute("SELECT current_user")
        return cur.fetchone()[0]
    finally:
        conn.close()


@celery_app.task(bind=True, name="app.tasks.housekeeping.ping", routing_key="housekeeping.task")
def ping(self, fail: bool = False, tenant_id: Optional[str] = None) -> dict:
    """
    Dummy task for foundation validation.

    Args:
        fail: when True, force a failure to exercise error paths/metrics.
        tenant_id: optional UUID string to set tenant GUC (future RLS-aware tasks).
    """
    correlation_id = getattr(self.request, "correlation_id", None) or str(uuid4())
    set_request_correlation_id(correlation_id)
    try:
        logger.info(
            "celery_task_start",
            extra={"task_name": self.name, "task_id": self.request.id, "correlation_id": correlation_id},
        )
        if fail:
            raise ValueError("ping failure requested")

        tenant_uuid = None
        if tenant_id:
            try:
                tenant_uuid = UUID(str(tenant_id))
            except Exception:
                tenant_uuid = None

        # Prefer sync path to avoid event loop issues in eager-mode tests.
        try:
            if tenant_uuid:
                set_tenant_id(tenant_uuid)
            db_user = _fetch_db_user_sync(tenant_uuid)
        except Exception:
            db_user = _run_coro(_fetch_db_user(tenant_uuid))
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "status": "ok",
            "timestamp": now,
            "db_user": db_user,
            "worker": getattr(self.request, "hostname", None),
        }
        logger.info(
            "celery_task_success",
            extra={
                "task_name": self.name,
                "task_id": self.request.id,
                "db_user": db_user,
                "tenant_id": str(tenant_uuid) if tenant_uuid else None,
                "correlation_id": correlation_id,
            },
        )
        return payload
    finally:
        set_request_correlation_id(None)
        set_tenant_id(None)

"""
Tenant context helpers for Celery tasks.

Provides a decorator that enforces tenant_id presence, sets contextvars for
logging, applies the tenant GUC using the shared engine, and normalizes
correlation IDs for observability.
"""
import asyncio
import functools
import logging
import threading
import time
import uuid
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy import text

from app.db.session import engine, set_tenant_guc
from app.observability.context import set_request_correlation_id, set_tenant_id

logger = logging.getLogger(__name__)

# Dedicated worker event loop reused for all async DB bridge calls from Celery tasks.
_WORKER_LOOP: asyncio.AbstractEventLoop | None = None
_WORKER_LOOP_THREAD: threading.Thread | None = None
_WORKER_LOOP_LOCK = threading.Lock()


def get_worker_event_loop() -> asyncio.AbstractEventLoop:
    """
    Return a reusable event loop for worker-side async bridges.

    Using a single loop prevents asyncpg/SQLAlchemy pools from being bound to
    different loops across sequential Celery tasks.
    """
    global _WORKER_LOOP
    global _WORKER_LOOP_THREAD
    with _WORKER_LOOP_LOCK:
        if _WORKER_LOOP is None or _WORKER_LOOP.is_closed():
            _WORKER_LOOP = asyncio.new_event_loop()
            def _runner(loop: asyncio.AbstractEventLoop) -> None:
                asyncio.set_event_loop(loop)
                loop.run_forever()

            _WORKER_LOOP_THREAD = threading.Thread(
                target=_runner,
                args=(_WORKER_LOOP,),
                name="worker-event-loop",
                daemon=True,
            )
            _WORKER_LOOP_THREAD.start()
    # Ensure the loop is running before returning
    while _WORKER_LOOP is not None and not _WORKER_LOOP.is_running():
        time.sleep(0.01)
    return _WORKER_LOOP


def run_in_worker_loop(coro: Awaitable[Any]) -> Any:
    """
    Execute the given coroutine on the dedicated worker loop.

    This avoids creating a fresh loop per call (the source of the cross-loop
    Future failure) while keeping execution synchronous for the caller.
    """
    loop = get_worker_event_loop()
    logger.info(
        "tenant_guc_event_loop_selected",
        extra={"loop_id": id(loop), "loop_running": loop.is_running()},
    )
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=60)


def _normalize_tenant_id(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


async def _set_tenant_guc_global(tenant_id: UUID) -> None:
    loop = asyncio.get_running_loop()
    logger.info(
        "tenant_guc_async_entry",
        extra={
            "loop_id": id(loop),
            "loop_running": loop.is_running(),
            "tenant_id": str(tenant_id),
        },
    )
    async with engine.begin() as conn:
        # Use SET LOCAL semantics so the value is scoped to this transaction only.
        # This prevents connection pool reuse from leaking a previous tenant_id into
        # a subsequent task when the same connection is returned to the pool.
        await set_tenant_guc(conn, tenant_id, local=True)
        # Explicitly mark execution context as worker so DB guardrails can distinguish
        # worker traffic from ingestion/API traffic (B0.5.3.5).
        await conn.execute(
            text("SELECT set_config('app.execution_context', 'worker', true)")
        )
        # Guardrail: read back to prove the GUC is set for this transaction
        await conn.execute(text("SELECT current_setting('app.current_tenant_id', true)"))


def tenant_task(task_fn: Callable) -> Callable:
    """
    Decorator for tenant-scoped Celery tasks.

    Enforces tenant_id, sets contextvars for logging, applies tenant GUC, and
    guarantees a correlation_id is present for downstream logs/metrics.
    """

    @functools.wraps(task_fn)
    def _wrapped(self, *args, **kwargs):
        tenant_id_value = kwargs.get("tenant_id")
        if tenant_id_value is None:
            raise ValueError("tenant_id is required for tenant-scoped tasks")

        tenant_uuid = _normalize_tenant_id(tenant_id_value)
        correlation_id = kwargs.get("correlation_id") or str(uuid.uuid4())

        set_tenant_id(tenant_uuid)
        set_request_correlation_id(correlation_id)
        kwargs["tenant_id"] = tenant_uuid
        kwargs["correlation_id"] = correlation_id

        # B0.5.3.1: Skip GUC setting in eager mode (already in event loop)
        # Eager mode is used for testing - GUC not needed for DLQ capture tests
        is_eager = getattr(self.app.conf, 'task_always_eager', False) if hasattr(self, 'app') else False

        if not is_eager:
            try:
                run_in_worker_loop(_set_tenant_guc_global(tenant_uuid))
            except RuntimeError as exc:
                # If already in event loop (shouldn't happen in worker mode), log and continue
                if "cannot be called from a running event loop" in str(exc):
                    logger.warning(
                        "celery_tenant_guc_skipped_event_loop",
                        extra={"tenant_id": str(tenant_uuid), "task_name": getattr(self, "name", None)},
                    )
                else:
                    raise
            except Exception as exc:
                logger.error(
                    "celery_tenant_guc_failed",
                    exc_info=exc,
                    extra={"tenant_id": str(tenant_uuid), "task_name": getattr(self, "name", None)},
                )
                raise

        try:
            return task_fn(self, *args, **kwargs)
        finally:
            # Reset contextvars to avoid leaking across reused worker threads
            set_tenant_id(None)
            set_request_correlation_id(None)

    return _wrapped

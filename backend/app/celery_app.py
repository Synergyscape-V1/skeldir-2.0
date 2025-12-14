"""
Celery application configured for PostgreSQL broker/result backend.

This module centralizes Celery initialization so workers and tests share
the same configuration, logging, and metrics wiring as the FastAPI app.
"""
import logging
import time
from typing import Optional

from celery import Celery, signals
from sqlalchemy.engine.url import make_url

from app.core.config import settings
from app.observability import metrics
from app.observability.logging_config import configure_logging
from app.observability.worker_monitoring import start_worker_http_server

logger = logging.getLogger(__name__)


def _sync_sqlalchemy_url(raw_url: str) -> str:
    """
    Convert async-friendly DATABASE_URL to a sync SQLAlchemy URL suitable for Celery.
    """
    url = make_url(raw_url)
    # Drop channel_binding for psycopg2 compatibility.
    query = dict(url.query)
    query.pop("channel_binding", None)
    url = url.set(query=query)
    driver = url.drivername
    if driver.startswith("postgresql+"):
        driver = "postgresql"
    url = url.set(drivername=driver)
    return str(url)


def _build_broker_url() -> str:
    """
    Build broker URL using SQLAlchemy transport over Postgres (sqla+postgresql://...).
    Defaults to DATABASE_URL-derived sync DSN when CELERY_BROKER_URL is unset.
    """
    if settings.CELERY_BROKER_URL:
        return settings.CELERY_BROKER_URL
    base = _sync_sqlalchemy_url(settings.DATABASE_URL.unicode_string())
    return f"sqla+{base}"


def _build_result_backend() -> str:
    """
    Build result backend URL using Celery database backend over Postgres (db+postgresql://...).
    Defaults to DATABASE_URL-derived sync DSN when CELERY_RESULT_BACKEND is unset.
    """
    if settings.CELERY_RESULT_BACKEND:
        return settings.CELERY_RESULT_BACKEND
    base = _sync_sqlalchemy_url(settings.DATABASE_URL.unicode_string())
    return f"db+{base}"


celery_app = Celery("skeldir_backend")

# B0.5.2: Explicit queue topology for deterministic routing
from kombu import Queue

celery_app.conf.update(
    broker_url=_build_broker_url(),
    result_backend=_build_result_backend(),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    enable_utc=True,
    timezone="UTC",
    task_track_started=True,
    broker_transport_options={"pool_recycle": 300},
    worker_send_task_events=True,
    worker_hijack_root_logger=False,
    include=[
        "app.tasks.housekeeping",
        "app.tasks.maintenance",
        "app.tasks.llm",
    ],
    # B0.5.2: Fixed queue topology
    task_queues=[
        Queue('housekeeping', routing_key='housekeeping.#'),
        Queue('maintenance', routing_key='maintenance.#'),
        Queue('llm', routing_key='llm.#'),
    ],
    task_routes={
        'app.tasks.housekeeping.*': {'queue': 'housekeeping', 'routing_key': 'housekeeping.task'},
        'app.tasks.maintenance.*': {'queue': 'maintenance', 'routing_key': 'maintenance.task'},
        'app.tasks.llm.*': {'queue': 'llm', 'routing_key': 'llm.task'},
    },
    task_default_queue='housekeeping',
    task_default_exchange='tasks',
    task_default_routing_key='housekeeping.task',
)


@signals.worker_process_init.connect
def _configure_worker_logging(**kwargs):
    """
    Ensure structured logging is configured inside each worker process.
    """
    configure_logging(settings.LOG_LEVEL)
    start_worker_http_server(
        celery_app,
        host=settings.CELERY_METRICS_ADDR,
        port=settings.CELERY_METRICS_PORT,
    )
    logger.info(
        "celery_worker_logging_configured",
        extra={"metrics_addr": settings.CELERY_METRICS_ADDR, "metrics_port": settings.CELERY_METRICS_PORT},
    )


@signals.task_prerun.connect
def _on_task_prerun(task_id, task, **kwargs):
    task.request._started_at = time.perf_counter()
    metrics.celery_task_started_total.labels(task_name=task.name).inc()


@signals.task_postrun.connect
def _on_task_postrun(task_id, task, retval, state, **kwargs):
    started = getattr(task.request, "_started_at", None)
    if started is not None:
        duration = time.perf_counter() - started
        metrics.celery_task_duration_seconds.labels(task_name=task.name).observe(duration)
    if state == "SUCCESS":
        metrics.celery_task_success_total.labels(task_name=task.name).inc()


@signals.task_failure.connect
def _on_task_failure(task_id=None, exception=None, args=None, kwargs=None, einfo=None, **extra):
    # Extract task from extra if available (signal signature variations)
    task = extra.get('sender')
    task_name = task.name if task else "unknown"

    metrics.celery_task_failure_total.labels(task_name=task_name).inc()
    logger.error(
        "celery_task_failed",
        extra={
            "task_name": task_name,
            "task_id": task_id,
            "error": str(exception),
        },
    )

    # B0.5.2: Persist task failure to worker DLQ (G4 remediation: sync psycopg2 path)
    try:
        import os
        import psycopg2
        import psycopg2.extras
        from uuid import UUID, uuid4
        from sqlalchemy.engine.url import make_url
        from app.core.config import settings

        # G4-AUTH: Build sync DSN with 127.0.0.1 normalization for CI determinism
        url = make_url(settings.DATABASE_URL.unicode_string())
        # Normalize localhost to 127.0.0.1 for IPv4 enforcement (prevents ::1 resolution)
        if url.host == "localhost" and os.getenv("CI") == "true":
            url = url.set(host="127.0.0.1")
        query = dict(url.query)
        query.pop("channel_binding", None)
        url = url.set(query=query)
        if url.drivername.startswith("postgresql+"):
            url = url.set(drivername="postgresql")
        dsn = str(url)

        # G4-AUTH diagnostic: Prove connection determinism
        if os.getenv("CI") == "true":
            logger.info(
                f"[G4-AUTH] DLQ connect: host={url.host} port={url.port} db={url.database} user={url.username}",
                extra={"dsn_host": url.host, "dsn_port": url.port, "dsn_db": url.database, "dsn_user": url.username}
            )

        # Extract metadata
        tenant_id = None
        if kwargs and 'tenant_id' in kwargs:
            try:
                tenant_id = UUID(str(kwargs['tenant_id']))
            except (ValueError, TypeError):
                pass

        # Classify error type
        error_type = "unknown"
        if exception:
            exc_name = exception.__class__.__name__
            if exc_name in ("ValueError", "KeyError"):
                error_type = "validation_error"
            elif exc_name in ("IntegrityError", "OperationalError"):
                error_type = "database_error"
            else:
                error_type = "application_error"

        # Get worker info
        queue = None
        worker_name = None
        correlation_id = None
        if task and hasattr(task, 'request'):
            queue = getattr(task.request, 'delivery_info', {}).get('routing_key', None)
            worker_name = getattr(task.request, 'hostname', None)
            correlation_id_val = getattr(task.request, 'correlation_id', None)
            if correlation_id_val:
                try:
                    correlation_id = UUID(str(correlation_id_val))
                except (ValueError, TypeError):
                    pass

        # G4-LOOP/G4-JSON: Sync persistence with proper JSONB encoding
        conn = psycopg2.connect(dsn)
        try:
            cur = conn.cursor()
            # G4-JSON: Use psycopg2.extras.Json for JSONB columns to prevent encoding defects
            cur.execute("""
                INSERT INTO celery_task_failures (
                    id, task_id, task_name, queue, worker,
                    task_args, task_kwargs, tenant_id,
                    error_type, exception_class, error_message, traceback,
                    retry_count, status, correlation_id, failed_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, CURRENT_TIMESTAMP
                )
            """, (
                str(uuid4()),
                task_id,
                task_name,
                queue,
                worker_name,
                psycopg2.extras.Json(args if args else []),  # G4-JSON: Explicit JSONB encoding
                psycopg2.extras.Json(kwargs if kwargs else {}),  # G4-JSON: Explicit JSONB encoding
                str(tenant_id) if tenant_id else None,
                error_type,
                exception.__class__.__name__ if exception else "Unknown",
                str(exception)[:500] if exception else "",
                str(einfo)[:2000] if einfo else None,
                0,
                "pending",
                str(correlation_id) if correlation_id else None,
            ))
            conn.commit()

            # G4-AUTH: Confirm successful persistence
            if os.getenv("CI") == "true":
                logger.info(
                    "[G4-AUTH] DB CONNECT OK - DLQ row persisted",
                    extra={"task_id": task_id, "task_name": task_name}
                )
        finally:
            conn.close()

    except Exception as dlq_error:
        # DLQ failure should not crash worker
        logger.error(
            "celery_dlq_persist_failed",
            exc_info=dlq_error,
            extra={"task_id": task_id, "task_name": task_name},
        )


__all__ = ["celery_app", "_build_broker_url", "_build_result_backend"]

# Explicit imports ensure task registration even outside worker autodiscovery.
import app.tasks.housekeeping  # noqa: E402,F401
import app.tasks.maintenance  # noqa: E402,F401
import app.tasks.llm  # noqa: E402,F401

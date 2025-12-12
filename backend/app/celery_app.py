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


__all__ = ["celery_app", "_build_broker_url", "_build_result_backend"]

# Explicit imports ensure task registration even outside worker autodiscovery.
import app.tasks.housekeeping  # noqa: E402,F401
import app.tasks.maintenance  # noqa: E402,F401
import app.tasks.llm  # noqa: E402,F401

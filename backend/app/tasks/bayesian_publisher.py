"""Dedicated global dispatcher task with separate credential custody."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from sqlalchemy import text

from app.bayesian.db_engine import create_dispatch_publisher_engine
from app.bayesian.dispatch_outbox import publish_due_dispatch_rows_sync
from app.celery_app import celery_app


logger = logging.getLogger(__name__)
DISPATCH_PUBLISHER_TASK_NAME = "app.tasks.bayesian.publish_due_fit_dispatches"


def _publisher_process() -> bool:
    return os.getenv("SKELDIR_CELERY_WORKER_ROLE", "").strip().lower() == (
        "bayesian_publisher"
    )


def _publisher_task(*args, **kwargs):
    if _publisher_process():
        return celery_app.task(*args, **kwargs)

    def _plain(function):
        return function

    return _plain


def _append_probe_event(event: dict[str, object]) -> None:
    path = os.getenv("BAYESIAN_PROBE_LOG_PATH")
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


@_publisher_task(
    bind=True,
    name=DISPATCH_PUBLISHER_TASK_NAME,
    routing_key="bayesian_publisher.task",
    soft_time_limit=30,
    time_limit=60,
    acks_late=True,
    max_retries=0,
)
def publish_due_fit_dispatches(self, *, batch_size: int = 25) -> dict:
    """Publish fresh dispatches only as the dedicated database principal."""

    task_id = str(self.request.id)
    engine = create_dispatch_publisher_engine()
    try:
        with engine.begin() as conn:
            principal = conn.execute(
                text("SELECT public.b24_assert_dispatch_publisher()")
            ).scalar_one()
            if principal != "app_dispatch_publisher":
                raise RuntimeError("dispatch_publisher_principal_mismatch")
            published_rows = publish_due_dispatch_rows_sync(conn, batch_size=batch_size)
    finally:
        engine.dispose()
    payload = {
        "status": "ok",
        "task_id": task_id,
        "publisher_principal": "app_dispatch_publisher",
        "dispatches_published": len(published_rows),
        "dispatch_ids": [str(row.id) for row in published_rows],
        "fit_ids": [str(row.fit_id) for row in published_rows],
    }
    logger.info("bayesian_fresh_dispatch_published", extra=payload)
    _append_probe_event({"event": "bayesian_fresh_dispatch_published", **payload})
    return payload


__all__ = ("DISPATCH_PUBLISHER_TASK_NAME", "publish_due_fit_dispatches")

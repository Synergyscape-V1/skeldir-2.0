"""
Test-only Celery tasks for structured worker logging runtime proof (B0.5.6.6).

These tasks are intentionally deterministic and DB-free. They are only loaded
when the worker is started with `SKELDIR_TEST_TASKS=1`.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.observability_test.success", routing_key="housekeeping.task")
def success(self, tenant_id: Optional[str] = None, correlation_id: Optional[str] = None) -> dict:
    return {"status": "ok"}


@celery_app.task(bind=True, name="app.tasks.observability_test.failure", routing_key="housekeeping.task")
def failure(self, tenant_id: Optional[str] = None, correlation_id: Optional[str] = None) -> None:
    raise ValueError("observability_test_failure")


@celery_app.task(bind=True, name="app.tasks.observability_test.redaction_canary", routing_key="housekeeping.task")
def redaction_canary(self, secret_value: str) -> dict:
    logger.info("LLM_PROVIDER_API_KEY=%s", secret_value)
    logger.warning("Authorization: Bearer %s", secret_value)
    return {"status": "ok"}

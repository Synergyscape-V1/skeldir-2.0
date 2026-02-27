"""
Test-only Celery tasks for structured worker logging runtime proof (B0.5.6.6).

These tasks are intentionally deterministic and DB-free. They are only loaded
when the worker is started with `SKELDIR_TEST_TASKS=1`.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from app.celery_app import celery_app
from app.db.session import get_session
from app.tasks.context import run_in_worker_loop, tenant_task
from sqlalchemy import text

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


async def _probe_worker_tenant_context(tenant_id: UUID, user_id: UUID) -> dict[str, str]:
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        tenant = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        user = await session.execute(text("SELECT current_setting('app.current_user_id', true)"))
        pid = await session.execute(text("SELECT pg_backend_pid()"))
    return {
        "tenant": str(tenant.scalar()),
        "user": str(user.scalar()),
        "backend_pid": str(pid.scalar()),
    }


@celery_app.task(bind=True, name="app.tasks.observability_test.tenant_context_probe", routing_key="housekeeping.task")
@tenant_task
def tenant_context_probe(self, tenant_id: UUID, user_id: UUID, correlation_id: Optional[str] = None) -> dict:
    return run_in_worker_loop(_probe_worker_tenant_context(tenant_id=tenant_id, user_id=user_id))

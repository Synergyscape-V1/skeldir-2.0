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
from app.tasks.context import assert_worker_auth_envelope_active, run_in_worker_loop
from app.tasks.tenant_base import TenantTask
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


async def _write_auth_envelope_probe(
    *,
    tenant_id: UUID,
    user_id: UUID,
    task_id: str,
    effect_key: str,
) -> int:
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        result = await session.execute(
            text(
                """
                INSERT INTO public.worker_side_effects (tenant_id, task_id, effect_key)
                VALUES (:tenant_id, :task_id, :effect_key)
                ON CONFLICT (tenant_id, task_id) DO NOTHING
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "task_id": task_id,
                "effect_key": effect_key,
            },
        )
    return int(result.rowcount or 0)


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.observability_test.tenant_context_probe",
    routing_key="housekeeping.task",
)
def tenant_context_probe(self, tenant_id: UUID, user_id: UUID, correlation_id: Optional[str] = None) -> dict:
    return run_in_worker_loop(_probe_worker_tenant_context(tenant_id=tenant_id, user_id=user_id))


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.observability_test.auth_envelope_probe",
    routing_key="housekeeping.task",
)
def auth_envelope_probe(
    self,
    tenant_id: UUID,
    user_id: UUID,
    auth_token: str,
    correlation_id: Optional[str] = None,
) -> dict:
    claims = assert_worker_auth_envelope_active(
        auth_token=auth_token,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    task_id = str(getattr(self.request, "id", None) or "missing-task-id")
    inserted = run_in_worker_loop(
        _write_auth_envelope_probe(
            tenant_id=tenant_id,
            user_id=user_id,
            task_id=task_id,
            effect_key=f"revocation-probe:{claims['jti']}",
        )
    )
    return {"status": "ok", "rows_inserted": inserted, "jti": str(claims["jti"])}

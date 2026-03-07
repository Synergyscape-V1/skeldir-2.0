"""
Test-only Celery tasks for structured worker logging runtime proof (B0.5.6.6).

These tasks are intentionally deterministic and DB-free. They are only loaded
when the worker is started with `SKELDIR_TEST_TASKS=1`.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional
from uuid import UUID

from app.celery_app import celery_app
from app.db.session import get_session
from app.security.auth import get_revocation_db_lookup_count, reset_revocation_db_lookup_count
from app.security.revocation_runtime import get_revocation_runtime_cache
from app.tasks.context import run_in_worker_loop
from app.tasks.tenant_base import TenantTask, task_tenant_id, task_user_id
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


@celery_app.task(
    bind=True,
    name="app.tasks.observability_test.revocation_runtime_control",
    routing_key="housekeeping.task",
)
def revocation_runtime_control(
    self,
    sleep_seconds: float = 0.0,
    reset_lookup_counter: bool = False,
) -> dict:
    if reset_lookup_counter:
        reset_revocation_db_lookup_count()
    if sleep_seconds > 0:
        time.sleep(float(sleep_seconds))
    cache = get_revocation_runtime_cache()
    cache.ensure_started()
    runtime_state = cache.runtime_state()
    return {
        "worker_pid": os.getpid(),
        "listener_pid": runtime_state["listener_pid"],
        "listener_alive": bool(runtime_state["listener_alive"]),
        "listener_conn_fd": runtime_state["listener_conn_fd"],
        "revocation_db_lookups": int(get_revocation_db_lookup_count()),
    }


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
def tenant_context_probe(self, correlation_id: Optional[str] = None) -> dict:
    return run_in_worker_loop(
        _probe_worker_tenant_context(
            tenant_id=task_tenant_id(self),
            user_id=task_user_id(self),
        )
    )


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.observability_test.auth_envelope_probe",
    routing_key="housekeeping.task",
)
def auth_envelope_probe(
    self,
    correlation_id: Optional[str] = None,
) -> dict:
    tenant_id = task_tenant_id(self)
    user_id = task_user_id(self)
    envelope = getattr(self.request, "authority_envelope", {}) or {}
    jti = str(envelope.get("jti", "missing-jti"))
    task_id = str(getattr(self.request, "id", None) or "missing-task-id")
    inserted = run_in_worker_loop(
        _write_auth_envelope_probe(
            tenant_id=tenant_id,
            user_id=user_id,
            task_id=task_id,
            effect_key=f"revocation-probe:{jti}",
        )
    )
    return {"status": "ok", "rows_inserted": inserted, "jti": jti}


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.observability_test.revocation_runtime_probe",
    routing_key="housekeeping.task",
)
def revocation_runtime_probe(
    self,
    correlation_id: Optional[str] = None,
    sleep_seconds: float = 0.0,
    reset_lookup_counter: bool = False,
) -> dict:
    tenant_id = task_tenant_id(self)
    user_id = task_user_id(self)
    if reset_lookup_counter:
        reset_revocation_db_lookup_count()
    if sleep_seconds > 0:
        time.sleep(float(sleep_seconds))
    cache = get_revocation_runtime_cache()
    cache.ensure_started()
    runtime_state = cache.runtime_state()
    return {
        "tenant": str(tenant_id),
        "user": str(user_id),
        "worker_pid": os.getpid(),
        "listener_pid": runtime_state["listener_pid"],
        "listener_alive": bool(runtime_state["listener_alive"]),
        "revocation_db_lookups": int(get_revocation_db_lookup_count()),
    }

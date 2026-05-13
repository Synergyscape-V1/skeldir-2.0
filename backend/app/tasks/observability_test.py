"""
Test-only Celery tasks for structured worker logging runtime proof (B0.5.6.6).

These tasks are intentionally deterministic and DB-free. They are only loaded
when the worker is started with `SKELDIR_TEST_TASKS=1`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from app.celery_app import celery_app
from app.core.secrets import get_database_url
from app.db.session import get_session
from app.observability.context import get_tenant_id, get_user_id
from app.security.auth import get_revocation_db_lookup_count, reset_revocation_db_lookup_count
from app.security.revocation_runtime import get_revocation_runtime_cache
from app.tasks.context import run_in_worker_loop
from app.tasks.tenant_base import TenantTask, task_tenant_id, task_user_id
from sqlalchemy import text

logger = logging.getLogger(__name__)
_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _qualified_public_table(table_name: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(table_name):
        raise ValueError(f"unsafe test table identifier: {table_name!r}")
    return f"public.{table_name}"


def _database_url_hostport() -> str:
    parsed = urlparse(get_database_url())
    host = parsed.hostname or ""
    port = parsed.port
    return f"{host}:{port}" if port else host


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


async def _m2_worker_concurrency_probe(
    *,
    tenant_id: UUID,
    user_id: UUID,
    table_name: str,
    run_id: str,
    marker: str,
    other_tenant_id: UUID,
    hold_seconds: float,
    barrier_timeout_seconds: float,
    task_id: str,
) -> dict:
    qualified_table = _qualified_public_table(table_name)
    qualified_barrier_table = _qualified_public_table(f"{table_name}_barrier")
    started_at = time.time()
    if hold_seconds > 0:
        await asyncio.sleep(float(hold_seconds))

    if barrier_timeout_seconds > 0:
        async with get_session(tenant_id=tenant_id, user_id=user_id) as barrier_session:
            await barrier_session.execute(
                text(
                    f"""
                    INSERT INTO {qualified_barrier_table} (
                        run_id,
                        marker,
                        tenant_id,
                        task_id,
                        worker_pid
                    )
                    VALUES (
                        :run_id,
                        :marker,
                        :tenant_id,
                        :task_id,
                        :worker_pid
                    )
                    ON CONFLICT (run_id, marker) DO NOTHING
                    """
                ),
                {
                    "run_id": run_id,
                    "marker": marker,
                    "tenant_id": str(tenant_id),
                    "task_id": task_id,
                    "worker_pid": os.getpid(),
                },
            )

    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        tenant_guc = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        user_guc = await session.execute(text("SELECT current_setting('app.current_user_id', true)"))
        backend_pid = await session.execute(text("SELECT pg_backend_pid()"))
        await session.execute(text("SET LOCAL ROLE m2_runtime_rls"))
        await session.execute(
            text(
                f"""
                INSERT INTO {qualified_table} (
                    id,
                    run_id,
                    tenant_id,
                    marker,
                    task_id,
                    worker_pid,
                    backend_pid
                )
                VALUES (
                    :id,
                    :run_id,
                    :tenant_id,
                    :marker,
                    :task_id,
                    :worker_pid,
                    :backend_pid
                )
                """
            ),
            {
                "id": str(uuid4()),
                "run_id": run_id,
                "tenant_id": str(tenant_id),
                "marker": marker,
                "task_id": task_id,
                "worker_pid": os.getpid(),
                "backend_pid": int(backend_pid.scalar_one()),
            },
        )
        own_visible = await session.execute(
            text(
                f"""
                SELECT count(*)
                  FROM {qualified_table}
                 WHERE run_id = :run_id
                   AND tenant_id = :tenant_id
                """
            ),
            {"run_id": run_id, "tenant_id": str(tenant_id)},
        )
        cross_visible = await session.execute(
            text(
                f"""
                SELECT count(*)
                  FROM {qualified_table}
                 WHERE run_id = :run_id
                   AND tenant_id = :other_tenant_id
                """
            ),
            {"run_id": run_id, "other_tenant_id": str(other_tenant_id)},
        )
        if barrier_timeout_seconds > 0:
            deadline = time.time() + float(barrier_timeout_seconds)
            while time.time() < deadline:
                barrier = await session.execute(
                    text(
                        f"""
                        SELECT count(DISTINCT marker)
                          FROM {qualified_barrier_table}
                         WHERE run_id = :run_id
                           AND marker IN ('tenant-a', 'tenant-b')
                        """
                    ),
                    {"run_id": run_id},
                )
                if int(barrier.scalar_one()) >= 2:
                    break
                await asyncio.sleep(0.25)
            else:
                raise RuntimeError("m2 worker concurrency barrier was not satisfied")
        finished_at = time.time()

    return {
        "tenant": str(tenant_id),
        "user": str(user_id),
        "tenant_guc": str(tenant_guc.scalar_one()),
        "user_guc": str(user_guc.scalar_one()),
        "context_tenant": str(get_tenant_id()),
        "context_user": str(get_user_id()),
        "own_visible": int(own_visible.scalar_one()),
        "cross_visible": int(cross_visible.scalar_one()),
        "worker_pid": os.getpid(),
        "database_url_hostport": _database_url_hostport(),
        "started_at": started_at,
        "finished_at": finished_at,
    }


@celery_app.task(
    bind=True,
    base=TenantTask,
    name="app.tasks.observability_test.m2_worker_concurrency_probe",
    routing_key="housekeeping.task",
)
def m2_worker_concurrency_probe(
    self,
    table_name: str,
    run_id: str,
    marker: str,
    other_tenant_id: str,
    hold_seconds: float = 0.0,
    barrier_timeout_seconds: float = 0.0,
    correlation_id: Optional[str] = None,
) -> dict:
    return run_in_worker_loop(
        _m2_worker_concurrency_probe(
            tenant_id=task_tenant_id(self),
            user_id=task_user_id(self),
            table_name=table_name,
            run_id=run_id,
            marker=marker,
            other_tenant_id=UUID(str(other_tenant_id)),
            hold_seconds=hold_seconds,
            barrier_timeout_seconds=barrier_timeout_seconds,
            task_id=str(getattr(self.request, "id", None) or "missing-task-id"),
        )
    )

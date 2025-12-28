"""
R4 — Worker Failure Semantics tasks.

These tasks are intentionally adversarial and used by `scripts/r4/worker_failure_semantics.py`
to prove crash/retry/RLS/least-privilege mechanics in CI against a real Postgres + Celery worker.
"""

from __future__ import annotations

import logging
import os
import random
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import psycopg2
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import _sync_sqlalchemy_url, celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_dsn() -> str:
    return _sync_sqlalchemy_url(settings.DATABASE_URL.unicode_string())


def _require_uuid(value: str | UUID, *, name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


@dataclass(frozen=True)
class DbCtx:
    tenant_id: UUID
    correlation_id: UUID


def _db_connect() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(_sync_dsn())
    conn.autocommit = False
    return conn


def _set_worker_context(cur: psycopg2.extensions.cursor, ctx: DbCtx) -> None:
    cur.execute("SELECT set_config('app.current_tenant_id', %s, true)", (str(ctx.tenant_id),))
    cur.execute("SELECT set_config('app.execution_context', 'worker', true)")
    cur.execute("SELECT set_config('app.correlation_id', %s, true)", (str(ctx.correlation_id),))
    cur.execute("SELECT current_setting('app.current_tenant_id', true)")
    guc = cur.fetchone()[0]
    if guc != str(ctx.tenant_id):
        raise RuntimeError(f"tenant GUC mismatch: expected={ctx.tenant_id} got={guc}")


@celery_app.task(
    bind=True,
    name="app.tasks.r4_failure_semantics.poison_pill",
    max_retries=3,
    default_retry_delay=1,
)
def poison_pill(self, *, tenant_id: str, correlation_id: str, marker: str) -> None:
    """
    Always fails; used to prove bounded retries + DLQ persistence on exhaustion.
    """
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")

    logger.info(
        "r4_poison_pill_attempt",
        extra={
            "tenant_id": str(tenant_uuid),
            "correlation_id": str(correlation_uuid),
            "task_id": self.request.id,
            "retries": int(getattr(self.request, "retries", 0) or 0),
            "marker": marker,
            "ts": _now_utc_iso(),
        },
    )

    try:
        raise RuntimeError(f"R4 poison pill marker={marker}")
    except Exception as exc:  # noqa: BLE001 - intentional poison pill
        retries = int(getattr(self.request, "retries", 0) or 0)
        if retries < int(getattr(self, "max_retries", 0) or 0):
            backoff = min(2**retries, 4)
            countdown = backoff + random.randint(0, 1)
            raise self.retry(exc=exc, countdown=countdown)
        raise


@celery_app.task(
    bind=True,
    name="app.tasks.r4_failure_semantics.crash_after_write_pre_ack",
    max_retries=0,
)
def crash_after_write_pre_ack(self, *, tenant_id: str, correlation_id: str, effect_key: str) -> dict[str, str | int]:
    """
    Simulates crash-after-write/pre-ack and proves idempotent side effects.

    First execution inserts a row and SIGKILLs the worker child process.
    Redelivery sees the existing row (conflict) and returns success without crashing again.
    """
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    ctx = DbCtx(tenant_id=tenant_uuid, correlation_id=correlation_uuid)

    inserted = 0
    with _db_connect() as conn:
        with conn.cursor() as cur:
            _set_worker_context(cur, ctx)
            cur.execute(
                """
                INSERT INTO worker_side_effects (tenant_id, task_id, correlation_id, effect_key)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, task_id) DO NOTHING
                """,
                (str(tenant_uuid), str(self.request.id), str(correlation_uuid), effect_key),
            )
            inserted = cur.rowcount
        conn.commit()

    if inserted == 1:
        logger.error(
            "r4_crash_after_write_triggered",
            extra={
                "tenant_id": str(tenant_uuid),
                "correlation_id": str(correlation_uuid),
                "task_id": self.request.id,
                "effect_key": effect_key,
                "ts": _now_utc_iso(),
            },
        )
        os.kill(os.getpid(), signal.SIGKILL)

    return {"inserted": inserted, "task_id": str(self.request.id), "effect_key": effect_key}


@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.rls_cross_tenant_probe")
def rls_cross_tenant_probe(
    self,
    *,
    tenant_id: str,
    correlation_id: str,
    target_external_event_id: str,
) -> dict[str, str | int]:
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    ctx = DbCtx(tenant_id=tenant_uuid, correlation_id=correlation_uuid)

    with _db_connect() as conn:
        with conn.cursor() as cur:
            _set_worker_context(cur, ctx)
            cur.execute("SELECT COUNT(*) FROM attribution_events WHERE external_event_id = %s", (target_external_event_id,))
            visible = int(cur.fetchone()[0] or 0)
        conn.commit()

    return {
        "visible_count": visible,
        "tenant_id": str(tenant_uuid),
        "target_external_event_id": target_external_event_id,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.r4_failure_semantics.runaway_sleep",
    soft_time_limit=2,
    time_limit=4,
)
def runaway_sleep(self, *, tenant_id: str, correlation_id: str, sleep_s: int) -> dict[str, str]:
    """
    Intentionally runs longer than the configured time limits.
    """
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    logger.info(
        "r4_runaway_start",
        extra={
            "tenant_id": str(tenant_uuid),
            "correlation_id": str(correlation_uuid),
            "task_id": self.request.id,
            "sleep_s": sleep_s,
            "ts": _now_utc_iso(),
        },
    )
    try:
        time.sleep(sleep_s)
    except SoftTimeLimitExceeded:
        logger.warning(
            "r4_runaway_soft_time_limit",
            extra={"task_id": self.request.id, "tenant_id": str(tenant_uuid), "correlation_id": str(correlation_uuid)},
        )
        raise
    return {"status": "completed_unexpectedly"}


@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.sentinel_side_effect")
def sentinel_side_effect(self, *, tenant_id: str, correlation_id: str, effect_key: str) -> dict[str, str]:
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    ctx = DbCtx(tenant_id=tenant_uuid, correlation_id=correlation_uuid)

    with _db_connect() as conn:
        with conn.cursor() as cur:
            _set_worker_context(cur, ctx)
            cur.execute(
                """
                INSERT INTO worker_side_effects (tenant_id, task_id, correlation_id, effect_key)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, task_id) DO NOTHING
                """,
                (str(tenant_uuid), str(self.request.id), str(correlation_uuid), effect_key),
            )
        conn.commit()

    return {"task_id": str(self.request.id), "effect_key": effect_key}


@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.privilege_probes")
def privilege_probes(self, *, tenant_id: str, correlation_id: str) -> dict[str, dict[str, str]]:
    """
    Executes DDL/RLS-disable/escalation probes under the worker DB role.
    Returns a map of probe_name -> {"ok": "true|false", "error": "..."}.
    """
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    ctx = DbCtx(tenant_id=tenant_uuid, correlation_id=correlation_uuid)

    probes: list[tuple[str, str]] = [
        ("ddl_create_table", "CREATE TABLE r4_priv_probe_tmp(id INT)"),
        ("disable_rls", "ALTER TABLE public.attribution_events DISABLE ROW LEVEL SECURITY"),
        ("force_rls", "ALTER TABLE public.attribution_events FORCE ROW LEVEL SECURITY"),
        ("bypass_rls_attempt", "SET row_security = off; SELECT COUNT(*) FROM public.attribution_events"),
        ("create_role", "CREATE ROLE r4_priv_probe_role"),
        ("grant_admin_role", "GRANT pg_read_all_data TO app_user"),
        ("set_bypassrls", "ALTER ROLE app_user BYPASSRLS"),
    ]

    results: dict[str, dict[str, str]] = {}
    with _db_connect() as conn:
        with conn.cursor() as cur:
            _set_worker_context(cur, ctx)
            for name, sql in probes:
                try:
                    cur.execute(sql)
                    results[name] = {"ok": "true", "error": ""}
                except Exception as exc:  # noqa: BLE001 - probe captures DB errors
                    conn.rollback()
                    results[name] = {"ok": "false", "error": str(exc)[:400]}
        conn.commit()

    return results

"""
R4 — Worker Failure Semantics tasks.

These tasks are intentionally adversarial and used by `scripts/r4/worker_failure_semantics.py`
to prove crash/retry/RLS/least-privilege mechanics in CI against a real Postgres + Celery worker.
"""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import psycopg2
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import _sync_sqlalchemy_url, celery_app
from app.core.secrets import get_database_url

logger = logging.getLogger(__name__)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_dsn() -> str:
    return _sync_sqlalchemy_url(get_database_url())


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


def _record_attempt(
    cur: psycopg2.extensions.cursor,
    ctx: DbCtx,
    *,
    task_id: str,
    scenario: str,
    worker_pid: int,
) -> int:
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)", (task_id,))
    cur.execute(
        "SELECT COALESCE(MAX(attempt_no), 0) FROM r4_task_attempts WHERE tenant_id=%s AND task_id=%s",
        (str(ctx.tenant_id), task_id),
    )
    attempt_no = int(cur.fetchone()[0] or 0) + 1
    cur.execute(
        """
        INSERT INTO r4_task_attempts (tenant_id, task_id, scenario, attempt_no, worker_pid)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (str(ctx.tenant_id), task_id, scenario, attempt_no, worker_pid),
    )
    return attempt_no


def _record_crash_barrier(
    cur: psycopg2.extensions.cursor,
    ctx: DbCtx,
    *,
    task_id: str,
    scenario: str,
    attempt_no: int,
    worker_pid: int,
) -> None:
    cur.execute(
        """
        INSERT INTO r4_crash_barriers (tenant_id, task_id, scenario, attempt_no, worker_pid)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (tenant_id, task_id, attempt_no) DO NOTHING
        """,
        (str(ctx.tenant_id), task_id, scenario, attempt_no, worker_pid),
    )


@celery_app.task(
    bind=True,
    name="app.tasks.r4_failure_semantics.poison_pill",
    max_retries=3,
    default_retry_delay=1,
    acks_late=False,
)
def poison_pill(self, *, tenant_id: str, correlation_id: str, marker: str) -> None:
    """
    Always fails; used to prove bounded retries + DLQ persistence on exhaustion.
    """
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    ctx = DbCtx(tenant_id=tenant_uuid, correlation_id=correlation_uuid)
    task_id = str(self.request.id)
    worker_pid = os.getpid()

    with _db_connect() as conn:
        with conn.cursor() as cur:
            _set_worker_context(cur, ctx)
            attempt_no = _record_attempt(
                cur,
                ctx,
                task_id=task_id,
                scenario="S1_PoisonPill",
                worker_pid=worker_pid,
            )
        conn.commit()

    logger.info(
        "r4_poison_pill_attempt",
        extra={
            "tenant_id": str(tenant_uuid),
            "correlation_id": str(correlation_uuid),
            "task_id": task_id,
            "attempt_no": attempt_no,
            # Kombu SQLAlchemy transport does not reliably propagate retries across redelivery;
            # attempt_no is the authoritative, DB-backed retry counter for R4.
            "retries": attempt_no - 1,
            "marker": marker,
            "ts": _now_utc_iso(),
        },
    )

    try:
        raise RuntimeError(f"R4 poison pill marker={marker}")
    except Exception as exc:  # noqa: BLE001 - intentional poison pill
        max_retries = int(getattr(self, "max_retries", 0) or 0)
        if attempt_no <= max_retries:
            retry_index = attempt_no - 1
            backoff = min(2**retry_index, 4)
            countdown = backoff + random.randint(0, 1)
            raise self.retry(exc=exc, countdown=countdown)
        raise


@celery_app.task(
    bind=True,
    name="app.tasks.r4_failure_semantics.crash_after_write_pre_ack",
    max_retries=0,
    acks_late=True,
)
def crash_after_write_pre_ack(self, *, tenant_id: str, correlation_id: str, effect_key: str) -> dict[str, str | int]:
    """
    Simulates crash-after-write/pre-ack and proves idempotent side effects.

    First execution inserts the side effect, commits, writes a crash barrier row, then blocks (pre-ack).
    The harness must SIGKILL the worker and restart it. Redelivery re-executes the same task_id; DB upsert
    prevents double-apply.
    """
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    ctx = DbCtx(tenant_id=tenant_uuid, correlation_id=correlation_uuid)

    inserted = 0
    attempt_no = 0
    task_id = str(self.request.id)
    worker_pid = os.getpid()
    with _db_connect() as conn:
        with conn.cursor() as cur:
            _set_worker_context(cur, ctx)
            attempt_no = _record_attempt(
                cur,
                ctx,
                task_id=task_id,
                scenario="S2_CrashAfterWritePreAck",
                worker_pid=worker_pid,
            )
            cur.execute(
                """
                INSERT INTO worker_side_effects (tenant_id, task_id, correlation_id, effect_key)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, task_id) DO NOTHING
                """,
                (str(tenant_uuid), task_id, str(correlation_uuid), effect_key),
            )
            inserted = cur.rowcount
            if attempt_no == 1:
                _record_crash_barrier(
                    cur,
                    ctx,
                    task_id=task_id,
                    scenario="S2_CrashAfterWritePreAck",
                    attempt_no=attempt_no,
                    worker_pid=worker_pid,
                )
            if attempt_no >= 2:
                cur.execute(
                    """
                    INSERT INTO r4_recovery_exclusions (scenario, task_id)
                    VALUES (%s, %s)
                    ON CONFLICT (scenario, task_id) DO NOTHING
                    """,
                    ("S2_CrashAfterWritePreAck", task_id),
                )
        conn.commit()

    logger.info(
        "r4_crash_after_write_progress",
        extra={
            "tenant_id": str(tenant_uuid),
            "correlation_id": str(correlation_uuid),
            "task_id": task_id,
            "attempt_no": attempt_no,
            "inserted": inserted,
            "worker_pid": worker_pid,
            "effect_key": effect_key,
            "ts": _now_utc_iso(),
        },
    )

    if attempt_no == 1:
        logger.error(
            "r4_crash_after_write_barrier_committed_pre_ack",
            extra={
                "tenant_id": str(tenant_uuid),
                "correlation_id": str(correlation_uuid),
                "task_id": task_id,
                "attempt_no": attempt_no,
                "effect_key": effect_key,
                "worker_pid": worker_pid,
                "ts": _now_utc_iso(),
            },
        )
        time.sleep(3600)

    return {"inserted": inserted, "task_id": task_id, "effect_key": effect_key, "attempt_no": attempt_no}


@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.rls_cross_tenant_probe", acks_late=False)
def rls_cross_tenant_probe(
    self,
    *,
    tenant_id: str,
    correlation_id: str,
    target_row_id: str,
) -> dict[str, str | int | None]:
    tenant_uuid = _require_uuid(tenant_id, name="tenant_id")
    correlation_uuid = _require_uuid(correlation_id, name="correlation_id")
    target_uuid = _require_uuid(target_row_id, name="target_row_id")
    ctx = DbCtx(tenant_id=tenant_uuid, correlation_id=correlation_uuid)

    result_rows: int | None = None
    sqlstate: str | None = None
    db_error: str | None = None

    with _db_connect() as conn:
        with conn.cursor() as cur:
            try:
                _set_worker_context(cur, ctx)
                cur.execute("SELECT COUNT(*) FROM worker_side_effects WHERE id = %s", (str(target_uuid),))
                result_rows = int(cur.fetchone()[0] or 0)
                conn.commit()
            except Exception as exc:  # noqa: BLE001 - probe surfaces DB errors for adjudication
                conn.rollback()
                result_rows = -1
                sqlstate = getattr(exc, "pgcode", None)
                db_error = str(exc)[:400]

    return {
        "result_rows": int(result_rows or 0),
        "tenant_id": str(tenant_uuid),
        "target_row_id": str(target_uuid),
        "sqlstate": sqlstate,
        "db_error": db_error,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.r4_failure_semantics.runaway_sleep",
    soft_time_limit=2,
    time_limit=4,
    acks_late=False,
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


@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.sentinel_side_effect", acks_late=False)
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


@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.privilege_probes", acks_late=False)
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

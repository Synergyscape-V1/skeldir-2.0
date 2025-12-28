"""
R4 — Worker Failure Semantics (Crash Physics + Adversarial Proof)

Authoritative proof harness: runs against a real Postgres + real Celery worker fabric
in CI and prints browser-verifiable verdict blocks + DB truth queries to stdout.
"""

from __future__ import annotations

import json
import os
import platform
import asyncio
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

# PYTHONPATH=backend is set in CI workflow for these imports
from app.celery_app import celery_app  # noqa: E402


def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    if v is None or v == "":
        if default is None:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return v


def _kill_stray_celery_workers() -> int:
    """
    Best-effort cleanup: ensure no orphaned Celery worker processes remain between scenarios.

    This is intentionally aggressive but scoped (matches only this app's worker command) and is
    required to keep Postgres connection usage bounded in CI evidence runs.
    """
    if os.name != "posix":
        return 0

    try:
        out = subprocess.check_output(["ps", "-eo", "pid,pgid,args"], stderr=subprocess.STDOUT).decode(
            "utf-8", errors="replace"
        )
    except Exception:
        return 0

    killed = 0
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        pid_s, pgid_s, args = parts
        if "celery" not in args or "app.celery_app.celery_app" not in args or " worker" not in args:
            continue
        try:
            pid = int(pid_s)
            pgid = int(pgid_s)
        except ValueError:
            continue
        try:
            os.killpg(pgid, signal.SIGKILL)
            print(f"R4_CLEANUP_KILLED pid={pid} pgid={pgid}")
            killed += 1
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"R4_CLEANUP_KILLED pid={pid} pgid={pgid} mode=pid")
                killed += 1
            except Exception:
                pass
    return killed


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(ts: datetime | None = None) -> str:
    return (ts or _now_utc()).isoformat()


def _uuid_deterministic(*parts: str) -> UUID:
    return uuid5(NAMESPACE_URL, ":".join(parts))


def _git_rev_parse_head() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.STDOUT)
            .decode("utf-8", errors="replace")
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def _verdict_block(name: str, payload: dict[str, Any]) -> None:
    print(f"R4_VERDICT_BEGIN {name}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"R4_VERDICT_END {name}")


@dataclass(frozen=True)
class ScenarioCtx:
    candidate_sha: str
    run_url: str
    tenant_a: UUID
    tenant_b: UUID


@dataclass
class WorkerSupervisor:
    concurrency: int
    pool: str
    log_prefix: str
    proc: subprocess.Popen | None = None
    pid_history: list[int] | None = None

    def __post_init__(self) -> None:
        if self.pid_history is None:
            self.pid_history = []

    def start(self) -> int:
        if self.proc is not None and self.proc.poll() is None:
            return int(self.proc.pid)

        log_path = f"{self.log_prefix}.pid{len(self.pid_history) + 1}.log"
        log_f = open(log_path, "ab", buffering=0)
        cmd = [
            "celery",
            "-A",
            "app.celery_app.celery_app",
            "worker",
            "--loglevel=INFO",
            "--pool",
            self.pool,
            "--concurrency",
            str(self.concurrency),
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            start_new_session=True,
        )
        log_f.close()
        self.pid_history.append(int(self.proc.pid))
        print(f"R4_WORKER_STARTED pid={self.proc.pid} log={log_path}")
        return int(self.proc.pid)

    def kill(self, *, sig: int = 9, timeout_s: float = 30.0) -> dict[str, Any]:
        if self.proc is None:
            return {"killed": False, "reason": "no_process"}
        pid = int(self.proc.pid)
        print(f"R4_S2_KILL_ISSUED pid={pid} sig={sig}")
        os.killpg(pid, sig)
        try:
            rc = self.proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            rc = None
        print(f"R4_S2_WORKER_EXITED pid={pid} exit_code={rc}")
        self.proc = None
        return {"killed": True, "pid": pid, "sig": sig, "exit_code": rc}

    def restart(self) -> int:
        new_pid = self.start()
        print(f"R4_S2_WORKER_RESTARTED new_pid={new_pid}")
        return new_pid

    def ensure_dead(self) -> None:
        if self.proc is None:
            return
        try:
            os.killpg(int(self.proc.pid), signal.SIGTERM)
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            pass
        self.proc = None


async def _pg(database_url: str) -> asyncpg.Connection:
    return await asyncpg.connect(database_url)


async def _seed_tenant(conn: asyncpg.Connection, tenant_id: UUID, *, label: str) -> None:
    api_key_hash = f"R4_{label}_{tenant_id}"
    notification_email = f"r4_{label}_{str(tenant_id)[:8]}@test.invalid"
    await conn.execute(
        """
        INSERT INTO tenants (id, name, api_key_hash, notification_email, created_at, updated_at)
        VALUES ($1, $2, $3, $4, NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        str(tenant_id),
        f"R4 Tenant {label}",
        api_key_hash,
        notification_email,
    )


async def _seed_worker_side_effect(conn: asyncpg.Connection, tenant_id: UUID, *, task_id: str, effect_key: str) -> None:
    await conn.execute(
        """
        INSERT INTO worker_side_effects (tenant_id, task_id, correlation_id, effect_key, created_at)
        VALUES ($1, $2, NULL, $3, NOW())
        ON CONFLICT (tenant_id, task_id) DO NOTHING
        """,
        str(tenant_id),
        task_id,
        effect_key,
    )


async def _db_conn_snapshot(conn: asyncpg.Connection) -> dict[str, Any]:
    max_connections_raw = await conn.fetchval("SHOW max_connections")
    max_connections = int(str(max_connections_raw))
    rows = await conn.fetch(
        """
        SELECT usename, state, COUNT(*)::int AS cnt
        FROM pg_stat_activity
        WHERE datname = current_database()
        GROUP BY 1, 2
        ORDER BY cnt DESC, usename, state
        """
    )
    return {
        "max_connections": max_connections,
        "by_user_state": [
            {"usename": r["usename"], "state": r["state"], "count": int(r["cnt"])} for r in rows
        ],
    }


def _wait_for_results(results, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if all(r.ready() for r in results):
            return
        time.sleep(0.25)
    raise TimeoutError("Timed out waiting for Celery results")


def _ping_worker(timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = celery_app.send_task("app.tasks.housekeeping.ping", kwargs={"fail": False})
            return r.get(timeout=10)
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("Worker ping did not succeed")


def _ping_worker_safe(timeout_s: float = 10.0) -> dict[str, Any]:
    try:
        return {"ok": True, "result": _ping_worker(timeout_s=timeout_s)}
    except Exception as exc:  # noqa: BLE001 - diagnostic surface for CI logs
        return {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}


async def _run_safely(
    verdict_name: str,
    scenario: str,
    fn,
    *,
    candidate_sha: str,
    run_url: str,
    tenant_a: UUID,
    tenant_b: UUID,
    n: int | None = None,
    conn: asyncpg.Connection | None = None,
) -> dict[str, Any]:
    try:
        verdict = await fn
        if conn is not None:
            try:
                verdict.setdefault("db_truth", {})["pg_connections_end"] = await _db_conn_snapshot(conn)
            except Exception as snap_exc:  # noqa: BLE001
                verdict.setdefault("db_truth", {})["pg_connections_end_error"] = f"{snap_exc.__class__.__name__}: {snap_exc}"
        return verdict
    except Exception as exc:  # noqa: BLE001 - harness must remain evidence-producing
        snapshot: dict[str, Any] | None = None
        if conn is not None:
            try:
                snapshot = await _db_conn_snapshot(conn)
            except Exception as snap_exc:  # noqa: BLE001
                snapshot = {"error": f"{snap_exc.__class__.__name__}: {snap_exc}"}
        verdict = {
            "scenario": scenario,
            "N": n,
            "candidate_sha": candidate_sha,
            "run_url": run_url,
            "tenant_a": str(tenant_a),
            "tenant_b": str(tenant_b),
            "db_truth": {"pg_connections_error_snapshot": snapshot} if snapshot is not None else {},
            "worker_observed": {"error": f"{exc.__class__.__name__}: {exc}"},
            "passed": False,
        }
        _verdict_block(verdict_name, verdict)
        return verdict


async def _count_worker_failed_jobs(
    conn: asyncpg.Connection,
    *,
    task_name: str,
    task_ids: list[str],
    since: datetime,
    until: datetime,
) -> dict[str, int]:
    if not task_ids:
        return {"rows": 0, "rows_total": 0, "max_retry_count": 0}
    rows_total = int(
        await conn.fetchval(
            """
            SELECT COUNT(*) FROM worker_failed_jobs
            WHERE task_name=$1
              AND task_id = ANY($2::text[])
              AND failed_at >= $3
              AND failed_at <= $4
            """,
            task_name,
            task_ids,
            since,
            until,
        )
    )
    rows = int(
        await conn.fetchval(
            """
            SELECT COUNT(DISTINCT task_id) FROM worker_failed_jobs
            WHERE task_name=$1
              AND task_id = ANY($2::text[])
              AND failed_at >= $3
              AND failed_at <= $4
            """,
            task_name,
            task_ids,
            since,
            until,
        )
    )
    max_retry = int(
        await conn.fetchval(
            """
            SELECT COALESCE(MAX(retry_count),0) FROM worker_failed_jobs
            WHERE task_name=$1
              AND task_id = ANY($2::text[])
              AND failed_at >= $3
              AND failed_at <= $4
            """,
            task_name,
            task_ids,
            since,
            until,
        )
    )
    return {"rows": rows, "rows_total": rows_total, "max_retry_count": max_retry}


async def _count_side_effects(
    conn: asyncpg.Connection,
    *,
    tenant_id: UUID,
    task_ids: list[str],
    since: datetime,
    until: datetime,
) -> dict[str, int]:
    if not task_ids:
        return {"rows": 0, "duplicate_task_ids": 0}
    rows = int(
        await conn.fetchval(
            """
            SELECT COUNT(*) FROM worker_side_effects
            WHERE tenant_id=$1
              AND task_id = ANY($2::text[])
              AND created_at >= $3
              AND created_at <= $4
            """,
            str(tenant_id),
            task_ids,
            since,
            until,
        )
    )
    dupes = int(
        await conn.fetchval(
            """
            SELECT COALESCE(COUNT(*) - COUNT(DISTINCT task_id),0) FROM worker_side_effects
            WHERE tenant_id=$1
              AND task_id = ANY($2::text[])
              AND created_at >= $3
              AND created_at <= $4
            """,
            str(tenant_id),
            task_ids,
            since,
            until,
        )
    )
    return {"rows": rows, "duplicate_task_ids": dupes}


async def _attempt_stats(
    conn: asyncpg.Connection,
    *,
    tenant_id: UUID,
    scenario: str,
    task_ids: list[str],
    since: datetime,
    until: datetime,
) -> dict[str, Any]:
    if not task_ids:
        return {
            "attempts_total": 0,
            "attempts_min_per_task": 0,
            "attempts_max_per_task": 0,
            "attempts_distribution": {},
            "task_count_observed": 0,
        }
    rows = await conn.fetch(
        """
        SELECT task_id, COUNT(*) AS attempts
        FROM r4_task_attempts
        WHERE tenant_id=$1
          AND scenario=$2
          AND task_id = ANY($3::text[])
          AND created_at >= $4
          AND created_at <= $5
        GROUP BY task_id
        """,
        str(tenant_id),
        scenario,
        task_ids,
        since,
        until,
    )
    per_task = [int(r["attempts"]) for r in rows]
    dist: dict[str, int] = {}
    for a in per_task:
        k = str(a)
        dist[k] = dist.get(k, 0) + 1
    return {
        "attempts_total": int(sum(per_task)),
        "attempts_min_per_task": int(min(per_task)) if per_task else 0,
        "attempts_max_per_task": int(max(per_task)) if per_task else 0,
        "attempts_distribution": dist,
        "task_count_observed": int(len(per_task)),
    }


async def _barrier_row(
    conn: asyncpg.Connection,
    *,
    tenant_id: UUID,
    task_id: str,
    scenario: str,
    timeout_s: float,
) -> dict[str, Any] | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = await conn.fetchrow(
            """
            SELECT attempt_no, worker_pid, wrote_at
            FROM r4_crash_barriers
            WHERE tenant_id=$1 AND task_id=$2 AND scenario=$3 AND attempt_no=1
            ORDER BY wrote_at DESC
            LIMIT 1
            """,
            str(tenant_id),
            task_id,
            scenario,
        )
        if row:
            return {
                "attempt_no": int(row["attempt_no"]),
                "worker_pid": int(row["worker_pid"]) if row["worker_pid"] is not None else None,
                "wrote_at": row["wrote_at"].isoformat() if row["wrote_at"] else None,
            }
        await asyncio.sleep(0.2)
    return None


async def _wait_for_redelivery_attempt(
    conn: asyncpg.Connection,
    *,
    tenant_id: UUID,
    task_id: str,
    scenario: str,
    min_attempt_no: int,
    timeout_s: float,
    since_ts: datetime | None = None,
) -> int | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if since_ts is None:
            val = await conn.fetchval(
                """
                SELECT COALESCE(MAX(attempt_no), 0) FROM r4_task_attempts
                WHERE tenant_id=$1 AND task_id=$2 AND scenario=$3
                """,
                str(tenant_id),
                task_id,
                scenario,
            )
            max_attempt = int(val or 0)
            if max_attempt >= min_attempt_no:
                return max_attempt
        else:
            row = await conn.fetchrow(
                """
                SELECT attempt_no
                FROM r4_task_attempts
                WHERE tenant_id=$1
                  AND task_id=$2
                  AND scenario=$3
                  AND attempt_no >= $4
                  AND created_at >= $5
                ORDER BY attempt_no DESC, created_at DESC
                LIMIT 1
                """,
                str(tenant_id),
                task_id,
                scenario,
                int(min_attempt_no),
                since_ts,
            )
            if row:
                return int(row["attempt_no"])
        await asyncio.sleep(0.2)
    return None


async def _kombu_payload_debug(conn: asyncpg.Connection, *, task_id: str, task_name_substr: str) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        SELECT payload
        FROM kombu_message
        WHERE payload LIKE $1 OR payload LIKE $2
        ORDER BY id DESC
        LIMIT 1
        """,
        f"%{task_id}%",
        f"%{task_name_substr}%",
    )
    if not row or not row.get("payload"):
        return {"found": False}
    payload_text = str(row["payload"])
    try:
        payload = json.loads(payload_text)
    except Exception as exc:  # noqa: BLE001
        return {"found": True, "parse_error": f"{exc.__class__.__name__}: {exc}", "payload_prefix": payload_text[:200]}

    headers = payload.get("headers") if isinstance(payload, dict) else None
    return {
        "found": True,
        "top_keys": sorted(list(payload.keys())) if isinstance(payload, dict) else [],
        "headers_id": headers.get("id") if isinstance(headers, dict) else None,
        "headers_task_id": headers.get("task_id") if isinstance(headers, dict) else None,
        "top_id": payload.get("id") if isinstance(payload, dict) else None,
        "headers_task": headers.get("task") if isinstance(headers, dict) else None,
    }


async def scenario_poison_pill(ctx: ScenarioCtx, conn: asyncpg.Connection, *, n: int) -> dict[str, Any]:
    correlation_id_prefix = f"r4:{ctx.candidate_sha}:S1"
    print(
        f"R4_S1_START PoisonPill N={n} tenant_a={ctx.tenant_a} tenant_b={ctx.tenant_b} correlation_id_prefix={correlation_id_prefix}"
    )
    s_start = _now_utc()

    task_name = "app.tasks.r4_failure_semantics.poison_pill"
    task_ids: list[str] = []
    for i in range(n):
        task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S1", "poison", str(i)))
        task_ids.append(task_id)
        celery_app.send_task(
            task_name,
            kwargs={
                "tenant_id": str(ctx.tenant_a),
                "correlation_id": task_id,
                "marker": f"R4_S1_{i}",
            },
            task_id=task_id,
        )

    deadline = time.time() + 180.0
    dlq: dict[str, int] = {"rows": 0, "max_retry_count": 0}
    while time.time() < deadline:
        now = _now_utc()
        dlq = await _count_worker_failed_jobs(conn, task_name=task_name, task_ids=task_ids, since=s_start, until=now)
        if dlq["rows"] >= n:
            break
        await asyncio.sleep(0.5)

    s_end = _now_utc()
    effects = await _count_side_effects(conn, tenant_id=ctx.tenant_a, task_ids=task_ids, since=s_start, until=s_end)
    attempts = await _attempt_stats(
        conn,
        tenant_id=ctx.tenant_a,
        scenario="S1_PoisonPill",
        task_ids=task_ids,
        since=s_start,
        until=s_end,
    )

    passed = (
        dlq["rows"] == n
        and dlq["max_retry_count"] == 3
        and effects["rows"] == 0
        and attempts["task_count_observed"] == n
        and attempts["attempts_min_per_task"] >= 2
        and attempts["attempts_max_per_task"] <= 4
    )

    verdict = {
        "scenario": "S1_PoisonPill",
        "N": n,
        "candidate_sha": ctx.candidate_sha,
        "run_url": ctx.run_url,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"worker_failed_jobs": dlq, "worker_side_effects": effects, "attempts": attempts},
        "worker_observed": {"dlq_rows_observed": dlq["rows"]},
        "passed": passed,
    }
    _verdict_block(f"S1_PoisonPill_N{n}", verdict)
    print("R4_S1_END")
    return verdict


async def scenario_crash_after_write(
    ctx: ScenarioCtx, conn: asyncpg.Connection, *, n: int, worker: WorkerSupervisor
) -> dict[str, Any]:
    correlation_id_prefix = f"r4:{ctx.candidate_sha}:S2"
    print(
        f"R4_S2_START CrashAfterWritePreAck N={n} tenant_a={ctx.tenant_a} tenant_b={ctx.tenant_b} correlation_id_prefix={correlation_id_prefix}"
    )
    s_start = _now_utc()

    worker_pid = worker.start()
    print(f"R4_S2_WORKER_PID_BEFORE {worker_pid}")
    print("R4_S2_WORKER_PING_BEFORE", json.dumps(_ping_worker_safe(timeout_s=15.0), sort_keys=True))

    task_name = "app.tasks.r4_failure_semantics.crash_after_write_pre_ack"
    task_ids: list[str] = []
    restart_pids: list[int] = []
    kill_events: list[dict[str, Any]] = []
    redelivery_observed = 0
    barrier_observed = 0
    kombu_debug: dict[str, Any] | None = None

    for i in range(n):
        task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S2", "crash", str(i)))
        task_ids.append(task_id)

        celery_app.send_task(
            task_name,
            kwargs={
                "tenant_id": str(ctx.tenant_a),
                "correlation_id": task_id,
                "effect_key": f"R4_S2_{i}",
            },
            task_id=task_id,
        )
        if i == 0:
            kombu_debug = await _kombu_payload_debug(conn, task_id=task_id, task_name_substr=task_name)
            print("R4_S2_KOMBU_PAYLOAD_DEBUG", json.dumps(kombu_debug, sort_keys=True))

        barrier = await _barrier_row(
            conn,
            tenant_id=ctx.tenant_a,
            task_id=task_id,
            scenario="S2_CrashAfterWritePreAck",
            timeout_s=30.0,
        )
        if not barrier:
            print(f"R4_S2_BARRIER_TIMEOUT task_id={task_id}")
            break

        barrier_observed += 1
        print(
            "R4_S2_BARRIER_OBSERVED",
            f"task_id={task_id}",
            f"attempt_no={barrier['attempt_no']}",
            f"task_worker_pid={barrier['worker_pid']}",
            f"worker_main_pid={worker_pid}",
            f"wrote_at={barrier['wrote_at']}",
        )

        kill_since = await conn.fetchval("SELECT clock_timestamp()")
        kill = worker.kill(sig=9, timeout_s=30.0)
        kill_events.append(kill)

        worker_pid = worker.restart()
        restart_pids.append(worker_pid)
        print("R4_S2_WORKER_PING_AFTER_RESTART", json.dumps(_ping_worker_safe(timeout_s=20.0), sort_keys=True))

        attempt = await _wait_for_redelivery_attempt(
            conn,
            tenant_id=ctx.tenant_a,
            task_id=task_id,
            scenario="S2_CrashAfterWritePreAck",
            min_attempt_no=2,
            timeout_s=30.0,
            since_ts=kill_since,
        )
        if attempt is not None and attempt >= 2:
            redelivery_observed += 1
            print(f"R4_S2_REDELIVERED task_id={task_id} attempt={attempt}")

    s_end = _now_utc()
    effects = await _count_side_effects(conn, tenant_id=ctx.tenant_a, task_ids=task_ids, since=s_start, until=s_end)
    attempts = await _attempt_stats(
        conn,
        tenant_id=ctx.tenant_a,
        scenario="S2_CrashAfterWritePreAck",
        task_ids=task_ids,
        since=s_start,
        until=s_end,
    )

    crash_markers_ok = (
        barrier_observed == n
        and len(kill_events) == n
        and len(restart_pids) == n
        and redelivery_observed == n
        and all(e.get("exit_code") is not None for e in kill_events)
        and attempts["task_count_observed"] == n
        and attempts["attempts_min_per_task"] >= 2
    )
    passed = crash_markers_ok and effects["rows"] == n and effects["duplicate_task_ids"] == 0

    verdict = {
        "scenario": "S2_CrashAfterWritePreAck",
        "N": n,
        "candidate_sha": ctx.candidate_sha,
        "run_url": ctx.run_url,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"worker_side_effects": effects, "attempts": attempts},
        "worker_observed": {
            "worker_pid_before": worker.pid_history[0] if worker.pid_history else None,
            "worker_pid_after": worker.pid_history[-1] if worker.pid_history else None,
            "kill_sig": 9,
            "kill_issued": True,
            "worker_exit_codes": [e.get("exit_code") for e in kill_events],
            "worker_pid_restarts": restart_pids,
            "redelivery_observed_count": redelivery_observed,
            "kombu_payload_debug": kombu_debug,
            "crash_physics": {
                "barrier_observed_count": barrier_observed,
                "kill_issued_count": len(kill_events),
                "worker_exited_count": sum(1 for e in kill_events if e.get("exit_code") is not None),
                "worker_restarted_count": len(restart_pids),
                "redelivery_observed_count": redelivery_observed,
            },
        },
        "passed": passed,
    }
    _verdict_block(f"S2_CrashAfterWritePreAck_N{n}", verdict)
    print("R4_S2_END")
    return verdict


async def scenario_rls_probe(ctx: ScenarioCtx, conn: asyncpg.Connection) -> dict[str, Any]:
    correlation_id_prefix = f"r4:{ctx.candidate_sha}:S3"
    print(
        f"R4_S3_START RLSProbe N=1 tenant_a={ctx.tenant_a} tenant_b={ctx.tenant_b} correlation_id_prefix={correlation_id_prefix}"
    )
    s_start = _now_utc()

    # Seed a tenant-B row into a tenant-scoped table and probe it from tenant-A task context
    target_effect_key = f"R4_RLS_TARGET_{ctx.candidate_sha[:7]}"
    seed_task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S3", "seed_b"))
    await _seed_worker_side_effect(conn, ctx.tenant_b, task_id=seed_task_id, effect_key=target_effect_key)

    task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S3", "rls_probe"))
    r = celery_app.send_task(
        "app.tasks.r4_failure_semantics.rls_cross_tenant_probe",
        kwargs={
            "tenant_id": str(ctx.tenant_a),
            "correlation_id": task_id,
            "target_effect_key": target_effect_key,
        },
        task_id=task_id,
    )
    result = r.get(timeout=30)

    # Missing-tenant probe should hard-fail and land in worker DLQ
    bad_task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S3", "missing_tenant"))
    bad = celery_app.send_task(
        "app.tasks.r4_failure_semantics.rls_cross_tenant_probe",
        kwargs={
            "tenant_id": "not-a-uuid",
            "correlation_id": bad_task_id,
            "target_effect_key": target_effect_key,
        },
        task_id=bad_task_id,
    )
    try:
        bad.get(timeout=30)
        bad_failed = False
    except Exception:
        bad_failed = True

    s_end = _now_utc()
    dlq = await _count_worker_failed_jobs(
        conn,
        task_name="app.tasks.r4_failure_semantics.rls_cross_tenant_probe",
        task_ids=[bad_task_id],
        since=s_start,
        until=s_end,
    )

    passed = int(result.get("visible_count", -1)) == 0 and bad_failed and dlq["rows"] == 1

    verdict = {
        "scenario": "S3_RLSProbe",
        "N": 1,
        "candidate_sha": ctx.candidate_sha,
        "run_url": ctx.run_url,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"missing_tenant_dlq_rows": dlq["rows"]},
        "worker_observed": {"visible_count_for_tenant_a": int(result.get("visible_count", -1)), "bad_failed": bad_failed},
        "passed": passed,
    }
    _verdict_block("S3_RLSProbe_N1", verdict)
    print("R4_S3_END")
    return verdict


async def scenario_runaway(ctx: ScenarioCtx, conn: asyncpg.Connection, *, sentinel_n: int) -> dict[str, Any]:
    correlation_id_prefix = f"r4:{ctx.candidate_sha}:S4"
    print(
        f"R4_S4_START RunawayNoStarve N={sentinel_n} tenant_a={ctx.tenant_a} tenant_b={ctx.tenant_b} correlation_id_prefix={correlation_id_prefix}"
    )
    s_start = _now_utc()

    runaway_task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S4", "runaway"))
    runaway = celery_app.send_task(
        "app.tasks.r4_failure_semantics.runaway_sleep",
        kwargs={"tenant_id": str(ctx.tenant_a), "correlation_id": runaway_task_id, "sleep_s": 30},
        task_id=runaway_task_id,
    )

    # Give runaway a head start so it occupies a worker slot
    time.sleep(0.5)

    sentinel_task_ids: list[str] = []
    for i in range(sentinel_n):
        tid = str(_uuid_deterministic("r4", ctx.candidate_sha, "S4", "sentinel", str(i)))
        sentinel_task_ids.append(tid)
        celery_app.send_task(
            "app.tasks.r4_failure_semantics.sentinel_side_effect",
            kwargs={"tenant_id": str(ctx.tenant_a), "correlation_id": tid, "effect_key": f"R4_S4_{i}"},
            task_id=tid,
        )

    deadline = time.time() + 180.0
    effects: dict[str, int] = {"rows": 0, "duplicate_task_ids": 0}
    while time.time() < deadline:
        now = _now_utc()
        effects = await _count_side_effects(
            conn, tenant_id=ctx.tenant_a, task_ids=sentinel_task_ids, since=s_start, until=now
        )
        if effects["rows"] >= sentinel_n:
            break
        await asyncio.sleep(0.5)

    runaway_outcome = "unknown"
    try:
        runaway.get(timeout=30)
        runaway_outcome = "completed_unexpectedly"
    except Exception as exc:  # noqa: BLE001 - expected timeout failure mode
        runaway_outcome = exc.__class__.__name__

    s_end = _now_utc()
    effects = await _count_side_effects(
        conn, tenant_id=ctx.tenant_a, task_ids=sentinel_task_ids, since=s_start, until=s_end
    )

    passed = effects["rows"] == sentinel_n and effects["duplicate_task_ids"] == 0 and runaway_outcome != "completed_unexpectedly"

    verdict = {
        "scenario": "S4_RunawayNoStarve",
        "N": sentinel_n,
        "candidate_sha": ctx.candidate_sha,
        "run_url": ctx.run_url,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"worker_side_effects": effects},
        "worker_observed": {"runaway_outcome": runaway_outcome, "sentinel_rows_observed": effects["rows"]},
        "passed": passed,
    }
    _verdict_block(f"S4_RunawayNoStarve_N{sentinel_n}", verdict)
    print("R4_S4_END")
    return verdict


async def scenario_least_privilege(ctx: ScenarioCtx, conn: asyncpg.Connection) -> dict[str, Any]:
    correlation_id_prefix = f"r4:{ctx.candidate_sha}:S5"
    print(
        f"R4_S5_START LeastPrivilege N=1 tenant_a={ctx.tenant_a} tenant_b={ctx.tenant_b} correlation_id_prefix={correlation_id_prefix}"
    )
    s_start = _now_utc()

    task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S5", "priv"))
    r = celery_app.send_task(
        "app.tasks.r4_failure_semantics.privilege_probes",
        kwargs={"tenant_id": str(ctx.tenant_a), "correlation_id": task_id},
        task_id=task_id,
    )
    probes = r.get(timeout=60)

    required_fail = [
        "ddl_create_table",
        "disable_rls",
        "force_rls",
        "bypass_rls_attempt",
        "create_role",
        "grant_admin_role",
        "set_bypassrls",
    ]
    failures = {k: probes.get(k, {}).get("ok") == "false" for k in required_fail}
    passed = all(failures.values())

    s_end = _now_utc()
    dlq = await _count_worker_failed_jobs(
        conn,
        task_name="app.tasks.r4_failure_semantics.privilege_probes",
        task_ids=[task_id],
        since=s_start,
        until=s_end,
    )

    verdict = {
        "scenario": "S5_LeastPrivilege",
        "N": 1,
        "candidate_sha": ctx.candidate_sha,
        "run_url": ctx.run_url,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"worker_failed_jobs_rows": dlq["rows"]},
        "worker_observed": {"probe_results": probes, "required_failures": failures},
        "passed": passed and dlq["rows"] == 0,
    }
    _verdict_block("S5_LeastPrivilege_N1", verdict)
    print("R4_S5_END")
    return verdict


async def main() -> int:
    candidate_sha = _env("CANDIDATE_SHA", _git_rev_parse_head())
    run_url = _env("RUN_URL", "UNKNOWN")
    admin_db = _env("R4_ADMIN_DATABASE_URL")

    tenant_a = _uuid_deterministic("r4", candidate_sha, "tenant_a")
    tenant_b = _uuid_deterministic("r4", candidate_sha, "tenant_b")
    ctx = ScenarioCtx(candidate_sha=candidate_sha, run_url=run_url, tenant_a=tenant_a, tenant_b=tenant_b)

    window_start = _now_utc()
    print(f"R4_WINDOW_START {_utc_iso(window_start)} {candidate_sha}")

    concurrency = int(_env("R4_WORKER_CONCURRENCY", "4") or 4)
    crash_concurrency = int(_env("R4_CRASH_WORKER_CONCURRENCY", "1") or 1)
    default_pool = _env("R4_WORKER_POOL", "prefork")
    poison_pool = _env("R4_POISON_WORKER_POOL", default_pool)
    crash_pool = _env("R4_CRASH_WORKER_POOL", default_pool)
    main_pool = _env("R4_MAIN_WORKER_POOL", default_pool)

    poison_worker = WorkerSupervisor(concurrency=concurrency, pool=poison_pool, log_prefix="celery_harness_worker_poison")
    poison_worker_pid_initial = poison_worker.start()
    ping = _ping_worker_safe(timeout_s=25.0)
    print("R4_WORKER_PING_POISON_INITIAL", json.dumps(ping, sort_keys=True))

    main_worker: WorkerSupervisor | None = None
    crash_worker: WorkerSupervisor | None = None

    broker_transport_options = getattr(celery_app.conf, "broker_transport_options", None)
    broker_recovery_config = {
        "visibility_timeout_s": int(_env("CELERY_BROKER_VISIBILITY_TIMEOUT_S", "0") or 0),
        "sweep_interval_s": float(
            _env("CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S", _env("CELERY_BROKER_POLLING_INTERVAL_S", "0.0")) or 0.0
        ),
        "task_name_filter": _env("CELERY_BROKER_RECOVERY_TASK_NAME_FILTER", ""),
    }
    config_dump = {
        "candidate_sha": candidate_sha,
        "run_url": run_url,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "celery": {
            "broker_url": celery_app.conf.broker_url,
            "result_backend": celery_app.conf.result_backend,
            "broker_transport_options": broker_transport_options,
            "broker_recovery": broker_recovery_config,
            "acks_late": bool(getattr(celery_app.conf, "task_acks_late", False)),
            "reject_on_worker_lost": bool(getattr(celery_app.conf, "task_reject_on_worker_lost", False)),
            "acks_on_failure_or_timeout": bool(getattr(celery_app.conf, "task_acks_on_failure_or_timeout", False)),
            "prefetch_multiplier": int(getattr(celery_app.conf, "worker_prefetch_multiplier", 0) or 0),
        },
        "tenants": {"tenant_a": str(tenant_a), "tenant_b": str(tenant_b)},
        "run_start_utc": _utc_iso(window_start),
    }
    print("=== R4_ENV ===")
    print(json.dumps(config_dump, indent=2, sort_keys=True))

    print(
        "R4_CONFIG",
        json.dumps(
            {
                "concurrency": concurrency,
                "crash_concurrency": crash_concurrency,
                "prefetch": config_dump["celery"]["prefetch_multiplier"],
                "acks_late": config_dump["celery"]["acks_late"],
                "reject_on_worker_lost": config_dump["celery"]["reject_on_worker_lost"],
                "acks_on_failure_or_timeout": config_dump["celery"]["acks_on_failure_or_timeout"],
                "broker_transport_options": broker_transport_options,
                "broker_recovery": broker_recovery_config,
                "time_limits": {"runaway_soft_s": 2, "runaway_hard_s": 4},
                "retry_policy": {"poison_max_retries": 3, "poison_backoff_cap_s": 4, "poison_jitter_s": "0..1"},
                "worker_pool_default": default_pool,
                "worker_pool_poison": poison_pool,
                "worker_pool_crash": crash_pool,
                "worker_pool_main": main_pool,
                "worker_pid_poison_initial": poison_worker_pid_initial,
                "worker_ping": ping,
            },
            sort_keys=True,
        ),
    )

    conn = await _pg(admin_db)
    try:
        print("R4_DB_CONN_SNAPSHOT_START", json.dumps(await _db_conn_snapshot(conn), sort_keys=True))
        await _seed_tenant(conn, tenant_a, label="A")
        await _seed_tenant(conn, tenant_b, label="B")

        poison_n = int(_env("R4_POISON_N", "10"))
        crash_n = int(_env("R4_CRASH_N", "10"))
        sentinel_n = int(_env("R4_SENTINEL_N", "10"))

        s1 = await _run_safely(
            f"S1_PoisonPill_N{poison_n}",
            "S1_PoisonPill",
            scenario_poison_pill(ctx, conn, n=poison_n),
            candidate_sha=candidate_sha,
            run_url=run_url,
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            n=poison_n,
            conn=conn,
        )
        print("R4_S1_WORKER_PING_AFTER", json.dumps(_ping_worker_safe(), sort_keys=True))
        print("R4_DB_CONN_SNAPSHOT_AFTER_S1", json.dumps(await _db_conn_snapshot(conn), sort_keys=True))

        poison_worker.ensure_dead()
        _kill_stray_celery_workers()
        print("R4_DB_CONN_SNAPSHOT_AFTER_POISON_WORKER_STOP", json.dumps(await _db_conn_snapshot(conn), sort_keys=True))

        crash_worker = WorkerSupervisor(concurrency=crash_concurrency, pool=crash_pool, log_prefix="celery_harness_worker_crash")
        crash_worker_pid_initial = crash_worker.start()
        print(f"R4_WORKER_CRASH_STARTED pid={crash_worker_pid_initial}")
        print("R4_WORKER_PING_CRASH_INITIAL", json.dumps(_ping_worker_safe(timeout_s=20.0), sort_keys=True))
        print("R4_DB_CONN_SNAPSHOT_AFTER_CRASH_WORKER_START", json.dumps(await _db_conn_snapshot(conn), sort_keys=True))

        s2 = await _run_safely(
            f"S2_CrashAfterWritePreAck_N{crash_n}",
            "S2_CrashAfterWritePreAck",
            scenario_crash_after_write(ctx, conn, n=crash_n, worker=crash_worker),
            candidate_sha=candidate_sha,
            run_url=run_url,
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            n=crash_n,
            conn=conn,
        )
        print("R4_S2_WORKER_PING_AFTER", json.dumps(_ping_worker_safe(), sort_keys=True))
        print("R4_DB_CONN_SNAPSHOT_AFTER_S2", json.dumps(await _db_conn_snapshot(conn), sort_keys=True))

        crash_worker.ensure_dead()
        _kill_stray_celery_workers()
        print("R4_DB_CONN_SNAPSHOT_AFTER_CRASH_WORKER_STOP", json.dumps(await _db_conn_snapshot(conn), sort_keys=True))

        main_worker = WorkerSupervisor(concurrency=concurrency, pool=main_pool, log_prefix="celery_harness_worker_main")
        worker_pid_initial = main_worker.start()
        print(f"R4_WORKER_MAIN_STARTED pid={worker_pid_initial}")
        print("R4_WORKER_PING_MAIN_INITIAL", json.dumps(_ping_worker_safe(timeout_s=20.0), sort_keys=True))
        print("R4_DB_CONN_SNAPSHOT_AFTER_MAIN_WORKER_START", json.dumps(await _db_conn_snapshot(conn), sort_keys=True))

        s3 = await _run_safely(
            "S3_RLSProbe_N1",
            "S3_RLSProbe",
            scenario_rls_probe(ctx, conn),
            candidate_sha=candidate_sha,
            run_url=run_url,
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            n=1,
            conn=conn,
        )
        print("R4_S3_WORKER_PING_AFTER", json.dumps(_ping_worker_safe(), sort_keys=True))

        s4 = await _run_safely(
            f"S4_RunawayNoStarve_N{sentinel_n}",
            "S4_RunawayNoStarve",
            scenario_runaway(ctx, conn, sentinel_n=sentinel_n),
            candidate_sha=candidate_sha,
            run_url=run_url,
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            n=sentinel_n,
            conn=conn,
        )
        print("R4_S4_WORKER_PING_AFTER", json.dumps(_ping_worker_safe(), sort_keys=True))

        s5 = await _run_safely(
            "S5_LeastPrivilege_N1",
            "S5_LeastPrivilege",
            scenario_least_privilege(ctx, conn),
            candidate_sha=candidate_sha,
            run_url=run_url,
            tenant_a=tenant_a,
            tenant_b=tenant_b,
            n=1,
            conn=conn,
        )

        all_passed = all(v.get("passed") is True for v in [s1, s2, s3, s4, s5])
    finally:
        poison_worker.ensure_dead()
        _kill_stray_celery_workers()
        if crash_worker is not None:
            crash_worker.ensure_dead()
            _kill_stray_celery_workers()
        if main_worker is not None:
            main_worker.ensure_dead()
            _kill_stray_celery_workers()
        await conn.close()

    window_end = _now_utc()
    print(f"R4_WINDOW_END {_utc_iso(window_end)} {candidate_sha}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

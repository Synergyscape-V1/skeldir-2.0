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
    tenant_a: UUID
    tenant_b: UUID


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


async def _seed_attribution_event(conn: asyncpg.Connection, tenant_id: UUID, *, external_event_id: str) -> None:
    await conn.execute(
        """
        INSERT INTO attribution_events (tenant_id, occurred_at, external_event_id, revenue_cents, raw_payload)
        VALUES ($1, NOW(), $2, 0, $3::jsonb)
        """,
        str(tenant_id),
        external_event_id,
        json.dumps({"marker": "R4_RLS_PROBE", "external_event_id": external_event_id}),
    )


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


async def _count_worker_failed_jobs(
    conn: asyncpg.Connection,
    *,
    task_name: str,
    task_ids: list[str],
    since: datetime,
    until: datetime,
) -> dict[str, int]:
    if not task_ids:
        return {"rows": 0, "max_retry_count": 0}
    rows = int(
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
    return {"rows": rows, "max_retry_count": max_retry}


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


async def scenario_poison_pill(ctx: ScenarioCtx, conn: asyncpg.Connection, *, n: int) -> dict[str, Any]:
    correlation_id_prefix = f"r4:{ctx.candidate_sha}:S1"
    print(
        f"R4_S1_START PoisonPill N={n} tenant_a={ctx.tenant_a} tenant_b={ctx.tenant_b} correlation_id_prefix={correlation_id_prefix}"
    )
    s_start = _now_utc()

    task_name = "app.tasks.r4_failure_semantics.poison_pill"
    task_ids: list[str] = []
    results = []
    for i in range(n):
        task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S1", "poison", str(i)))
        task_ids.append(task_id)
        results.append(
            celery_app.send_task(
                task_name,
                kwargs={
                    "tenant_id": str(ctx.tenant_a),
                    "correlation_id": task_id,
                    "marker": f"R4_S1_{i}",
                },
                task_id=task_id,
            )
        )

    _wait_for_results(results, timeout_s=120.0)
    failures = sum(1 for r in results if r.failed())
    successes = sum(1 for r in results if r.successful())

    s_end = _now_utc()
    dlq = await _count_worker_failed_jobs(conn, task_name=task_name, task_ids=task_ids, since=s_start, until=s_end)
    effects = await _count_side_effects(conn, tenant_id=ctx.tenant_a, task_ids=task_ids, since=s_start, until=s_end)

    passed = (
        failures == n
        and successes == 0
        and dlq["rows"] == n
        and dlq["max_retry_count"] <= 3
        and effects["rows"] == 0
    )

    verdict = {
        "scenario": "S1_PoisonPill",
        "N": n,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"worker_failed_jobs": dlq, "worker_side_effects": effects},
        "worker_observed": {"failed_results": failures, "successful_results": successes},
        "passed": passed,
    }
    _verdict_block(f"S1_PoisonPill_N{n}", verdict)
    print("R4_S1_END")
    return verdict


async def scenario_crash_after_write(ctx: ScenarioCtx, conn: asyncpg.Connection, *, n: int) -> dict[str, Any]:
    correlation_id_prefix = f"r4:{ctx.candidate_sha}:S2"
    print(
        f"R4_S2_START CrashAfterWritePreAck N={n} tenant_a={ctx.tenant_a} tenant_b={ctx.tenant_b} correlation_id_prefix={correlation_id_prefix}"
    )
    s_start = _now_utc()

    task_name = "app.tasks.r4_failure_semantics.crash_after_write_pre_ack"
    task_ids: list[str] = []
    results = []
    for i in range(n):
        task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S2", "crash", str(i)))
        task_ids.append(task_id)
        results.append(
            celery_app.send_task(
                task_name,
                kwargs={
                    "tenant_id": str(ctx.tenant_a),
                    "correlation_id": task_id,
                    "effect_key": f"R4_S2_{i}",
                },
                task_id=task_id,
            )
        )

    _wait_for_results(results, timeout_s=120.0)
    failures = sum(1 for r in results if r.failed())
    successes = sum(1 for r in results if r.successful())

    s_end = _now_utc()
    effects = await _count_side_effects(conn, tenant_id=ctx.tenant_a, task_ids=task_ids, since=s_start, until=s_end)
    passed = successes == n and failures == 0 and effects["rows"] == n and effects["duplicate_task_ids"] == 0

    verdict = {
        "scenario": "S2_CrashAfterWritePreAck",
        "N": n,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"worker_side_effects": effects},
        "worker_observed": {"failed_results": failures, "successful_results": successes},
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

    # Seed a tenant-B event and probe it from tenant-A task context
    target_external_event_id = f"R4_RLS_TARGET_{ctx.candidate_sha[:7]}"
    await _seed_attribution_event(conn, ctx.tenant_b, external_event_id=target_external_event_id)

    task_id = str(_uuid_deterministic("r4", ctx.candidate_sha, "S3", "rls_probe"))
    r = celery_app.send_task(
        "app.tasks.r4_failure_semantics.rls_cross_tenant_probe",
        kwargs={
            "tenant_id": str(ctx.tenant_a),
            "correlation_id": task_id,
            "target_external_event_id": target_external_event_id,
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
            "target_external_event_id": target_external_event_id,
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
    sentinels = []
    for i in range(sentinel_n):
        tid = str(_uuid_deterministic("r4", ctx.candidate_sha, "S4", "sentinel", str(i)))
        sentinel_task_ids.append(tid)
        sentinels.append(
            celery_app.send_task(
                "app.tasks.r4_failure_semantics.sentinel_side_effect",
                kwargs={"tenant_id": str(ctx.tenant_a), "correlation_id": tid, "effect_key": f"R4_S4_{i}"},
                task_id=tid,
            )
        )

    _wait_for_results(sentinels, timeout_s=120.0)
    sent_ok = sum(1 for r in sentinels if r.successful())

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

    passed = sent_ok == sentinel_n and effects["rows"] == sentinel_n and effects["duplicate_task_ids"] == 0 and runaway_outcome != "completed_unexpectedly"

    verdict = {
        "scenario": "S4_RunawayNoStarve",
        "N": sentinel_n,
        "tenant_a": str(ctx.tenant_a),
        "tenant_b": str(ctx.tenant_b),
        "db_truth": {"worker_side_effects": effects},
        "worker_observed": {"runaway_outcome": runaway_outcome, "sentinel_success": sent_ok},
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
    ctx = ScenarioCtx(candidate_sha=candidate_sha, tenant_a=tenant_a, tenant_b=tenant_b)

    window_start = _now_utc()
    print(f"R4_WINDOW_START {_utc_iso(window_start)} {candidate_sha}")

    config_dump = {
        "candidate_sha": candidate_sha,
        "run_url": run_url,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "celery": {
            "broker_url": celery_app.conf.broker_url,
            "result_backend": celery_app.conf.result_backend,
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

    # Verify worker is alive and DB role is least-privileged (app_user)
    ping = _ping_worker()
    print(
        "R4_CONFIG",
        json.dumps(
            {
                "concurrency": int(_env("R4_WORKER_CONCURRENCY", "0") or 0),
                "prefetch": config_dump["celery"]["prefetch_multiplier"],
                "acks_late": config_dump["celery"]["acks_late"],
                "reject_on_worker_lost": config_dump["celery"]["reject_on_worker_lost"],
                "acks_on_failure_or_timeout": config_dump["celery"]["acks_on_failure_or_timeout"],
                "time_limits": {"runaway_soft_s": 2, "runaway_hard_s": 4},
                "retry_policy": {"poison_max_retries": 3, "poison_backoff_cap_s": 4, "poison_jitter_s": "0..1"},
                "worker_ping": ping,
            },
            sort_keys=True,
        ),
    )

    conn = await _pg(admin_db)
    try:
        await _seed_tenant(conn, tenant_a, label="A")
        await _seed_tenant(conn, tenant_b, label="B")

        s1 = await scenario_poison_pill(ctx, conn, n=int(_env("R4_POISON_N", "10")))
        _ping_worker()
        s2 = await scenario_crash_after_write(ctx, conn, n=int(_env("R4_CRASH_N", "10")))
        _ping_worker()
        s3 = await scenario_rls_probe(ctx, conn)
        _ping_worker()
        s4 = await scenario_runaway(ctx, conn, sentinel_n=int(_env("R4_SENTINEL_N", "10")))
        _ping_worker()
        s5 = await scenario_least_privilege(ctx, conn)

        all_passed = all(v.get("passed") is True for v in [s1, s2, s3, s4, s5])
    finally:
        await conn.close()

    window_end = _now_utc()
    print(f"R4_WINDOW_END {_utc_iso(window_end)} {candidate_sha}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

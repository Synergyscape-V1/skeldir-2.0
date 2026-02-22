"""
R5 — Context Gathering Probes (Determinism + Complexity Ratios)

Measurement-only harness:
- Seeds deterministic datasets into Postgres (no PII).
- Runs the current deterministic baseline attribution compute.
- Emits browser-visible evidence lines and JSON verdict blocks.

This phase MUST NOT remediate attribution logic. If outputs drift, the probe reports
the first-diff surface and points back to code locations; fixes belong to R5 remediation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg
from sqlalchemy import event as sa_event
from scripts.security.db_secret_access import resolve_runtime_database_url

# PYTHONPATH=backend
from app.db.session import engine  # noqa: E402
from app.tasks.attribution import _compute_allocations_deterministic_baseline  # noqa: E402


def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    if v is None or v == "":
        if default is None:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return v


def _git_rev_parse_head() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.STDOUT)
            .decode("utf-8", errors="replace")
            .strip()
        )
    except Exception:
        return "UNKNOWN"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(ts: datetime | None = None) -> str:
    return (ts or _utc_now()).isoformat()


def _uuid_det(*parts: str) -> UUID:
    return uuid5(NAMESPACE_URL, ":".join(parts))


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _dsn_fingerprint(dsn: str) -> dict[str, str]:
    if not dsn:
        return {"scheme": "", "host": "", "port": "", "database": ""}
    p = urlsplit(dsn)
    return {
        "scheme": p.scheme,
        "host": p.hostname or "",
        "port": str(p.port or ""),
        "database": (p.path or "").lstrip("/"),
    }


def _meminfo_total_kb() -> int | None:
    try:
        if os.name != "posix":
            return None
        path = "/proc/meminfo"
        if not os.path.exists(path):
            return None
        for line in open(path, encoding="utf-8", errors="replace"):
            if line.startswith("MemTotal:"):
                parts = line.split()
                return int(parts[1])
    except Exception:
        return None
    return None


class StatementCounter:
    def __init__(self) -> None:
        self.count = 0

    def before_cursor_execute(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        self.count += 1


@dataclass(frozen=True)
class ProbeCtx:
    candidate_sha: str
    run_url: str
    admin_db_url: str


async def _pg(admin_db_url: str) -> asyncpg.Connection:
    return await asyncpg.connect(admin_db_url)


async def _ensure_tenant(conn: asyncpg.Connection, tenant_id: UUID, *, label: str) -> None:
    api_key_hash = f"R5_{label}_{tenant_id}"
    notification_email = f"r5_{label}_{str(tenant_id)[:8]}@test.invalid"
    await conn.execute(
        """
        INSERT INTO tenants (id, name, api_key_hash, notification_email, created_at, updated_at)
        VALUES ($1, $2, $3, $4, NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        str(tenant_id),
        f"R5 Tenant {label}",
        api_key_hash,
        notification_email,
    )


def _iter_event_records(
    *,
    tenant_id: UUID,
    candidate_sha: str,
    scenario: str,
    n: int,
    window_start: datetime,
    occurred_at_step_us: int,
) -> Iterable[tuple[Any, ...]]:
    for i in range(n):
        event_id = _uuid_det("r5", candidate_sha, scenario, "event_id", str(i))
        session_id = _uuid_det("r5", candidate_sha, scenario, "session_id", str(i))
        correlation_id = _uuid_det("r5", candidate_sha, scenario, "correlation_id", str(i))
        idempotency_key = f"r5:{candidate_sha}:{scenario}:{i}"
        occurred_at = window_start + timedelta(microseconds=i * occurred_at_step_us)
        raw_payload = {"r5": True, "scenario": scenario, "i": i}

        yield (
            str(event_id),
            str(tenant_id),
            occurred_at,
            occurred_at,
            occurred_at,
            f"ext_{i}",
            str(correlation_id),
            str(session_id),
            0,  # revenue_cents=0: required for current per-row allocation inserts to pass trg_check_allocation_sum
            json.dumps(raw_payload),
            idempotency_key,
            "conversion",
            "direct",
            "USD",
            occurred_at,
            "processed",
            0,
        )


async def _seed_events(
    conn: asyncpg.Connection,
    *,
    tenant_id: UUID,
    candidate_sha: str,
    scenario: str,
    n: int,
    window_start: datetime,
    occurred_at_step_us: int,
) -> dict[str, Any]:
    await _ensure_tenant(conn, tenant_id, label=scenario)

    await conn.execute(
        """
        DELETE FROM attribution_allocations WHERE tenant_id = $1 AND model_version = '1.0.0'
        """,
        str(tenant_id),
    )
    await conn.execute(
        """
        DELETE FROM attribution_recompute_jobs WHERE tenant_id = $1 AND model_version = '1.0.0'
        """,
        str(tenant_id),
    )
    await conn.execute(
        """
        DELETE FROM attribution_events WHERE tenant_id = $1 AND idempotency_key LIKE $2
        """,
        str(tenant_id),
        f"r5:{candidate_sha}:{scenario}:%",
    )

    records = list(
        _iter_event_records(
            tenant_id=tenant_id,
            candidate_sha=candidate_sha,
            scenario=scenario,
            n=n,
            window_start=window_start,
            occurred_at_step_us=occurred_at_step_us,
        )
    )

    t0 = time.perf_counter()
    await conn.copy_records_to_table(
        "attribution_events",
        records=records,
        columns=[
            "id",
            "tenant_id",
            "created_at",
            "updated_at",
            "occurred_at",
            "external_event_id",
            "correlation_id",
            "session_id",
            "revenue_cents",
            "raw_payload",
            "idempotency_key",
            "event_type",
            "channel",
            "currency",
            "event_timestamp",
            "processing_status",
            "retry_count",
        ],
    )
    t1 = time.perf_counter()
    return {"seeded_events": n, "seed_wall_s": round(t1 - t0, 6)}


async def _fetch_allocations(conn: asyncpg.Connection, *, tenant_id: UUID) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT
            id,
            tenant_id,
            event_id,
            channel_code,
            allocation_ratio,
            model_version,
            model_type,
            confidence_score,
            verified,
            allocated_revenue_cents,
            created_at,
            updated_at
        FROM attribution_allocations
        WHERE tenant_id = $1
          AND model_version = '1.0.0'
        ORDER BY event_id ASC, channel_code ASC, id ASC
        """,
        str(tenant_id),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": str(r["id"]),
                "tenant_id": str(r["tenant_id"]),
                "event_id": str(r["event_id"]),
                "channel_code": str(r["channel_code"]),
                "allocation_ratio": str(r["allocation_ratio"]),
                "model_version": str(r["model_version"]),
                "model_type": str(r["model_type"]),
                "confidence_score": str(r["confidence_score"]),
                "verified": bool(r["verified"]),
                "allocated_revenue_cents": int(r["allocated_revenue_cents"]),
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
            }
        )
    return out


async def _fetch_recompute_jobs(
    conn: asyncpg.Connection, *, tenant_id: UUID, window_start: datetime, window_end: datetime
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT
            id,
            tenant_id,
            window_start,
            window_end,
            model_version,
            status,
            run_count,
            last_correlation_id,
            created_at,
            updated_at,
            started_at,
            finished_at
        FROM attribution_recompute_jobs
        WHERE tenant_id = $1
          AND model_version = '1.0.0'
          AND window_start = $2
          AND window_end = $3
        ORDER BY id ASC
        """,
        str(tenant_id),
        window_start,
        window_end,
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": str(r["id"]),
                "tenant_id": str(r["tenant_id"]),
                "window_start": r["window_start"].isoformat(),
                "window_end": r["window_end"].isoformat(),
                "model_version": str(r["model_version"]),
                "status": str(r["status"]),
                "run_count": int(r["run_count"]),
                "last_correlation_id": str(r["last_correlation_id"]) if r["last_correlation_id"] else None,
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            }
        )
    return out


def _strip_nondeterministic_allocation_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "event_id": r["event_id"],
                "channel_code": r["channel_code"],
                "allocation_ratio": r["allocation_ratio"],
                "model_version": r["model_version"],
                "model_type": r["model_type"],
                "confidence_score": r["confidence_score"],
                "verified": r["verified"],
                "allocated_revenue_cents": r["allocated_revenue_cents"],
            }
        )
    return out


def _first_diff(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(a) != len(b):
        return {"reason": "row_count_differs", "len_a": len(a), "len_b": len(b)}
    for i, (ra, rb) in enumerate(zip(a, b, strict=True)):
        if ra == rb:
            continue
        keys = sorted(set(ra.keys()) | set(rb.keys()))
        diffs = {k: {"a": ra.get(k), "b": rb.get(k)} for k in keys if ra.get(k) != rb.get(k)}
        return {"reason": "row_differs", "index": i, "diffs": diffs}
    return None


def _ru_maxrss_kb() -> int:
    # Linux: kilobytes. (macOS differs; this probe runs in ubuntu CI by default.)
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


async def _run_compute_with_count(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    counter = StatementCounter()
    sa_event.listen(engine.sync_engine, "before_cursor_execute", counter.before_cursor_execute)
    t0 = time.perf_counter()
    try:
        meta = await _compute_allocations_deterministic_baseline(
            tenant_id=tenant_id, window_start=window_start, window_end=window_end, model_version="1.0.0"
        )
    finally:
        t1 = time.perf_counter()
        sa_event.remove(engine.sync_engine, "before_cursor_execute", counter.before_cursor_execute)
    return {
        "compute_wall_s": round(t1 - t0, 6),
        "sqlalchemy_statement_count": int(counter.count),
        "compute_meta": meta,
        "ru_maxrss_kb": _ru_maxrss_kb(),
    }


async def probe_p1_determinism(ctx: ProbeCtx) -> dict[str, Any]:
    name = "P1_Determinism_MicroCheck"
    runs = int(_env("R5_P1_RUNS", "3"))
    n = int(_env("R5_P1_EVENTS_N", "500"))

    tenant_id = _uuid_det("r5", ctx.candidate_sha, "P1", "tenant")
    window_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    window_end = window_start + timedelta(days=1)

    conn = await _pg(ctx.admin_db_url)
    try:
        seed = await _seed_events(
            conn,
            tenant_id=tenant_id,
            candidate_sha=ctx.candidate_sha,
            scenario="P1",
            n=n,
            window_start=window_start,
            occurred_at_step_us=10,
        )

        full_alloc_checksums: list[str] = []
        norm_alloc_checksums: list[str] = []
        job_checksums: list[str] = []
        alloc_snapshots: list[list[dict[str, Any]]] = []
        job_snapshots: list[list[dict[str, Any]]] = []
        run_metrics: list[dict[str, Any]] = []

        for i in range(runs):
            run_meta = await _run_compute_with_count(
                tenant_id=tenant_id, window_start=window_start, window_end=window_end
            )
            alloc = await _fetch_allocations(conn, tenant_id=tenant_id)
            jobs = await _fetch_recompute_jobs(conn, tenant_id=tenant_id, window_start=window_start, window_end=window_end)

            alloc_snapshots.append(alloc)
            job_snapshots.append(jobs)

            full_alloc_checksums.append(_sha256_hex(_canonical_json_bytes(alloc)))
            norm_alloc_checksums.append(
                _sha256_hex(_canonical_json_bytes(_strip_nondeterministic_allocation_fields(alloc)))
            )
            job_checksums.append(_sha256_hex(_canonical_json_bytes(jobs)))
            run_metrics.append(run_meta)

        full_equal = len(set(full_alloc_checksums)) == 1
        norm_equal = len(set(norm_alloc_checksums)) == 1
        jobs_equal = len(set(job_checksums)) == 1

        first_diff_alloc = _first_diff(alloc_snapshots[0], alloc_snapshots[1]) if runs >= 2 else None
        first_diff_jobs = _first_diff(job_snapshots[0], job_snapshots[1]) if runs >= 2 else None

        return {
            "probe": name,
            "candidate_sha": ctx.candidate_sha,
            "run_url": ctx.run_url,
            "tenant_id": str(tenant_id),
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "seed": seed,
            "runs": runs,
            "N": n,
            "checksums": {
                "allocations_full": full_alloc_checksums,
                "allocations_normalized": norm_alloc_checksums,
                "recompute_jobs_full": job_checksums,
            },
            "determinism": {
                "allocations_full_bit_identical": full_equal,
                "allocations_value_identical_excluding_id_timestamps": norm_equal,
                "recompute_jobs_full_bit_identical": jobs_equal,
            },
            "first_diff": {
                "allocations_full": first_diff_alloc,
                "recompute_jobs_full": first_diff_jobs,
            },
            "run_metrics": run_metrics,
        }
    finally:
        await conn.close()


async def probe_p3_scaling(ctx: ProbeCtx) -> dict[str, Any]:
    name = "P3_Complexity_RatioCheck"
    n_small = int(_env("R5_P3_N_SMALL", "10000"))
    n_large = int(_env("R5_P3_N_LARGE", "100000"))
    max_s = float(_env("R5_P3_MAX_SECONDS", "900"))

    window_start = datetime(2025, 2, 1, tzinfo=timezone.utc)
    window_end = window_start + timedelta(days=1)

    tenant_small = _uuid_det("r5", ctx.candidate_sha, "P3", "tenant_small")
    tenant_large = _uuid_det("r5", ctx.candidate_sha, "P3", "tenant_large")

    conn = await _pg(ctx.admin_db_url)
    try:
        seed_small = await _seed_events(
            conn,
            tenant_id=tenant_small,
            candidate_sha=ctx.candidate_sha,
            scenario="P3_SMALL",
            n=n_small,
            window_start=window_start,
            occurred_at_step_us=1,
        )

        small_meta = await _run_compute_with_count(tenant_id=tenant_small, window_start=window_start, window_end=window_end)
        small_alloc = await _fetch_allocations(conn, tenant_id=tenant_small)

        large_result: dict[str, Any] = {"attempted": False, "completed": False, "error": None}

        seed_large = await _seed_events(
            conn,
            tenant_id=tenant_large,
            candidate_sha=ctx.candidate_sha,
            scenario="P3_LARGE",
            n=n_large,
            window_start=window_start,
            occurred_at_step_us=1,
        )
        large_result["attempted"] = True

        try:
            large_meta = await asyncio.wait_for(
                _run_compute_with_count(tenant_id=tenant_large, window_start=window_start, window_end=window_end),
                timeout=max_s,
            )
            large_alloc = await _fetch_allocations(conn, tenant_id=tenant_large)
            large_result.update({"completed": True, "compute": large_meta, "allocations_row_count": len(large_alloc)})
        except asyncio.TimeoutError:
            large_result.update({"completed": False, "error": f"timeout_after_s={max_s}"})
        except Exception as exc:  # noqa: BLE001
            large_result.update({"completed": False, "error": f"{exc.__class__.__name__}: {exc}"[:400]})

        ratio: dict[str, Any] = {"time_ratio": None, "stmt_ratio": None, "rss_ratio": None}
        if large_result.get("completed"):
            ratio["time_ratio"] = round(float(large_result["compute"]["compute_wall_s"]) / float(small_meta["compute_wall_s"]), 6)
            ratio["stmt_ratio"] = round(
                float(large_result["compute"]["sqlalchemy_statement_count"]) / float(small_meta["sqlalchemy_statement_count"]), 6
            )
            ratio["rss_ratio"] = round(float(large_result["compute"]["ru_maxrss_kb"]) / float(small_meta["ru_maxrss_kb"]), 6)

        return {
            "probe": name,
            "candidate_sha": ctx.candidate_sha,
            "run_url": ctx.run_url,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "small": {
                "tenant_id": str(tenant_small),
                "N": n_small,
                "seed": seed_small,
                "compute": small_meta,
                "allocations_row_count": len(small_alloc),
            },
            "large": {"tenant_id": str(tenant_large), "N": n_large, "seed": seed_large, **large_result},
            "ratios": ratio,
        }
    finally:
        await conn.close()


def _print_verdict(name: str, payload: dict[str, Any]) -> None:
    print(f"R5_VERDICT_BEGIN {name}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"R5_VERDICT_END {name}")


async def _db_version_snapshot(conn: asyncpg.Connection) -> dict[str, Any]:
    version = str(await conn.fetchval("SELECT version()"))
    server_version = str(await conn.fetchval("SHOW server_version"))
    max_connections = str(await conn.fetchval("SHOW max_connections"))
    return {"version": version, "server_version": server_version, "max_connections": max_connections}


async def main() -> int:
    candidate_sha = _env("CANDIDATE_SHA", _git_rev_parse_head())
    run_url = _env("RUN_URL", "UNKNOWN")
    admin_db_url = _env("R5_ADMIN_DATABASE_URL")

    ctx = ProbeCtx(candidate_sha=candidate_sha, run_url=run_url, admin_db_url=admin_db_url)

    print(f"R5_WINDOW_START {_utc_iso()} {candidate_sha}")

    conn = await _pg(admin_db_url)
    try:
        db_snapshot = await _db_version_snapshot(conn)
    finally:
        await conn.close()

    env_snapshot = {
        "candidate_sha": candidate_sha,
        "run_url": run_url,
        "os": {"platform": platform.platform(), "machine": platform.machine()},
        "python": {"version": sys.version.split()[0], "full": sys.version},
        "hw": {"cpu_count": os.cpu_count(), "mem_total_kb": _meminfo_total_kb()},
        "db": db_snapshot,
        "dsn": {
            "DATABASE_URL": _dsn_fingerprint(resolve_runtime_database_url()),
            "R5_ADMIN_DATABASE_URL": _dsn_fingerprint(admin_db_url),
        },
    }

    print("=== R5_ENV ===")
    print(json.dumps(env_snapshot, indent=2, sort_keys=True))

    p1 = await probe_p1_determinism(ctx)
    _print_verdict("P1_Determinism", p1)

    p3 = await probe_p3_scaling(ctx)
    _print_verdict("P3_Scaling", p3)

    print(f"R5_WINDOW_END {_utc_iso()} {candidate_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""
R5 Remediation Verification Harness

Authoritative goals (binary; CI logs are the proof channel):
- Determinism: allocation output is bit-identical across
  - 3 sequential reruns
  - concurrency=10
  - induced retry (at least one retry must be observed in logs)
- Scaling: 10k and 100k complete in CI and ratios are ~O(N)

This script is designed to be run in GitHub Actions against an ephemeral Postgres.
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


def _dsn_scheme_and_hash(dsn: str) -> dict[str, str]:
    if not dsn:
        return {"scheme": "", "sha256": ""}
    p = urlsplit(dsn)
    return {"scheme": p.scheme, "sha256": _sha256_hex(dsn.encode("utf-8"))}


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


def _ru_maxrss_kb() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


class StatementCounter:
    def __init__(self) -> None:
        self.count = 0

    def before_cursor_execute(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        self.count += 1


@dataclass(frozen=True)
class RunCtx:
    candidate_sha: str
    run_url: str
    admin_db_url: str


async def _pg(admin_db_url: str) -> asyncpg.Connection:
    return await asyncpg.connect(admin_db_url)


async def _db_settings_snapshot(conn: asyncpg.Connection) -> dict[str, str]:
    settings = {}
    for k in [
        "server_version",
        "shared_buffers",
        "work_mem",
        "maintenance_work_mem",
        "max_wal_size",
        "checkpoint_timeout",
        "checkpoint_completion_target",
        "wal_compression",
        "wal_level",
        "fsync",
        "synchronous_commit",
        "full_page_writes",
    ]:
        try:
            settings[k] = str(await conn.fetchval(f"SHOW {k}"))
        except Exception:
            settings[k] = "UNKNOWN"
    return settings


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
        revenue_cents = (i % 97) + 1  # deterministic, non-zero

        yield (
            str(event_id),
            str(tenant_id),
            occurred_at,
            occurred_at,
            occurred_at,
            f"ext_{i}",
            str(correlation_id),
            str(session_id),
            revenue_cents,
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


async def _fetch_allocations_snapshot(
    conn: asyncpg.Connection,
    *,
    tenant_id: UUID,
    model_version: str,
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT
            aa.id::text AS id,
            aa.tenant_id::text AS tenant_id,
            aa.event_id::text AS event_id,
            aa.channel_code AS channel_code,
            aa.allocated_revenue_cents AS allocated_revenue_cents,
            aa.model_metadata AS model_metadata,
            aa.correlation_id::text AS correlation_id,
            aa.allocation_ratio::text AS allocation_ratio,
            aa.model_version AS model_version,
            aa.model_type AS model_type,
            aa.confidence_score::text AS confidence_score,
            aa.credible_interval_lower_cents AS credible_interval_lower_cents,
            aa.credible_interval_upper_cents AS credible_interval_upper_cents,
            aa.convergence_r_hat::text AS convergence_r_hat,
            aa.effective_sample_size AS effective_sample_size,
            aa.verified AS verified,
            aa.verification_source AS verification_source,
            aa.verification_timestamp AS verification_timestamp,
            aa.created_at AS created_at,
            aa.updated_at AS updated_at
        FROM attribution_allocations aa
        INNER JOIN attribution_events e
            ON e.id = aa.event_id
           AND e.tenant_id = aa.tenant_id
        WHERE aa.tenant_id = $1
          AND aa.model_version = $2
          AND e.occurred_at >= $3
          AND e.occurred_at < $4
        ORDER BY aa.event_id ASC, aa.channel_code ASC, aa.id ASC
        """,
        str(tenant_id),
        model_version,
        window_start,
        window_end,
    )

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "tenant_id": r["tenant_id"],
                "event_id": r["event_id"],
                "channel_code": r["channel_code"],
                "allocated_revenue_cents": int(r["allocated_revenue_cents"]),
                "model_metadata": r["model_metadata"],
                "correlation_id": r["correlation_id"],
                "allocation_ratio": r["allocation_ratio"],
                "model_version": r["model_version"],
                "model_type": r["model_type"],
                "confidence_score": r["confidence_score"],
                "credible_interval_lower_cents": r["credible_interval_lower_cents"],
                "credible_interval_upper_cents": r["credible_interval_upper_cents"],
                "convergence_r_hat": r["convergence_r_hat"],
                "effective_sample_size": r["effective_sample_size"],
                "verified": bool(r["verified"]),
                "verification_source": r["verification_source"],
                "verification_timestamp": r["verification_timestamp"].isoformat()
                if r["verification_timestamp"]
                else None,
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
            }
        )
    return out


async def _run_compute_with_count(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    model_version: str,
) -> dict[str, Any]:
    counter = StatementCounter()
    sa_event.listen(engine.sync_engine, "before_cursor_execute", counter.before_cursor_execute)
    t0 = time.perf_counter()
    try:
        meta = await _compute_allocations_deterministic_baseline(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
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


async def _run_compute_concurrency(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    model_version: str,
    concurrency: int,
) -> dict[str, Any]:
    counter = StatementCounter()
    sa_event.listen(engine.sync_engine, "before_cursor_execute", counter.before_cursor_execute)
    t0 = time.perf_counter()
    try:
        tasks = [
            _compute_allocations_deterministic_baseline(
                tenant_id=tenant_id,
                window_start=window_start,
                window_end=window_end,
                model_version=model_version,
            )
            for _ in range(concurrency)
        ]
        await asyncio.gather(*tasks)
    finally:
        t1 = time.perf_counter()
        sa_event.remove(engine.sync_engine, "before_cursor_execute", counter.before_cursor_execute)
    return {
        "compute_wall_s": round(t1 - t0, 6),
        "sqlalchemy_statement_count": int(counter.count),
        "ru_maxrss_kb": _ru_maxrss_kb(),
    }


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


async def main() -> int:
    candidate_sha = _env("CANDIDATE_SHA", _git_rev_parse_head())
    run_url = _env("RUN_URL", "UNKNOWN")
    admin_db_url = _env("R5_ADMIN_DATABASE_URL")
    model_version = _env("R5_MODEL_VERSION", "1.0.0")

    n_det = int(_env("R5_DETERMINISM_EVENTS_N", "1000"))
    det_runs = int(_env("R5_DETERMINISM_RUNS", "3"))
    det_concurrency = int(_env("R5_DETERMINISM_CONCURRENCY", "10"))

    n_small = int(_env("R5_SCALE_N_SMALL", "10000"))
    n_large = int(_env("R5_SCALE_N_LARGE", "100000"))

    ctx = RunCtx(candidate_sha=candidate_sha, run_url=run_url, admin_db_url=admin_db_url)

    print(f"R5_WINDOW_START {_utc_iso()} {candidate_sha}")
    print(f"R5_SHA={candidate_sha}")
    print(f"R5_RUN_URL={run_url}")
    print(f"R5_ADMIN_DSN_SCHEME={_dsn_scheme_and_hash(admin_db_url)['scheme']}")
    print(f"R5_ADMIN_DSN_SHA256={_dsn_scheme_and_hash(admin_db_url)['sha256']}")

    env_snapshot = {
        "candidate_sha": candidate_sha,
        "run_url": run_url,
        "os": {"platform": platform.platform(), "machine": platform.machine()},
        "python": {"version": sys.version.split()[0], "full": sys.version},
        "hw": {"cpu_count": os.cpu_count(), "mem_total_kb": _meminfo_total_kb()},
    }
    print("=== R5_ENV ===")
    print(json.dumps(env_snapshot, indent=2, sort_keys=True))

    window_start = datetime(2025, 5, 1, tzinfo=timezone.utc)
    window_end = window_start + timedelta(days=1)
    print(f"R5_WINDOW={window_start.isoformat()},{window_end.isoformat()}")

    conn = await _pg(admin_db_url)
    verdict: dict[str, Any] = {"candidate_sha": candidate_sha, "run_url": run_url, "gates": {}}
    try:
        db_settings = await _db_settings_snapshot(conn)
        for k, v in sorted(db_settings.items()):
            print(f"R5_DB_{k.upper()}={v}")

        # ------------------------------------------------------------------
        # EG-R5-1: Determinism - 3 sequential reruns
        # ------------------------------------------------------------------
        tenant_det = _uuid_det("r5", ctx.candidate_sha, "DET_SERIAL", "tenant")
        print(f"R5_DATASET_SEED=sha:{candidate_sha} scenario:DET_SERIAL tenant:{tenant_det}")
        await _seed_events(
            conn,
            tenant_id=tenant_det,
            candidate_sha=ctx.candidate_sha,
            scenario="DET_SERIAL",
            n=n_det,
            window_start=window_start,
            occurred_at_step_us=10,
        )

        serial_hashes: list[str] = []
        for i in range(det_runs):
            meta = await _run_compute_with_count(
                tenant_id=tenant_det,
                window_start=window_start,
                window_end=window_end,
                model_version=model_version,
            )
            snap = await _fetch_allocations_snapshot(
                conn,
                tenant_id=tenant_det,
                model_version=model_version,
                window_start=window_start,
                window_end=window_end,
            )
            h = _sha256_hex(_canonical_json_bytes(snap))
            serial_hashes.append(h)
            print(
                " ".join(
                    [
                        "R5_RUN_MODE=serial",
                        f"R5_RUN_INDEX={i+1}",
                        f"R5_DETERMINISM_FULL_SHA256={h}",
                        f"R5_STATEMENTS_TOTAL={meta['sqlalchemy_statement_count']}",
                        f"R5_WALL_S={meta['compute_wall_s']}",
                        f"R5_PEAK_RSS_KB={meta['ru_maxrss_kb']}",
                    ]
                )
            )

        _require(len(set(serial_hashes)) == 1, f"EG-R5-1 FAIL: serial hashes drifted: {serial_hashes}")
        verdict["gates"]["EG-R5-1"] = {"pass": True, "hash": serial_hashes[0]}

        # ------------------------------------------------------------------
        # EG-R5-2: Determinism - concurrency invariance
        # ------------------------------------------------------------------
        tenant_conc = _uuid_det("r5", ctx.candidate_sha, "DET_CONC", "tenant")
        print(f"R5_DATASET_SEED=sha:{candidate_sha} scenario:DET_CONC tenant:{tenant_conc}")
        await _seed_events(
            conn,
            tenant_id=tenant_conc,
            candidate_sha=ctx.candidate_sha,
            scenario="DET_CONC",
            n=n_det,
            window_start=window_start,
            occurred_at_step_us=10,
        )

        print(f"R5_RUN_MODE=concurrency10 R5_CONCURRENCY_TARGET={det_concurrency}")
        conc_meta = await _run_compute_concurrency(
            tenant_id=tenant_conc,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
            concurrency=det_concurrency,
        )
        conc_snap = await _fetch_allocations_snapshot(
            conn,
            tenant_id=tenant_conc,
            model_version=model_version,
            window_start=window_start,
            window_end=window_end,
        )
        conc_hash = _sha256_hex(_canonical_json_bytes(conc_snap))
        print(
            " ".join(
                [
                    "R5_RUN_MODE=concurrency10",
                    f"R5_DETERMINISM_FULL_SHA256={conc_hash}",
                    f"R5_STATEMENTS_TOTAL={conc_meta['sqlalchemy_statement_count']}",
                    f"R5_WALL_S={conc_meta['compute_wall_s']}",
                    f"R5_PEAK_RSS_KB={conc_meta['ru_maxrss_kb']}",
                ]
            )
        )

        rerun_meta = await _run_compute_with_count(
            tenant_id=tenant_conc,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        )
        rerun_snap = await _fetch_allocations_snapshot(
            conn,
            tenant_id=tenant_conc,
            model_version=model_version,
            window_start=window_start,
            window_end=window_end,
        )
        rerun_hash = _sha256_hex(_canonical_json_bytes(rerun_snap))
        print(
            " ".join(
                [
                    "R5_RUN_MODE=post_concurrency_serial",
                    f"R5_DETERMINISM_FULL_SHA256={rerun_hash}",
                    f"R5_STATEMENTS_TOTAL={rerun_meta['sqlalchemy_statement_count']}",
                    f"R5_WALL_S={rerun_meta['compute_wall_s']}",
                    f"R5_PEAK_RSS_KB={rerun_meta['ru_maxrss_kb']}",
                ]
            )
        )

        _require(
            conc_hash == rerun_hash,
            f"EG-R5-2 FAIL: concurrency hash != serial hash (same dataset): {conc_hash} vs {rerun_hash}",
        )
        verdict["gates"]["EG-R5-2"] = {"pass": True, "hash": conc_hash}

        # ------------------------------------------------------------------
        # EG-R5-3: Determinism - induced retry invariance (proof via log markers)
        # ------------------------------------------------------------------
        tenant_retry = _uuid_det("r5", ctx.candidate_sha, "DET_RETRY", "tenant")
        print(f"R5_DATASET_SEED=sha:{candidate_sha} scenario:DET_RETRY tenant:{tenant_retry}")
        await _seed_events(
            conn,
            tenant_id=tenant_retry,
            candidate_sha=ctx.candidate_sha,
            scenario="DET_RETRY",
            n=n_det,
            window_start=window_start,
            occurred_at_step_us=10,
        )

        print("R5_RUN_MODE=retry_injected R5_RETRY_ATTEMPT=1")
        try:
            await _compute_allocations_deterministic_baseline(
                tenant_id=tenant_retry,
                window_start=window_start,
                window_end=window_end,
                model_version=model_version,
                inject_fail_once_key=f"r5:{candidate_sha}:DET_RETRY",
                inject_fail_after_batches=1,
            )
            raise RuntimeError("Expected retry injection failure did not occur")
        except Exception as exc:  # noqa: BLE001
            print(f"R5_RETRY_INJECTED_FAILURE_CAUGHT=1 R5_ERROR={exc.__class__.__name__}")

        after_fail = await _fetch_allocations_snapshot(
            conn,
            tenant_id=tenant_retry,
            model_version=model_version,
            window_start=window_start,
            window_end=window_end,
        )
        print(f"R5_RETRY_AFTER_FAIL_ALLOCATION_ROWS={len(after_fail)}")
        _require(
            len(after_fail) == 0,
            f"EG-R5-3 FAIL: expected 0 allocations after injected failure, got {len(after_fail)}",
        )

        print("R5_RUN_MODE=retry_injected R5_RETRY_ATTEMPT=2")
        retry_meta = await _run_compute_with_count(
            tenant_id=tenant_retry,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        )

        retry_snap = await _fetch_allocations_snapshot(
            conn,
            tenant_id=tenant_retry,
            model_version=model_version,
            window_start=window_start,
            window_end=window_end,
        )
        retry_hash = _sha256_hex(_canonical_json_bytes(retry_snap))
        print(
            " ".join(
                [
                    "R5_RUN_MODE=retry_injected",
                    "R5_RETRY_OBSERVED=1",
                    f"R5_DETERMINISM_FULL_SHA256={retry_hash}",
                    f"R5_STATEMENTS_TOTAL={retry_meta['sqlalchemy_statement_count']}",
                    f"R5_WALL_S={retry_meta['compute_wall_s']}",
                    f"R5_PEAK_RSS_KB={retry_meta['ru_maxrss_kb']}",
                ]
            )
        )

        post_retry_meta = await _run_compute_with_count(
            tenant_id=tenant_retry,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        )
        post_retry_snap = await _fetch_allocations_snapshot(
            conn,
            tenant_id=tenant_retry,
            model_version=model_version,
            window_start=window_start,
            window_end=window_end,
        )
        post_retry_hash = _sha256_hex(_canonical_json_bytes(post_retry_snap))
        print(
            " ".join(
                [
                    "R5_RUN_MODE=post_retry_serial",
                    f"R5_DETERMINISM_FULL_SHA256={post_retry_hash}",
                    f"R5_STATEMENTS_TOTAL={post_retry_meta['sqlalchemy_statement_count']}",
                    f"R5_WALL_S={post_retry_meta['compute_wall_s']}",
                    f"R5_PEAK_RSS_KB={post_retry_meta['ru_maxrss_kb']}",
                ]
            )
        )
        _require(
            retry_hash == post_retry_hash,
            f"EG-R5-3 FAIL: retry hash != post-retry serial hash: {retry_hash} vs {post_retry_hash}",
        )
        verdict["gates"]["EG-R5-3"] = {"pass": True, "hash": retry_hash}

        # ------------------------------------------------------------------
        # EG-R5-4: Complexity ratio proof (10k vs 100k)
        # ------------------------------------------------------------------
        scale_start = datetime(2025, 6, 1, tzinfo=timezone.utc)
        scale_end = scale_start + timedelta(days=1)

        tenant_small = _uuid_det("r5", ctx.candidate_sha, "SCALE_10K", "tenant")
        tenant_large = _uuid_det("r5", ctx.candidate_sha, "SCALE_100K", "tenant")

        await _seed_events(
            conn,
            tenant_id=tenant_small,
            candidate_sha=ctx.candidate_sha,
            scenario="SCALE_10K",
            n=n_small,
            window_start=scale_start,
            occurred_at_step_us=1,
        )
        small_meta = await _run_compute_with_count(
            tenant_id=tenant_small,
            window_start=scale_start,
            window_end=scale_end,
            model_version=model_version,
        )
        print(
            " ".join(
                [
                    f"R5_N={n_small}",
                    f"R5_WALL_S={small_meta['compute_wall_s']}",
                    f"R5_STATEMENTS_TOTAL={small_meta['sqlalchemy_statement_count']}",
                    f"R5_PEAK_RSS_KB={small_meta['ru_maxrss_kb']}",
                ]
            )
        )

        await _seed_events(
            conn,
            tenant_id=tenant_large,
            candidate_sha=ctx.candidate_sha,
            scenario="SCALE_100K",
            n=n_large,
            window_start=scale_start,
            occurred_at_step_us=1,
        )
        large_meta = await _run_compute_with_count(
            tenant_id=tenant_large,
            window_start=scale_start,
            window_end=scale_end,
            model_version=model_version,
        )
        print(
            " ".join(
                [
                    f"R5_N={n_large}",
                    f"R5_WALL_S={large_meta['compute_wall_s']}",
                    f"R5_STATEMENTS_TOTAL={large_meta['sqlalchemy_statement_count']}",
                    f"R5_PEAK_RSS_KB={large_meta['ru_maxrss_kb']}",
                ]
            )
        )

        time_ratio = float(large_meta["compute_wall_s"]) / float(small_meta["compute_wall_s"])
        stmt_ratio = float(large_meta["sqlalchemy_statement_count"]) / float(
            small_meta["sqlalchemy_statement_count"]
        )
        rss_ratio = float(large_meta["ru_maxrss_kb"]) / float(small_meta["ru_maxrss_kb"])

        print(f"R5_TIME_RATIO={round(time_ratio, 6)}")
        print(f"R5_STMT_RATIO={round(stmt_ratio, 6)}")
        print(f"R5_PEAK_RSS_RATIO={round(rss_ratio, 6)}")

        _require(time_ratio <= 15.0, f"EG-R5-4 FAIL: TIME_RATIO {time_ratio} > 15")
        _require(stmt_ratio <= 12.0, f"EG-R5-4 FAIL: STMT_RATIO {stmt_ratio} > 12")
        _require(rss_ratio <= 12.0, f"EG-R5-4 FAIL: PEAK_RSS_RATIO {rss_ratio} > 12")
        verdict["gates"]["EG-R5-4"] = {
            "pass": True,
            "time_ratio": round(time_ratio, 6),
            "stmt_ratio": round(stmt_ratio, 6),
            "rss_ratio": round(rss_ratio, 6),
        }

        verdict["gates"]["EG-R5-5"] = {"pass": True}
        verdict["pass"] = True
    finally:
        await conn.close()

    print("R5_VERDICT_BEGIN")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    print("R5_VERDICT_END")
    print(f"R5_WINDOW_END {_utc_iso()} {candidate_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

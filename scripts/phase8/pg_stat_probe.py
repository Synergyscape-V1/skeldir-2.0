"""Hosted intra-postgres split probe for the Phase 8 full-physics leg.

Ordered-plan step-3/4 measurement (observation only; no threshold reads it):
samples `pg_stat_statements` (loaded with track=all by the composed postgres)
every interval while the R3 leg runs. Each sample carries the top-N
statements by cumulative `total_exec_time` plus engine-wide totals; the
per-leg split is derived post-hoc by differencing the samples that bound
each R3 verdict window (the same window-bounded aggregation method the
runner CPU probe uses).

This is the instrument that splits the ~2 postgres cores burned during a
failing leg into named statements and function-internal statements, so the
next repair targets a measured cause instead of a hypothesis. The DSN comes
from --dsn or the pack-provided admin environment (never logged; only
current_user is recorded).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

_TOPN_DEFAULT = 120
_QUERY_TEXT_MAX = 120


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dsn_from_env() -> str:
    for name in ("R3_ADMIN_DATABASE_URL", "MIGRATION_DATABASE_URL"):
        value = os.environ.get(name, "")
        if value:
            return value
    return ""


def _collect_metadata(conn) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "pgss_available": False,
        "pgss_error": None,
        "extversion": None,
        "preloaded_libraries": None,
        "track_setting": None,
        "server_version": None,
        "current_user": None,
    }
    try:
        meta["current_user"] = conn.execute(text("SELECT current_user")).scalar()
        meta["server_version"] = conn.execute(text("SHOW server_version")).scalar()
        meta["preloaded_libraries"] = conn.execute(
            text("SHOW shared_preload_libraries")
        ).scalar()
        meta["extversion"] = conn.execute(
            text(
                "SELECT extversion FROM pg_extension WHERE extname = 'pg_stat_statements'"
            )
        ).scalar()
        meta["track_setting"] = conn.execute(
            text("SHOW pg_stat_statements.track")
        ).scalar()
        conn.execute(text("SELECT count(*) FROM pg_stat_statements")).scalar()
        meta["pgss_available"] = meta["extversion"] is not None
    except Exception as exc:  # noqa: BLE001 - recorded, drives fail-closed status
        meta["pgss_error"] = f"{type(exc).__name__}: {exc}"
    return meta


def _sample_top(conn, top_n: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    totals_row = conn.execute(
        text(
            """
            SELECT count(*) AS statements,
                   COALESCE(sum(calls), 0) AS calls,
                   COALESCE(sum(total_exec_time), 0) AS total_exec_ms
            FROM pg_stat_statements
            WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
            """
        )
    ).one()
    rows = conn.execute(
        text(
            """
            SELECT queryid::text AS qid,
                   calls,
                   total_exec_time,
                   rows,
                   toplevel,
                   left(regexp_replace(query, E'\\\\s+', ' ', 'g'), :qmax) AS q
            FROM pg_stat_statements
            WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
            ORDER BY total_exec_time DESC
            LIMIT :limit
            """
        ),
        {"limit": top_n, "qmax": _QUERY_TEXT_MAX},
    ).all()
    totals = {
        "statements": int(totals_row.statements or 0),
        "calls": int(totals_row.calls or 0),
        "total_exec_ms": round(float(totals_row.total_exec_ms or 0.0), 3),
    }
    top = [
        {
            "qid": row.qid,
            "calls": int(row.calls or 0),
            "ms": round(float(row.total_exec_time or 0.0), 3),
            "rows": int(row.rows or 0),
            "toplevel": bool(row.toplevel),
            "q": row.q,
        }
        for row in rows
    ]
    return totals, top


def _delta_split(
    first: list[dict[str, Any]] | None,
    last: list[dict[str, Any]] | None,
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    if not first or not last:
        return []
    first_by_qid = {row["qid"]: row for row in first}
    out: list[dict[str, Any]] = []
    for row in last:
        prev = first_by_qid.get(row["qid"])
        calls = row["calls"] - (prev["calls"] if prev else 0)
        ms = row["ms"] - (prev["ms"] if prev else 0.0)
        if calls <= 0 and ms <= 0:
            continue
        out.append(
            {
                "qid": row["qid"],
                "q": row["q"],
                "calls": calls,
                "total_exec_ms": round(ms, 3),
                "mean_exec_ms": round(ms / calls, 4) if calls > 0 else None,
                "rows": row["rows"] - (prev["rows"] if prev else 0),
                "toplevel": row["toplevel"],
            }
        )
    out.sort(key=lambda item: item["total_exec_ms"], reverse=True)
    return out[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default="")
    parser.add_argument("--duration-s", type=float, required=True)
    parser.add_argument("--interval-s", type=float, default=5.0)
    parser.add_argument("--top-n", type=int, default=_TOPN_DEFAULT)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, default=None)
    args = parser.parse_args()

    if args.duration_s <= 0 or args.interval_s <= 0 or args.top_n <= 0:
        print("duration-s, interval-s and top-n must be > 0", file=sys.stderr)
        return 2
    dsn = args.dsn or _dsn_from_env()
    if not dsn:
        print(
            "no DSN: pass --dsn or set R3_ADMIN_DATABASE_URL/MIGRATION_DATABASE_URL",
            file=sys.stderr,
        )
        return 2

    jsonl_path = args.jsonl or args.artifact.with_suffix(".jsonl")
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = _now_utc()
    start_monotonic = time.monotonic()
    deadline = start_monotonic + args.duration_s

    engine = create_engine(dsn, pool_pre_ping=True)
    metadata: dict[str, Any] = {}
    sample_count = 0
    error_count = 0
    last_error: str | None = None
    first_totals: dict[str, Any] | None = None
    last_totals: dict[str, Any] | None = None
    first_top: list[dict[str, Any]] | None = None
    last_top: list[dict[str, Any]] | None = None

    jsonl_handle = jsonl_path.open("w", encoding="utf-8")
    try:
        with engine.connect() as conn:
            metadata = _collect_metadata(conn)
            if not metadata.get("pgss_available"):
                last_error = (
                    metadata.get("pgss_error") or "pg_stat_statements unavailable"
                )
            while time.monotonic() < deadline:
                time.sleep(args.interval_s)
                try:
                    totals, top = _sample_top(conn, args.top_n)
                except (
                    Exception
                ) as exc:  # noqa: BLE001 - transient sample errors recorded
                    error_count += 1
                    last_error = f"{type(exc).__name__}: {exc}"
                    conn.rollback()
                    continue
                if first_totals is None:
                    first_totals = totals
                    first_top = top
                last_totals = totals
                last_top = top
                sample = {
                    "ts": _now_utc(),
                    "idx": sample_count,
                    "totals": totals,
                    "top": top,
                }
                jsonl_handle.write(json.dumps(sample) + "\n")
                jsonl_handle.flush()
                sample_count += 1
    finally:
        jsonl_handle.close()
        engine.dispose()

    finished_at = _now_utc()
    runtime_s = round(time.monotonic() - start_monotonic, 3)
    if sample_count >= 2 and metadata.get("pgss_available"):
        status = "ok"
        error: str | None = None
    else:
        status = "failed"
        error = last_error or "insufficient samples"
    summary = {
        "status": status,
        "error": error,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": args.duration_s,
        "runtime_s": runtime_s,
        "interval_s": args.interval_s,
        "top_n": args.top_n,
        "sample_count": sample_count,
        "sample_error_count": error_count,
        "last_sample_error": last_error if error_count > 0 else None,
        **metadata,
        "totals_first": first_totals,
        "totals_last": last_totals,
        "top_statements_by_delta": _delta_split(first_top, last_top),
    }

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": status,
                "sample_count": sample_count,
                "pgss_available": metadata.get("pgss_available"),
                "extversion": metadata.get("extversion"),
                "track_setting": metadata.get("track_setting"),
            },
            indent=2,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_snapshot(conn) -> dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
              q.name AS queue_name,
              COALESCE(SUM(CASE WHEN m.visible THEN 1 ELSE 0 END), 0)::INTEGER AS visible_messages,
              COALESCE(SUM(CASE WHEN NOT m.visible THEN 1 ELSE 0 END), 0)::INTEGER AS invisible_messages,
              COALESCE(COUNT(m.id), 0)::INTEGER AS total_messages
            FROM kombu_queue q
            LEFT JOIN kombu_message m ON m.queue_id = q.id
            GROUP BY q.name
            ORDER BY q.name
            """
        )
        rows = cur.fetchall()

    by_queue: dict[str, dict[str, int]] = {}
    visible_total = 0
    invisible_total = 0
    total = 0
    for row in rows:
        queue_name = str(row["queue_name"])
        visible = int(row["visible_messages"])
        invisible = int(row["invisible_messages"])
        queue_total = int(row["total_messages"])
        by_queue[queue_name] = {
            "visible_messages": visible,
            "invisible_messages": invisible,
            "total_messages": queue_total,
        }
        visible_total += visible
        invisible_total += invisible
        total += queue_total
    return {
        "visible_messages": visible_total,
        "invisible_messages": invisible_total,
        "total_messages": total,
        "queues": by_queue,
    }


def _summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "sample_count": 0,
            "max_total_messages": 0,
            "final_total_messages": 0,
            "drain_rate_messages_per_s": 0.0,
            "peak_observed_at": None,
            "duration_s": 0.0,
        }

    peak = max(samples, key=lambda item: int(item["total_messages"]))
    final = samples[-1]
    start = samples[0]
    start_ts = float(start["monotonic_s"])
    peak_ts = float(peak["monotonic_s"])
    final_ts = float(final["monotonic_s"])
    peak_total = int(peak["total_messages"])
    final_total = int(final["total_messages"])
    drain_window_s = max(0.001, final_ts - peak_ts)
    drain_rate = (peak_total - final_total) / drain_window_s

    per_queue_peak: dict[str, int] = {}
    for sample in samples:
        for queue_name, queue_data in sample.get("queues", {}).items():
            queue_total = int(queue_data.get("total_messages", 0))
            current = per_queue_peak.get(queue_name, 0)
            if queue_total > current:
                per_queue_peak[queue_name] = queue_total

    final_queue_totals = {
        queue_name: int(queue_data.get("total_messages", 0))
        for queue_name, queue_data in final.get("queues", {}).items()
    }

    return {
        "sample_count": len(samples),
        "max_total_messages": peak_total,
        "final_total_messages": final_total,
        "drain_rate_messages_per_s": round(drain_rate, 6),
        "peak_observed_at": peak.get("observed_at"),
        "duration_s": round(final_ts - start_ts, 6),
        "per_queue_peak_total_messages": per_queue_peak,
        "per_queue_final_total_messages": final_queue_totals,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--duration-s", type=float, required=True)
    parser.add_argument("--interval-s", type=float, default=0.5)
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()

    duration_s = max(1.0, float(args.duration_s))
    interval_s = max(0.1, float(args.interval_s))
    artifact_path = Path(args.artifact)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    t0 = time.monotonic()
    deadline = t0 + duration_s
    samples: list[dict[str, Any]] = []

    with psycopg2.connect(args.db_url) as conn:
        conn.autocommit = True
        while True:
            now = time.monotonic()
            snapshot = _read_snapshot(conn)
            samples.append(
                {
                    "observed_at": _utc_now(),
                    "monotonic_s": round(now, 6),
                    **snapshot,
                }
            )
            if now >= deadline:
                break
            time.sleep(interval_s)

    finished_at = _utc_now()
    summary = _summarize(samples)
    payload = {
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_target_s": duration_s,
        "interval_s": interval_s,
        "summary": summary,
        "samples": samples,
    }
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

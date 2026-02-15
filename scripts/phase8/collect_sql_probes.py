#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text


def _read_runtime_probe(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Runtime probe not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Runtime probe must be a JSON object")
    return payload


def _csv_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = sorted(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in keys})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--runtime-probe", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--llm-load-probe", required=False)
    args = parser.parse_args()

    runtime_probe = _read_runtime_probe(Path(args.runtime_probe))
    tenant_id = str(runtime_probe["tenant_id"])
    user_id = str(runtime_probe["primary_user_id"])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    llm_load_probe: dict[str, Any] | None = None
    if args.llm_load_probe:
        load_path = Path(args.llm_load_probe)
        if load_path.exists():
            llm_load_probe = json.loads(load_path.read_text(encoding="utf-8"))

    engine = create_engine(args.db_url)
    with engine.begin() as conn:
        current_user = str(conn.execute(text("SELECT current_user")).scalar_one())
        rolsuper = bool(
            conn.execute(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            ).scalar_one()
        )

        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": tenant_id},
        )
        conn.execute(
            text("SELECT set_config('app.current_user_id', :user_id, false)"),
            {"user_id": user_id},
        )

        topology_counts = dict(
            conn.execute(
                text(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM attribution_events WHERE tenant_id = :tenant_id) AS attribution_events,
                      (SELECT COUNT(*) FROM dead_events WHERE tenant_id = :tenant_id) AS dead_events,
                      (SELECT COUNT(*) FROM attribution_recompute_jobs WHERE tenant_id = :tenant_id) AS attribution_recompute_jobs,
                      (SELECT COUNT(*) FROM revenue_ledger WHERE tenant_id = :tenant_id) AS revenue_ledger,
                      (SELECT COUNT(*) FROM reconciliation_runs WHERE tenant_id = :tenant_id) AS reconciliation_runs,
                      (SELECT COUNT(*) FROM llm_api_calls WHERE tenant_id = :tenant_id) AS llm_api_calls,
                      (SELECT COUNT(*) FROM llm_call_audit WHERE tenant_id = :tenant_id) AS llm_call_audit
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().one()
        )

        llm_outcomes = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT
                        status,
                        provider_attempted,
                        was_cached,
                        COUNT(*)::INTEGER AS calls
                    FROM llm_api_calls
                    WHERE tenant_id = :tenant_id
                    GROUP BY status, provider_attempted, was_cached
                    ORDER BY status, provider_attempted, was_cached
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings()
        ]

        cost_correctness = dict(
            conn.execute(
                text(
                    """
                    SELECT
                      (SELECT COALESCE(SUM(cost_cents), 0)::BIGINT
                       FROM llm_api_calls
                       WHERE tenant_id = :tenant_id) AS api_cost_cents,
                      (SELECT COALESCE(SUM(total_cost_cents), 0)::BIGINT
                       FROM llm_monthly_costs
                       WHERE tenant_id = :tenant_id) AS monthly_rollup_cost_cents
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().one()
        )

        pg_snapshot = dict(
            conn.execute(
                text(
                    """
                    SELECT
                      COUNT(*)::INTEGER AS active_connections,
                      COUNT(*) FILTER (WHERE wait_event IS NOT NULL)::INTEGER AS waiting_connections
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    """
                )
            ).mappings().one()
        )

        perf_composed_llm_calls = 0
        if llm_load_probe:
            params = {
                "tenant_id": llm_load_probe["tenant_id"],
                "started_at": llm_load_probe["started_at"],
                "finished_at": llm_load_probe["finished_at"],
            }
            perf_api_calls = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*)::INTEGER
                        FROM llm_api_calls
                        WHERE tenant_id = :tenant_id
                          AND request_id LIKE 'phase8-perf-llm-%'
                          AND created_at >= :started_at
                          AND created_at <= :finished_at
                        """
                    ),
                    params,
                ).scalar_one()
            )
            perf_audit_calls = int(
                conn.execute(
                    text(
                        """
                        SELECT COUNT(*)::INTEGER
                        FROM llm_call_audit
                        WHERE tenant_id = :tenant_id
                          AND request_id LIKE 'phase8-perf-llm-%'
                          AND created_at >= :started_at
                          AND created_at <= :finished_at
                        """
                    ),
                    params,
                ).scalar_one()
            )
            perf_composed_llm_calls = max(perf_api_calls, perf_audit_calls)

    summary = {
        "runtime_identity": {
            "current_user": current_user,
            "rolsuper": rolsuper,
        },
        "topology_counts": topology_counts,
        "llm_outcomes": llm_outcomes,
        "cost_correctness": cost_correctness,
        "pg_snapshot": pg_snapshot,
        "perf_composed_llm_calls": perf_composed_llm_calls,
    }
    (out_dir / "phase8_sql_probe_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    _csv_write(out_dir / "phase8_llm_outcomes.csv", llm_outcomes)
    _csv_write(out_dir / "phase8_topology_counts.csv", [topology_counts])
    _csv_write(out_dir / "phase8_pg_snapshot.csv", [pg_snapshot])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

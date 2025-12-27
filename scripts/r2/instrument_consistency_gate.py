#!/usr/bin/env python3
"""
R2 Instrument Consistency Gate

Compares the AUTHORITATIVE DB-log window verdict with the mandatory ORM
cross-check verdict for the same candidate SHA and window ID.

Hard FAIL conditions:
  - Either instrument total == 0
  - Either instrument forbidden match count != 0
  - Scenario IDs/order mismatch
  - Any scenario has non-marker count < 1 in either instrument
  - Large unexplained discrepancy between totals
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _db_total(v: dict) -> int:
    return int(v.get("total_db_statements_captured_in_window", 0))


def _db_forbidden(v: dict) -> int:
    return int(v.get("match_count_destructive_on_immutable", 0))


def _db_per_scenario(v: dict) -> dict[int, int]:
    out: dict[int, int] = {}
    for item in v.get("scenario_windows", []) or []:
        try:
            out[int(item["number"])] = int(item["non_marker_count"])
        except Exception:
            continue
    return out


def _orm_total(v: dict) -> int:
    return int(v.get("total_orm_statements_captured_in_window", 0))


def _orm_forbidden(v: dict) -> int:
    return int(v.get("orm_forbidden_match_count", 0))


def _orm_per_scenario(v: dict) -> dict[int, int]:
    out: dict[int, int] = {}
    for k, val in (v.get("per_scenario_non_marker_counts", {}) or {}).items():
        try:
            out[int(k)] = int(val)
        except Exception:
            continue
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-window-json", required=True)
    parser.add_argument("--orm-window-json", required=True)
    parser.add_argument("--num-scenarios", type=int, default=6)
    args = parser.parse_args()

    db = _load(args.db_window_json)
    orm = _load(args.orm_window_json)

    failures: list[str] = []

    db_total = _db_total(db)
    orm_total = _orm_total(orm)
    db_forbidden = _db_forbidden(db)
    orm_forbidden = _orm_forbidden(orm)

    if db_total <= 0:
        failures.append("DB_TOTAL_IN_WINDOW=0 (dead DB instrument)")
    if orm_total <= 0:
        failures.append("ORM_TOTAL_IN_WINDOW=0 (dead ORM instrument)")
    if db_forbidden != 0:
        failures.append(f"DB_FORBIDDEN_MATCH_COUNT={db_forbidden}")
    if orm_forbidden != 0:
        failures.append(f"ORM_FORBIDDEN_MATCH_COUNT={orm_forbidden}")

    # Scenario alignment + per-scenario minimum activity.
    db_s = _db_per_scenario(db)
    orm_s = _orm_per_scenario(orm)

    expected = list(range(1, args.num_scenarios + 1))
    if sorted(db_s.keys()) != expected:
        failures.append(f"DB_SCENARIO_IDS_MISMATCH={sorted(db_s.keys())}")
    if sorted(orm_s.keys()) != expected:
        failures.append(f"ORM_SCENARIO_IDS_MISMATCH={sorted(orm_s.keys())}")

    for i in expected:
        if db_s.get(i, 0) < 1:
            failures.append(f"S{i}_NON_MARKER_DB_STATEMENTS_COUNT<1")
        if orm_s.get(i, 0) < 1:
            failures.append(f"S{i}_NON_MARKER_ORM_STATEMENTS_COUNT<1")

    # Discrepancy guard: totals should be broadly comparable.
    if db_total > 0 and orm_total > 0:
        hi = max(db_total, orm_total)
        lo = min(db_total, orm_total)
        ratio = lo / hi if hi else 0.0
        if ratio < 0.5 and (hi - lo) > 10:
            failures.append(f"TOTAL_DISCREPANCY_TOO_LARGE (db={db_total}, orm={orm_total}, ratio={ratio:.2f})")

    print("R2_INSTRUMENT_CONSISTENCY_VERDICT")
    print(f"DB_TOTAL_IN_WINDOW={db_total}")
    print(f"ORM_TOTAL_IN_WINDOW={orm_total}")
    print(f"DB_FORBIDDEN_MATCH_COUNT={db_forbidden}")
    print(f"ORM_FORBIDDEN_MATCH_COUNT={orm_forbidden}")
    for i in range(1, args.num_scenarios + 1):
        print(f"S{i}_DB_NON_MARKER_COUNT={db_s.get(i, 0)}")
        print(f"S{i}_ORM_NON_MARKER_COUNT={orm_s.get(i, 0)}")
    if failures:
        print("FAILURES=" + "; ".join(failures))
    print("END_VERDICT")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())


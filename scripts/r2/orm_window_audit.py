#!/usr/bin/env python3
"""
R2 ORM Runtime Innocence (MANDATORY secondary cross-check)

Consumes the ORM window JSON verdict produced by scripts/r2/runtime_scenario_suite.py
and enforces:
  - total ORM statements in window > 0
  - per-scenario non-marker ORM statement counts >= 1
  - forbidden match count == 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orm-window-json", required=True)
    parser.add_argument("--num-scenarios", type=int, default=6)
    args = parser.parse_args()

    verdict = _load(args.orm_window_json)

    total = int(verdict.get("total_orm_statements_captured_in_window", 0))
    forbidden = int(verdict.get("orm_forbidden_match_count", 0))
    per_scenario_raw = verdict.get("per_scenario_non_marker_counts", {}) or {}

    failures: list[str] = []
    if total <= 0:
        failures.append("TOTAL_ORM_STATEMENTS_CAPTURED_IN_WINDOW=0 (dead ORM instrument)")
    if forbidden != 0:
        failures.append(f"ORM_FORBIDDEN_MATCH_COUNT={forbidden}")

    per_scenario: dict[int, int] = {}
    for k, v in per_scenario_raw.items():
        try:
            per_scenario[int(k)] = int(v)
        except Exception:
            continue

    expected = list(range(1, args.num_scenarios + 1))
    if sorted(per_scenario.keys()) != expected:
        failures.append(f"SCENARIO_IDS_MISMATCH={sorted(per_scenario.keys())}")

    for i in expected:
        if per_scenario.get(i, 0) < 1:
            failures.append(f"S{i}_NON_MARKER_ORM_STATEMENTS_COUNT<1")

    # Bubble up any failures the suite already recorded.
    suite_failures = verdict.get("failures") or []
    for item in suite_failures:
        failures.append(f"SUITE_REPORTED:{item}")

    print("R2_ORM_RUNTIME_INNOCENCE_VERDICT")
    print("IMMUTABLE_TABLE_SET=attribution_events,revenue_ledger")
    print("DESTRUCTIVE_VERBS=ALTER,DELETE,TRUNCATE,UPDATE")
    print(f"TOTAL_ORM_STATEMENTS_CAPTURED_IN_WINDOW={total}")
    for i in expected:
        print(f"S{i}_NON_MARKER_ORM_STATEMENTS_COUNT={per_scenario.get(i, 0)}")
    print(f"ORM_FORBIDDEN_MATCH_COUNT={forbidden}")
    if failures:
        print("FAILURES=" + "; ".join(failures))
    print("END_VERDICT")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())


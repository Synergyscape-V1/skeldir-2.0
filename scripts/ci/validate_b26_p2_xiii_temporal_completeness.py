#!/usr/bin/env python3
"""B2.6-P2 Corrective XIII temporal completeness validator (BLOCKER E).

Laws:
- every semantic dependency declared by the closed contract carries
  exactly one temporal disposition (SEM minus TEMP = EMPTY);
- set-level event kinds (INSERT/DELETE/COUNT) are declared where
  semantic;
- every mutable disposition has an executed behavioral treatment
  (live --dsn runs real mutations after a lawful conducted lineage;
  static mode verifies the battery covers every disposition).

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT / "contracts-internal" / "governance"
    / "b26_p2_xiii_semantic_contract.v1.json"
)
BATTERY = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xii_temporal_behavioral.py"


def _contract_sets() -> tuple[set[str], set[str], dict]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    cols: set[str] = set()
    for rel, collist in (contract.get("allowed_source_columns", {}) or {}).items():
        for col in collist:
            cols.add(f"{rel}.{col}".lower())
    treated = {str(k).lower() for k in (contract.get("temporal_dispositions", {}) or {})}
    return cols, treated, contract


def _static_checks(violations: list[str], checks: dict) -> None:
    cols, treated, contract = _contract_sets()
    uncovered = {c for c in cols if c not in treated}
    checks["column_dependency_count"] = len(cols)
    checks["temporal_treatment_count"] = len(treated)
    if uncovered:
        violations.append(
            "xiii_temporal_missing_disposition:" + ",".join(sorted(uncovered))
        )
    # Set-level events must be declared.
    for event in (
        "b23_match_verdicts.insert_qualifying_row",
        "b23_match_verdicts.delete_qualifying_row",
        "b23_match_verdicts.count_qualifying_set",
    ):
        if event not in treated:
            violations.append(f"xiii_temporal_missing_set_event:{event}")
    # Battery must cover every disposition kind.
    try:
        battery_src = BATTERY.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xiii_temporal_battery_unreadable:{exc}")
        return
    for token in (
        "presence-flip",
        "conducted_set_insert_refused",
        "conducted_verdict_immutable",
        "immutable",
        "policy_semantic_mutation_refused",
        "stale",
        "quarantine",
    ):
        if token not in battery_src:
            violations.append(f"xiii_temporal_battery_gap:{token}")
    # Contract dispositions must use only governed vocabulary.
    allowed = {
        "IMMUTABLE", "UPDATE_REFUSED", "INSERT_DELETE_REFUSED",
        "VERSION_BOUND", "SUPERSEDED_AND_REEVALUATED",
    }
    for key, disp in (contract.get("temporal_dispositions", {}) or {}).items():
        if str(disp).upper() not in allowed:
            violations.append(f"xiii_temporal_bad_disposition:{key}={disp}")
    checks["static_bijection_done"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate XIII temporal completeness.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        # Live behavioral battery is the XII battery (conserved) run
        # against the XIII lane: every mutable dependency already has
        # an executed mutation there. Invoke it as a subprocess so its
        # own gate remains the behavioral authority.
        import subprocess
        import sys

        proc = subprocess.run(
            [sys.executable, str(BATTERY), "--dsn", args.dsn],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if proc.returncode != 0:
            violations.append(
                "xiii_temporal_behavioral_failed:" + (proc.stdout + proc.stderr)[-300:]
            )
        else:
            checks["behavioral_battery_green"] = True
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIII_TEMP_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {"gate_id": "B26-P2-XIII-TEMPORAL", "status": status,
                 "violations": sorted(violations), "checks": checks},
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())

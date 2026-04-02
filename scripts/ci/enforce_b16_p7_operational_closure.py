#!/usr/bin/env python3
"""B1.6-P7 Operational Closure Gate Enforcer.

Verifies that all required P7 evidence artifacts exist in the repo before
production promotion is permitted. This is the CI-adjudication surface for
the P7 operational closure requirement.

Exit gates enforced:
  EG1: Staging telemetry evidence file exists
  EG2: Observation window evidence file exists
  EG3: Manual audit report exists
  EG4: Alert verification evidence exists
  EG5: CI gate evidence document exists
  EG6: Regression evidence document exists

This script does NOT accept prose substitutes. Only committed file presence
constitutes machine-verifiable proof. The 7-day observation window and
live telemetry requirements are separately verified in the evidence docs
themselves (which are reviewed during adjudication).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FORENSICS_ROOT = Path("docs/forensics/evidence")

REQUIRED_P7_EVIDENCE_FILES = [
    "B1.6-P7_telemetry_evidence.md",
    "B1.6-P7_observation_window_evidence.md",
    "B1.6-P7_manual_audit_report.md",
    "B1.6-P7_alert_verification_evidence.md",
    "B1.6-P7_ci_gate_evidence.md",
    "B1.6-P7_regression_evidence.md",
]

P7_EVIDENCE_DIR = FORENSICS_ROOT / "b16_p7"

PLACEHOLDER_TOKENS = (
    "PENDING",
    "TODO",
    "NOT YET COLLECTED",
    "OBSERVATION WINDOW NOT ELAPSED",
    "AWAITING STAGING",
)


def check_file_exists_and_not_placeholder(path: Path) -> list[str]:
    """Return a list of errors for the given evidence file."""
    errors: list[str] = []
    if not path.exists():
        errors.append(f"MISSING evidence file: {path}")
        return errors
    content = path.read_text(encoding="utf-8")
    for token in PLACEHOLDER_TOKENS:
        if token in content.upper():
            errors.append(
                f"Placeholder token '{token}' found in {path}. "
                "Evidence must be real, not a stub."
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B1.6-P7 operational closure evidence artifacts."
    )
    parser.add_argument(
        "--simulate-regression",
        action="store_true",
        help="Simulate a regression by always failing (for negative-control tests).",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=P7_EVIDENCE_DIR,
        help="Directory containing P7 evidence files.",
    )
    args = parser.parse_args(argv)

    if args.simulate_regression:
        print("[REGRESSION SIMULATION] enforce_b16_p7_operational_closure.py failing as designed.")
        return 1

    evidence_dir: Path = args.evidence_dir
    errors: list[str] = []

    if not evidence_dir.exists():
        errors.append(
            f"P7 evidence directory does not exist: {evidence_dir}. "
            "All six P7 evidence files must be committed before promotion."
        )
    else:
        for filename in REQUIRED_P7_EVIDENCE_FILES:
            path = evidence_dir / filename
            errors.extend(check_file_exists_and_not_placeholder(path))

    if errors:
        print("[B1.6-P7 Operational Closure Gate] FAILED — production promotion is BLOCKED.")
        for error in errors:
            print(f"  ERROR: {error}")
        print()
        print(
            "Resolution: All six P7 evidence files must be committed with real "
            "operational data (staging telemetry, 7-day observation window, manual "
            "audit confirming zero hallucinated financial leakage, alert verification, "
            "CI gate evidence, and regression evidence). "
            "See B1.6-P7 Remediation Directive for evidence requirements."
        )
        return 1

    print("[B1.6-P7 Operational Closure Gate] PASSED — all six evidence artifacts present and non-placeholder.")
    for filename in REQUIRED_P7_EVIDENCE_FILES:
        print(f"  OK: {evidence_dir / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

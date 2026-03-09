#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_SECTIONS = (
    "## Executive Verdict",
    "## Hypothesis Ledger",
    "## Root-Cause Findings",
    "## Exact Remediations Performed",
    "## Proof Pointers",
    "## Exit Gates",
    "## Blockers",
    "## Non-Blocking Observations",
    "## Authorization Decision",
)

REQUIRED_PATTERNS = (
    ("h_p0_01", re.compile(r"H-P0-01", re.IGNORECASE)),
    ("h_p0_09", re.compile(r"H-P0-09", re.IGNORECASE)),
    ("raw_branch_protection", re.compile(r"raw branch-protection output", re.IGNORECASE)),
    ("ci_run_url", re.compile(r"https://github\.com/[^\s)]+/actions/runs/\d+", re.IGNORECASE)),
    ("exit_gate_1", re.compile(r"Exit Gate 1", re.IGNORECASE)),
    ("exit_gate_4", re.compile(r"Exit Gate 4", re.IGNORECASE)),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="B1.3-P0 evidence pack shape enforcement")
    parser.add_argument(
        "--evidence-pack",
        default="docs/forensics/B1.3-P0_Remediation_Evidence_Pack.md",
    )
    args = parser.parse_args()

    evidence_path = (REPO_ROOT / args.evidence_pack).resolve()
    if not evidence_path.exists():
        print(f"B1.3-P0 evidence gate failed: file not found {evidence_path}")
        return 1

    text = evidence_path.read_text(encoding="utf-8")
    errors: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"Missing required section: {section}")

    for name, pattern in REQUIRED_PATTERNS:
        if not pattern.search(text):
            errors.append(f"Missing required evidence pattern: {name}")

    if "PASS" not in text and "FAIL" not in text:
        errors.append("Evidence pack must contain PASS/FAIL verdict tokens")

    if errors:
        print("B1.3-P0 evidence gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P0 evidence gate passed.")
    print(f"  evidence_pack={evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

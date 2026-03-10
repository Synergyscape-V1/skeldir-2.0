#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


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
    ("h_p2_01", re.compile(r"H-P2-01", re.IGNORECASE)),
    ("h_p2_08", re.compile(r"H-P2-08", re.IGNORECASE)),
    ("exit_gate_1", re.compile(r"Exit Gate 1", re.IGNORECASE)),
    ("exit_gate_4", re.compile(r"Exit Gate 4", re.IGNORECASE)),
    ("p2_check_name", re.compile(r"B1\.3 P2 Handshake State Proofs", re.IGNORECASE)),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P2 evidence pack shape enforcement")
    parser.add_argument(
        "--evidence-pack",
        default="docs/forensics/B1.3-P2_Remediation_Evidence_Pack.md",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    evidence_path = Path(args.evidence_pack)
    if not evidence_path.exists():
        print(f"B1.3-P2 evidence gate failed: file not found {evidence_path}")
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
        errors.append("Evidence pack must contain PASS/FAIL verdict token")

    if errors:
        print("B1.3-P2 evidence gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P2 evidence gate passed.")
    print(f"  evidence_pack={evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Utility to record phase gate acknowledgements into the evidence registry.

Writes backend/validation/evidence/phase_ack/<phase>.json with metadata about
the gate status, commit, workflow, and run identifiers.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record phase gate acknowledgement."
    )
    parser.add_argument("--phase", required=True, help="Phase identifier (e.g., B0.1)")
    parser.add_argument(
        "--status",
        required=True,
        choices=["success", "failure", "skipped"],
        help="Gate result status.",
    )
    parser.add_argument(
        "--message",
        default="",
        help="Optional descriptive message to include with the acknowledgement.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    evidence_dir = (
        repo_root / "backend" / "validation" / "evidence" / "phase_ack"
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)

    ack_path = evidence_dir / f"{args.phase.replace('.', '_')}.json"

    payload = {
        "phase": args.phase,
        "status": args.status,
        "message": args.message,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "workflow": os.environ.get("GITHUB_WORKFLOW", "local-run"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local"),
    }

    with open(ack_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(f"Recorded phase acknowledgement at {ack_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

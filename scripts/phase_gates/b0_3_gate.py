#!/usr/bin/env python3
"""B0.3 gate runner for Phase 2 schema closure."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "backend" / "validation" / "evidence" / "database"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


class GateFailure(RuntimeError):
    pass


def run_command(cmd: List[str], log_name: str, env: dict | None = None) -> None:
    log_path = EVIDENCE_DIR / log_name
    with open(log_path, "w", encoding="utf-8") as log_file:
        process = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
    if process.returncode != 0:
        raise GateFailure(f"Command {' '.join(cmd)} failed (see {log_path})")


def run_b0_3_gate() -> dict:
    summary = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "steps": [],
    }
    env = os.environ.copy()
    if "DATABASE_URL" not in env:
        raise GateFailure("DATABASE_URL environment variable is required.")

    # Phase 2 closure gate (EG2.1-EG2.5 + non-vacuous controls).
    run_command(
        [
            "python",
            "scripts/ci/phase2_schema_closure_gate.py",
            "--evidence-dir",
            str(EVIDENCE_DIR / "phase2_b03"),
        ],
        "phase2_schema_closure_gate.log",
        env=env,
    )
    summary["steps"].append({"name": "phase2_schema_closure", "status": "success"})

    return summary


def main() -> int:
    summary_path = EVIDENCE_DIR / "b0_3_summary.json"
    ack_path = REPO_ROOT / "backend" / "validation" / "evidence" / "phase_ack" / "B0_3.json"
    try:
        summary = run_b0_3_gate()
        summary["status"] = "success"
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        ack_path.parent.mkdir(parents=True, exist_ok=True)
        ack_payload = {
            "phase": "B0.3",
            "status": "PASS",
            "timestamp": summary["timestamp"],
            "steps": summary["steps"],
        }
        with open(ack_path, "w", encoding="utf-8") as ack_file:
            json.dump(ack_payload, ack_file, indent=2)
        print("B0.3 gate completed successfully.")
        return 0
    except GateFailure as exc:
        summary = {
            "status": "failure",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "error": str(exc),
        }
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"B0.3 gate failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

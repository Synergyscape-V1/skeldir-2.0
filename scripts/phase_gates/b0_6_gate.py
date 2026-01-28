#!/usr/bin/env python3
"""
B0.6 gate runner for realtime revenue cache + stampede prevention.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "backend" / "validation" / "evidence" / "phases"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


class GateFailure(RuntimeError):
    pass


def run(cmd: list[str], log_name: str, env: dict | None = None) -> None:
    log_path = EVIDENCE_DIR / log_name
    with log_path.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            cmd,
            stdout=fh,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=Path(__file__).resolve().parents[2],
            env=env,
        )
    if proc.returncode != 0:
        raise GateFailure(f"Command {' '.join(cmd)} failed (see {log_path})")


def main() -> int:
    env = os.environ.copy()
    if "DATABASE_URL" not in env:
        print("DATABASE_URL is required.", file=os.sys.stderr)
        return 1
    summary_path = EVIDENCE_DIR / "b0_6_summary.json"
    try:
        run(["alembic", "upgrade", "skeldir_foundation@head"], "b0_6_alembic.log", env=env)
        run(
            [
                "python",
                "-m",
                "pytest",
                "backend/tests/test_b060_phase3_realtime_revenue_cache.py",
                "-v",
            ],
            "b0_6_realtime_revenue_cache.log",
            env=env,
        )
        summary = {
            "phase": "B0.6",
            "status": "success",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    except GateFailure as exc:
        summary = {
            "phase": "B0.6",
            "status": "failure",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "error": str(exc),
        }
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return 0 if summary["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

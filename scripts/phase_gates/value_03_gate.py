"""
VALUE_03-WIN gate runner.

Ensures required schema is migrated (including llm_call_audit),
then runs the Value Trace 03 test which proves budget enforcement.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "backend" / "validation" / "evidence" / "phases"
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
            cwd=REPO_ROOT,
            env=env,
        )
    if proc.returncode != 0:
        raise GateFailure(f"Command {' '.join(cmd)} failed (see {log_path})")


def main() -> int:
    env = os.environ.copy()
    if "DATABASE_URL" not in env:
        print("DATABASE_URL is required.", file=os.sys.stderr)
        return 1

    try:
        # Run core migrations
        run(["alembic", "upgrade", "202511131121"], "value_03_alembic_core.log", env=env)
        run(
            ["alembic", "upgrade", "skeldir_foundation@head"],
            "value_03_alembic_foundation.log",
            env=env,
        )
        # Run forensic migrations (llm_call_audit)
        run(
            ["alembic", "upgrade", "head"],
            "value_03_alembic_forensic.log",
            env=env,
        )
        # Run VALUE_03-WIN test
        run(
            [
                "python",
                "-m",
                "pytest",
                "backend/tests/value_traces/test_value_03_provider_handshake.py",
                "-q",
            ],
            "value_03_pytest.log",
            env=env,
        )
        return 0
    except GateFailure as exc:
        print(str(exc), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


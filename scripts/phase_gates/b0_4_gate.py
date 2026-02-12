#!/usr/bin/env python3
"""
B0.4 gate runner for ingestion soundness.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "backend" / "validation" / "evidence" / "phases"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


class GateFailure(RuntimeError):
    pass


def run(cmd: list[str], log_name: str, env: dict | None = None) -> None:
    log_path = EVIDENCE_DIR / log_name
    with log_path.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True, cwd=Path(__file__).resolve().parents[2], env=env)
    if proc.returncode != 0:
        raise GateFailure(f"Command {' '.join(cmd)} failed (see {log_path})")


def wait_for_http_ready(base_url: str, timeout_s: int = 60) -> None:
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as resp:
                if 200 <= int(resp.status) < 300:
                    return
        except Exception:
            time.sleep(1)
    raise GateFailure(f"API failed readiness check at {base_url}/health within {timeout_s}s")


def main() -> int:
    env = os.environ.copy()
    if "DATABASE_URL" not in env:
        print("DATABASE_URL is required.", file=os.sys.stderr)
        return 1
    summary_path = EVIDENCE_DIR / "b0_4_summary.json"
    try:
        run(["alembic", "upgrade", "202511131121"], "b0_4_alembic_core.log", env=env)
        run(["alembic", "upgrade", "skeldir_foundation@head"], "b0_4_alembic_foundation.log", env=env)
        run(
            ["python", "-m", "pytest", "backend/tests/test_b04_ingestion_soundness.py", "-q"],
            "b0_4_ingestion_soundness.log",
            env=env,
        )
        run(
            ["python", "scripts/security/phase4_enforcement_probe.py"],
            "b0_4_phase4_security_probe.log",
            env=env,
        )

        # EG4.7: run unchanged EG3.4 customer-profile perf suite under RLS-enabled schema.
        base_url = env.get("R3_API_BASE_URL", "http://127.0.0.1:8000")
        uvicorn_log = EVIDENCE_DIR / "b0_4_r3_uvicorn.log"
        with uvicorn_log.open("w", encoding="utf-8") as fh:
            server = subprocess.Popen(
                [
                    "python",
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--workers",
                    env.get("R3_SERVER_WORKERS", "2"),
                    "--no-access-log",
                ],
                cwd=Path(__file__).resolve().parents[2] / "backend",
                env=env,
                stdout=fh,
                stderr=subprocess.STDOUT,
                text=True,
            )
        try:
            wait_for_http_ready(base_url=base_url, timeout_s=90)
            run(["python", "scripts/r3/ingestion_under_fire.py"], "b0_4_r3_harness.log", env=env)
        finally:
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()

        summary = {
            "phase": "B0.4",
            "status": "success",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    except GateFailure as exc:
        summary = {
            "phase": "B0.4",
            "status": "failure",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "error": str(exc),
        }
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return 0 if summary["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
B0.2 gate runner for mock server deployment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "backend" / "validation" / "evidence" / "mocks"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
GIT_BASH_PATH = Path(
    os.environ.get("GIT_BASH_PATH", r"C:\Program Files\Git\bin\bash.exe")
)
TOOLS_DIR = REPO_ROOT / "tools"
TOOLS_JQ = TOOLS_DIR / "jq"

BASE_ENV = os.environ.copy()
BASE_ENV.setdefault("PYTHONPATH", str(REPO_ROOT))
BASE_ENV.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
additional_paths: list[str] = []
if TOOLS_JQ.exists():
    additional_paths.append(str(TOOLS_JQ))
if Path(r"C:\Program Files\nodejs").exists():
    additional_paths.append(r"C:\Program Files\nodejs")
if additional_paths:
    BASE_ENV["PATH"] = os.pathsep.join(additional_paths + [BASE_ENV.get("PATH", "")])


class GateFailure(RuntimeError):
    pass


def resolve_command(cmd: List[str]) -> List[str]:
    resolved = cmd[:]
    if resolved and resolved[0] == "bash":
        if GIT_BASH_PATH.exists():
            resolved[0] = str(GIT_BASH_PATH)
        else:
            bash_exe = shutil.which("bash")
            if bash_exe:
                resolved[0] = bash_exe
    if os.name == "nt" and resolved:
        if resolved[0] == "npx":
            resolved = ["cmd", "/c", *resolved]
    return resolved


def run_command(cmd: List[str], log_name: str) -> None:
    log_path = EVIDENCE_DIR / log_name
    resolved_cmd = resolve_command(cmd)
    with open(log_path, "w", encoding="utf-8") as log_file:
        process = subprocess.run(
            resolved_cmd,
            cwd=REPO_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env=BASE_ENV,
        )
    if process.returncode != 0:
        raise GateFailure(f"Command {' '.join(resolved_cmd)} failed (see {log_path})")


def run_b0_2_gate() -> dict:
    summary = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "steps": [],
    }

    # R1: Configuration alignment
    run_command(
        [
            "python",
            "scripts/mocks/validate_config.py",
            "--output",
            str(EVIDENCE_DIR / "mock_config_report.json"),
        ],
        "mock_config.log",
    )
    summary["steps"].append({"name": "config", "status": "success"})

    # R2: Prism toolchain
    run_command(
        [
            "python",
            "scripts/mocks/check_prism_toolchain.py",
            "--output",
            str(EVIDENCE_DIR / "prism_toolchain_report.json"),
        ],
        "prism_toolchain.log",
    )
    summary["steps"].append({"name": "toolchain", "status": "success"})

    # Ensure bundled contracts exist for all registered mock domains.
    run_command(["bash", "scripts/contracts/bundle.sh"], "bundle_contracts.log")
    summary["steps"].append({"name": "bundle_contracts", "status": "success"})

    mocks_started = False
    try:
        # Start mocks
        run_command(["bash", "scripts/start-mocks.sh"], "start_mocks.log")
        mocks_started = True

        # R3: Contract integrity tests
        run_command(
            ["python", "-m", "pytest", "tests/contract/test_mock_integrity.py", "-q"],
            "mock_integrity.log",
        )
        run_command(
            ["python", "-m", "pytest", "tests/contract/test_route_fidelity.py", "-q"],
            "route_fidelity.log",
        )
        summary["steps"].append({"name": "behavior", "status": "success"})

        # R4: Latency measurement
        run_command(["bash", "scripts/measure-latency.sh"], "latency.log")
        latency_src = REPO_ROOT / "mocks-latency-report.json"
        if latency_src.exists():
            shutil.move(latency_src, EVIDENCE_DIR / "latency_report.json")
        summary["steps"].append({"name": "latency", "status": "success"})

        # R5: Error simulation
        run_command(["bash", "scripts/test-response-parity.sh"], "response_parity.log")
        summary["steps"].append({"name": "error_simulation", "status": "success"})

        # R6: Frontend integration (Playwright)
        run_command(
            [
                "npx",
                "playwright",
                "test",
                "tests/frontend-integration.spec.ts",
            ],
            "playwright.log",
        )
        summary["steps"].append({"name": "frontend", "status": "success"})
    finally:
        if mocks_started:
            subprocess.run(
                resolve_command(["bash", "scripts/stop-mocks.sh"]),
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=BASE_ENV,
            )

    return summary


def main() -> int:
    summary_path = EVIDENCE_DIR / "b0_2_summary.json"
    try:
        summary = run_b0_2_gate()
        summary["status"] = "success"
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print("B0.2 gate completed successfully.")
        return 0
    except GateFailure as exc:
        summary = {
            "status": "failure",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "error": str(exc),
        }
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"B0.2 gate failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

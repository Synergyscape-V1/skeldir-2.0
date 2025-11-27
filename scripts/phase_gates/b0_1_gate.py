#!/usr/bin/env python3
"""
B0.1 gate runner.

Executes all contract validation requirements (R1-R6) and captures evidence.
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
EVIDENCE_DIR = REPO_ROOT / "backend" / "validation" / "evidence" / "contracts"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
GIT_BASH_PATH = Path(
    os.environ.get("GIT_BASH_PATH", r"C:\Program Files\Git\bin\bash.exe")
)
TOOLS_OASDIFF = REPO_ROOT / "tools" / "oasdiff"

BASE_ENV = os.environ.copy()
BASE_ENV.setdefault("PYTHONPATH", str(REPO_ROOT))
BASE_ENV.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
if TOOLS_OASDIFF.exists():
    BASE_ENV["PATH"] = f"{str(TOOLS_OASDIFF)}{os.pathsep}{BASE_ENV.get('PATH', '')}"


class GateFailure(RuntimeError):
    """Raised when a gate step fails."""


def resolve_command(cmd: List[str]) -> List[str]:
    resolved = cmd[:]
    if resolved and resolved[0] == "bash":
        if GIT_BASH_PATH.exists():
            resolved[0] = str(GIT_BASH_PATH)
        else:
            bash_exe = shutil.which("bash")
            if bash_exe:
                resolved[0] = bash_exe
    return resolved


def run_command(cmd: List[str], log_name: str) -> None:
    resolved_cmd = resolve_command(cmd)
    log_path = EVIDENCE_DIR / log_name
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


def run_b0_1_gate() -> dict:
    summary = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "steps": [],
    }

    # R1 & R4: Contract validation + breaking change detection
    run_command(["bash", "scripts/contracts/validate-contracts.sh"], "contract_validation.log")
    summary["steps"].append({"name": "contract_validation", "status": "success"})

    # R2: RFC 7807 error model check
    run_command(
        [
            "python",
            "scripts/contracts/check_error_model.py",
            "--output",
            str(EVIDENCE_DIR / "error_model_report.json"),
        ],
        "error_model.log",
    )
    summary["steps"].append({"name": "error_model", "status": "success"})

    # R3: Example coverage check
    run_command(
        [
            "python",
            "scripts/contracts/check_examples.py",
            "--output",
            str(EVIDENCE_DIR / "example_validation_report.json"),
        ],
        "examples.log",
    )
    summary["steps"].append({"name": "examples", "status": "success"})

    # R5: Model generation + dependency checks
    run_command(["bash", "scripts/generate-models.sh"], "model_generation.log")
    run_command(["python", "scripts/check_model_usage.py"], "model_usage.log")
    run_command(
        ["python", "-m", "pytest", "backend/tests/test_generated_models.py", "-q"],
        "model_pytest.log",
    )
    summary["steps"].append({"name": "models", "status": "success"})

    # R6: Provider contract tests (implementation vs contracts)
    run_command(
        ["python", "-m", "pytest", "tests/contract/test_contract_semantics.py", "-q"],
        "provider_contract_tests.log",
    )
    summary["steps"].append({"name": "contract_semantics", "status": "success"})

    return summary


def main() -> int:
    summary_path = EVIDENCE_DIR / "b0_1_summary.json"
    try:
        summary = run_b0_1_gate()
        summary["status"] = "success"
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print("B0.1 gate completed successfully.")
        return 0
    except GateFailure as exc:
        summary = {
            "status": "failure",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "error": str(exc),
        }
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"B0.1 gate failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

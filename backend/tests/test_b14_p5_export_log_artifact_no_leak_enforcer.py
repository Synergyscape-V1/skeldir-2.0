from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b14_p5_export_log_artifact_no_leak.py"
REQUIRED_CHECKS = REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
EXPORT_FILE = REPO_ROOT / "backend" / "app" / "api" / "export.py"


def _run(extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(SCRIPT)]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def test_b14_p5_enforcer_passes_repo_state() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b14_p5_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.4 P5 Export Log Artifact No-Leak"
    ]
    checks_copy = tmp_path / "required_checks.json"
    checks_copy.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(["--required-checks-file", str(checks_copy)])
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "missing_required_context_in_contract" in combined


def test_b14_p5_negative_control_detects_export_allowlist_regression(tmp_path: Path) -> None:
    mutated = EXPORT_FILE.read_text(encoding="utf-8").replace("EXPORT_ROW_ALLOWLIST", "EXPORT_ROW_REMOVED")
    export_copy = tmp_path / "export.py"
    export_copy.write_text(mutated, encoding="utf-8")

    result = _run(["--export-file", str(export_copy)])
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "export_surface_missing_token:EXPORT_ROW_ALLOWLIST" in combined


def test_b14_p5_negative_control_simulate_regression_flag() -> None:
    result = _run(["--simulate-regression"])
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "synthetic_regression=no_leak_gate_removed" in combined

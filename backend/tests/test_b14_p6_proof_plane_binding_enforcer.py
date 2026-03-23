"""B1.4-P6 proof-plane binding enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b14_p6_proof_plane_binding.py"
REQUIRED_CHECKS = (
    REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
)
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"


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


def test_b14_p6_enforcer_passes_repo_state() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b14_p6_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    payload = json.loads(REQUIRED_CHECKS.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.4 P6 Merge-Blocking Privacy Proof Plane Binding"
    ]
    checks_copy = tmp_path / "required_checks.json"
    checks_copy.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(["--required-checks-file", str(checks_copy)])
    assert result.returncode != 0
    assert "required_checks_missing_context:B1.4 P6 Merge-Blocking Privacy Proof Plane Binding" in (
        result.stdout + result.stderr
    )


def test_b14_p6_negative_control_detects_artifact_contract_drift(tmp_path: Path) -> None:
    workflow_copy = tmp_path / "ci.workflow.regression.yml"
    workflow_text = WORKFLOW_FILE.read_text(encoding="utf-8")
    workflow_copy.write_text(
        workflow_text.replace("name: b14-p0-runtime-artifacts", "name: b14-p0-runtime-artifacts-regressed", 1),
        encoding="utf-8",
    )

    result = _run(["--workflow-file", str(workflow_copy)])
    assert result.returncode != 0
    assert "job_artifact_name_mismatch:b14-p0-privacy-authority-lock" in (result.stdout + result.stderr)


def test_b14_p6_negative_control_simulate_regression() -> None:
    result = _run(["--simulate-regression"])
    assert result.returncode != 0
    assert "synthetic_regression=proof_plane_binding_removed" in (result.stdout + result.stderr)

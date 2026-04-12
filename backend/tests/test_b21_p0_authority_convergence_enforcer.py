from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.ci.enforce_b21_p0_authority_convergence import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p0_authority_convergence.py"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
RUNTIME_PROOF = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p0_runtime_authority_closeout.py"


def test_b21_p0_authority_convergence_enforcer_passes_on_repo_state():
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        workflow_file=CI_WORKFLOW,
        runtime_proof_file=RUNTIME_PROOF,
    )
    assert status == 0, f"unexpected authority convergence violations: {violations}"


def test_b21_p0_authority_convergence_enforcer_negative_control_non_vacuous():
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--simulate-regression"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "synthetic_regression=forced_failure_path" in combined


def test_b21_p0_authority_convergence_enforcer_negative_control_missing_runtime_ci_step(
    tmp_path: Path,
):
    workflow_regression = tmp_path / "ci.workflow.regression.yml"
    workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")
    workflow_regression.write_text(
        workflow_text.replace(
            "Run B2.1-P0 closeout runtime authority proofs",
            "Run B2.1-P0 runtime proofs (regressed)",
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--workflow-file",
            str(workflow_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "workflow_missing_b21_closeout_token" in combined


def test_b21_p0_authority_convergence_enforcer_negative_control_missing_runtime_proof_token(
    tmp_path: Path,
):
    runtime_proof_regression = tmp_path / "b21.runtime.proof.regression.py"
    runtime_text = RUNTIME_PROOF.read_text(encoding="utf-8")
    runtime_proof_regression.write_text(
        runtime_text.replace(
            "test_b21_p0_worker_substrate_path_is_tenant_safe_with_cross_tenant_negative_control",
            "test_b21_p0_worker_substrate_path_regressed",
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--runtime-proof-file",
            str(runtime_proof_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "runtime_proof_missing_b21_closeout_token" in combined

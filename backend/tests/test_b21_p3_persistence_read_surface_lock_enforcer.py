from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.ci.enforce_b21_p3_persistence_read_surface_lock import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p3_persistence_read_surface_lock.py"
TASK_FILE = REPO_ROOT / "backend" / "app" / "tasks" / "attribution.py"
API_FILE = REPO_ROOT / "backend" / "app" / "api" / "attribution.py"
SCHEMA_FILE = REPO_ROOT / "backend" / "app" / "schemas" / "attribution.py"
CONTRACT_FILE = REPO_ROOT / "api-contracts" / "openapi" / "v1" / "attribution.yaml"
RUNTIME_FILE = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p3_persistence_read_surface_runtime.py"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS_FILE = REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"


def test_b21_p3_persistence_read_surface_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        task_file=TASK_FILE,
        api_file=API_FILE,
        schema_file=SCHEMA_FILE,
        contract_file=CONTRACT_FILE,
        runtime_proof_file=RUNTIME_FILE,
        workflow_file=WORKFLOW_FILE,
        required_checks_file=REQUIRED_CHECKS_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_forced_regression() -> None:
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


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_missing_projection_filter(
    tmp_path: Path,
) -> None:
    api_regression = tmp_path / "attribution_api.regression.py"
    api_regression.write_text(
        API_FILE.read_text(encoding="utf-8").replace(
            "AND aa.recompute_job_id = :recompute_job_id",
            "AND aa.tenant_id = :tenant_id",
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--api-file",
            str(api_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "api_missing_token:aa.recompute_job_id = :recompute_job_id" in combined


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_missing_contract_projection_param(
    tmp_path: Path,
) -> None:
    contract_regression = tmp_path / "attribution_contract.regression.yaml"
    contract_regression.write_text(
        CONTRACT_FILE.read_text(encoding="utf-8").replace(
            "name: model_type",
            "name: model_type_removed",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--contract-file",
            str(contract_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "contract_missing_required_query_param:model_type" in combined


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_missing_workflow_hook(
    tmp_path: Path,
) -> None:
    workflow_regression = tmp_path / "ci.regression.yml"
    workflow_regression.write_text(
        WORKFLOW_FILE.read_text(encoding="utf-8").replace(
            "Enforce B2.1-P3 persistence read-surface lock",
            "Enforce B2.1-P3 lock removed",
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
    assert "workflow_missing_token:Enforce B2.1-P3 persistence read-surface lock" in combined

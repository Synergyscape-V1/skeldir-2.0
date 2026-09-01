from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from scripts.ci.enforce_b21_p3_persistence_read_surface_lock import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p3_persistence_read_surface_lock.py"
TASK_FILE = REPO_ROOT / "backend" / "app" / "tasks" / "attribution.py"
API_FILE = REPO_ROOT / "backend" / "app" / "api" / "attribution.py"
SCHEMA_FILE = REPO_ROOT / "backend" / "app" / "schemas" / "attribution.py"
CONTRACT_FILE = REPO_ROOT / "api-contracts" / "openapi" / "v1" / "attribution.yaml"
BUNDLED_CONTRACT_FILE = (
    REPO_ROOT / "api-contracts" / "dist" / "openapi" / "v1" / "attribution.bundled.yaml"
)
FRONTEND_TYPES_FILE = REPO_ROOT / "frontend" / "src" / "types" / "api" / "attribution.ts"
FRONTEND_TYPEGEN_SCRIPT_FILE = REPO_ROOT / "scripts" / "contracts" / "generate_frontend_types.sh"
CONTRACT_BUNDLE_SCRIPT_FILE = REPO_ROOT / "scripts" / "contracts" / "bundle.sh"
CONTRACT_ENTRYPOINTS_FILE = REPO_ROOT / "scripts" / "contracts" / "entrypoints.json"
RUNTIME_FILE = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p3_persistence_read_surface_runtime.py"
CANONICAL_SCHEMA_FILE = REPO_ROOT / "db" / "schema" / "canonical_schema.sql"
TRIGGER_ALIGNMENT_MIGRATION_FILE = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202604171330_b21_p3_projection_sum_validation_alignment.py"
)
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS_FILE = REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"


def test_b21_p3_persistence_read_surface_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        task_file=TASK_FILE,
        api_file=API_FILE,
        schema_file=SCHEMA_FILE,
        contract_file=CONTRACT_FILE,
        bundled_contract_file=BUNDLED_CONTRACT_FILE,
        frontend_types_file=FRONTEND_TYPES_FILE,
        frontend_typegen_script_file=FRONTEND_TYPEGEN_SCRIPT_FILE,
        contract_bundle_script_file=CONTRACT_BUNDLE_SCRIPT_FILE,
        contract_entrypoints_file=CONTRACT_ENTRYPOINTS_FILE,
        runtime_proof_file=RUNTIME_FILE,
        canonical_schema_file=CANONICAL_SCHEMA_FILE,
        trigger_alignment_migration_file=TRIGGER_ALIGNMENT_MIGRATION_FILE,
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


CHANNELS_PATH = "/api/attribution/channels"


def _contract_without_channels_422(source: Path, destination: Path) -> None:
    """Remove the exact response the enforcer reads, not the first one in the file.

    These controls used to delete the first ``'422':`` line in the document.
    Once another path declared a 422 above the channels endpoint that edit
    stopped touching the channels response at all, and the control passed while
    proving nothing.
    """

    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    responses = document["paths"][CHANNELS_PATH]["get"]["responses"]
    assert "422" in responses, "control precondition: the channels 422 must exist"
    del responses["422"]
    destination.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_missing_contract_422_response(
    tmp_path: Path,
) -> None:
    contract_regression = tmp_path / "attribution_contract_422.regression.yaml"
    _contract_without_channels_422(CONTRACT_FILE, contract_regression)
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
    assert "contract_missing_channels_422_response" in combined


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_missing_bundled_contract_422_response(
    tmp_path: Path,
) -> None:
    bundled_contract_regression = tmp_path / "attribution_bundled_422.regression.yaml"
    _contract_without_channels_422(BUNDLED_CONTRACT_FILE, bundled_contract_regression)
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--bundled-contract-file",
            str(bundled_contract_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "bundled_contract_missing_channels_422_response" in combined


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_typegen_not_sourced_from_bundle(
    tmp_path: Path,
) -> None:
    typegen_script_regression = tmp_path / "generate_frontend_types.regression.sh"
    typegen_script_regression.write_text(
        FRONTEND_TYPEGEN_SCRIPT_FILE.read_text(encoding="utf-8").replace(
            'generate "attribution.bundled.yaml" "attribution.ts"',
            'generate "attribution.yaml" "attribution.ts"',
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--frontend-typegen-script-file",
            str(typegen_script_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert (
        'frontend_typegen_script_missing_token:generate "attribution.bundled.yaml" "attribution.ts"'
        in combined
    )


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_projection_reassignment_on_conflict(
    tmp_path: Path,
) -> None:
    task_regression = tmp_path / "attribution_task.regression.py"
    task_regression.write_text(
        TASK_FILE.read_text(encoding="utf-8").replace(
            "attribution_allocations.recompute_job_id = EXCLUDED.recompute_job_id",
            "TRUE",
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--task-file",
            str(task_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "task_missing_token:attribution_allocations.recompute_job_id = EXCLUDED.recompute_job_id" in combined


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


def test_b21_p3_persistence_read_surface_lock_enforcer_negative_control_missing_projection_sum_scope(
    tmp_path: Path,
) -> None:
    schema_regression = tmp_path / "canonical_schema.regression.sql"
    schema_regression.write_text(
        CANONICAL_SCHEMA_FILE.read_text(encoding="utf-8").replace(
            "a.recompute_job_id IS NOT NULL AND aa.recompute_job_id = a.recompute_job_id",
            "a.recompute_job_id IS NOT NULL",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--canonical-schema-file",
            str(schema_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "canonical_schema_projection_scope_count_lt_3:2" in combined

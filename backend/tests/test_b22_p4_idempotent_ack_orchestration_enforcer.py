from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b22_p4_idempotent_ack_orchestration.py"
_SPEC = importlib.util.spec_from_file_location("b22_p4_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement

GOVERNANCE_CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b22_p4_idempotent_ack_orchestration.main.json"
)
EVENT_SERVICE_FILE = REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py"
WEBHOOKS_FILE = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
P4_TEST_FILE = REPO_ROOT / "backend" / "tests" / "test_b22_p4_idempotent_ack_orchestration.py"
P4_ENFORCER_TEST_FILE = (
    REPO_ROOT / "backend" / "tests" / "test_b22_p4_idempotent_ack_orchestration_enforcer.py"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b22_p4_idempotent_ack_orchestration_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        governance_contract=GOVERNANCE_CONTRACT,
        event_service_file=EVENT_SERVICE_FILE,
        webhooks_file=WEBHOOKS_FILE,
        ci_workflow=CI_WORKFLOW,
        p4_test_file=P4_TEST_FILE,
        p4_enforcer_test_file=P4_ENFORCER_TEST_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b22_p4_idempotent_ack_orchestration_enforcer_negative_control_forced_regression() -> None:
    proc = _run("--simulate-regression")
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b22_p4_idempotent_ack_orchestration_enforcer_negative_control_private_duplicate_marker_detected(
    tmp_path: Path,
) -> None:
    mutated_event_service = tmp_path / "event_service.regression.py"
    mutated_event_service.write_text(
        EVENT_SERVICE_FILE.read_text(encoding="utf-8")
        + "\n# regression marker\n_ingestion_duplicate = True\n",
        encoding="utf-8",
    )
    proc = _run("--event-service-file", str(mutated_event_service))
    assert proc.returncode != 0
    assert "event_service_forbidden_token_present:_ingestion_duplicate" in (proc.stdout + proc.stderr)


def test_b22_p4_idempotent_ack_orchestration_enforcer_negative_control_ci_wiring_missing(
    tmp_path: Path,
) -> None:
    mutated_workflow = tmp_path / "ci.regression.yml"
    mutated_workflow.write_text(
        CI_WORKFLOW.read_text(encoding="utf-8").replace(
            "python scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py",
            "python scripts/ci/enforce_b22_p4_regressed.py",
            1,
        ),
        encoding="utf-8",
    )
    proc = _run("--ci-workflow", str(mutated_workflow))
    assert proc.returncode != 0
    assert "ci_missing_b22_p4_token" in (proc.stdout + proc.stderr)


def test_b22_p4_idempotent_ack_orchestration_enforcer_negative_control_contract_ack_outcome_drift(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["ack_matrix_contract"].pop("unsupported_event_family")
    mutated_contract = tmp_path / "b22_p4.regression.contract.json"
    mutated_contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract", str(mutated_contract))
    assert proc.returncode != 0
    assert "contract_ack_outcome_set_mismatch" in (proc.stdout + proc.stderr)

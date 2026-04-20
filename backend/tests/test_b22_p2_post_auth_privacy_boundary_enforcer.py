from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b22_p2_post_auth_privacy_boundary.py"
_SPEC = importlib.util.spec_from_file_location("b22_p2_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement

GOVERNANCE_CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b22_p2_post_auth_privacy_boundary.main.json"
)
EVENT_SERVICE_FILE = REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py"
WEBHOOKS_FILE = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
DLQ_HANDLER_FILE = REPO_ROOT / "backend" / "app" / "ingestion" / "dlq_handler.py"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
P2_TEST_FILE = REPO_ROOT / "backend" / "tests" / "test_b22_p2_post_auth_privacy_boundary.py"
P2_ENFORCER_TEST_FILE = (
    REPO_ROOT / "backend" / "tests" / "test_b22_p2_post_auth_privacy_boundary_enforcer.py"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b22_p2_post_auth_privacy_boundary_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        governance_contract=GOVERNANCE_CONTRACT,
        event_service_file=EVENT_SERVICE_FILE,
        webhooks_file=WEBHOOKS_FILE,
        dlq_handler_file=DLQ_HANDLER_FILE,
        ci_workflow=CI_WORKFLOW,
        p2_test_file=P2_TEST_FILE,
        p2_enforcer_test_file=P2_ENFORCER_TEST_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b22_p2_post_auth_privacy_boundary_enforcer_negative_control_forced_regression() -> None:
    proc = _run("--simulate-regression")
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b22_p2_post_auth_privacy_boundary_enforcer_negative_control_ci_wiring_missing(
    tmp_path: Path,
) -> None:
    mutated_workflow = tmp_path / "ci.regression.yml"
    mutated_workflow.write_text(
        CI_WORKFLOW.read_text(encoding="utf-8").replace(
            "python scripts/ci/enforce_b22_p2_post_auth_privacy_boundary.py",
            "python scripts/ci/enforce_b22_p2_regressed.py",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--ci-workflow", str(mutated_workflow))
    assert proc.returncode != 0
    assert "ci_missing_b22_p2_token" in (proc.stdout + proc.stderr)


def test_b22_p2_post_auth_privacy_boundary_enforcer_negative_control_contract_disallowed_field_drift(
    tmp_path: Path,
) -> None:
    payload = json.loads(GOVERNANCE_CONTRACT.read_text(encoding="utf-8"))
    payload["disallowed_durable_ingress_identifiers"] = ["ip_address", "raw_headers"]
    mutated_contract = tmp_path / "b22_p2.regression.contract.json"
    mutated_contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--governance-contract", str(mutated_contract))
    assert proc.returncode != 0
    assert "contract_disallowed_field_set_mismatch" in (proc.stdout + proc.stderr)


def test_b22_p2_post_auth_privacy_boundary_enforcer_negative_control_event_service_regression(
    tmp_path: Path,
) -> None:
    mutated_event_service = tmp_path / "event_service.regression.py"
    mutated_event_service.write_text(
        EVENT_SERVICE_FILE.read_text(encoding="utf-8").replace(
            "return None, None, None",
            "return _first_header_value(normalized_headers, (\"x-forwarded-for\", \"x-real-ip\")), _first_header_value(normalized_headers, (\"user-agent\",)), dict(normalized_headers) or None",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--event-service-file", str(mutated_event_service))
    assert proc.returncode != 0
    assert "event_service_missing_token:return None, None, None" in (proc.stdout + proc.stderr)

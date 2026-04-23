from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b22_p6_merge_blocking_closure.py"
_SPEC = importlib.util.spec_from_file_location("b22_p6_enforcer_module", ENFORCER)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
run_enforcement = _MODULE.run_enforcement

GOVERNANCE_CONTRACT = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b22_p6_merge_blocking_closure.main.json"
)
REQUIRED_CHECKS_FILE = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b03_phase2_required_status_checks.main.json"
)
CI_WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
TRUTH_INGRESS_TEST_FILE = (
    REPO_ROOT / "backend" / "tests" / "integration" / "test_b22_p6_end_to_end_truth_ingress.py"
)
B23_COMPAT_TEST_FILE = (
    REPO_ROOT / "backend" / "tests" / "integration" / "test_b22_p6_b23_downstream_readiness.py"
)
WEBHOOKS_FILE = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
EVENT_SERVICE_FILE = REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py"
P6_ENFORCER_TEST_FILE = (
    REPO_ROOT / "backend" / "tests" / "test_b22_p6_merge_blocking_closure_enforcer.py"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b22_p6_merge_blocking_closure_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        governance_contract_file=GOVERNANCE_CONTRACT,
        required_checks_file=REQUIRED_CHECKS_FILE,
        ci_workflow_file=CI_WORKFLOW_FILE,
        p6_truth_ingress_test_file=TRUTH_INGRESS_TEST_FILE,
        p6_b23_compat_test_file=B23_COMPAT_TEST_FILE,
        webhooks_file=WEBHOOKS_FILE,
        event_service_file=EVENT_SERVICE_FILE,
        p6_enforcer_test_file=P6_ENFORCER_TEST_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b22_p6_merge_blocking_closure_enforcer_negative_control_forced_regression() -> None:
    proc = _run("--simulate-regression")
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b22_p6_merge_blocking_closure_enforcer_negative_control_required_context_missing(
    tmp_path: Path,
) -> None:
    payload = json.loads(REQUIRED_CHECKS_FILE.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        item
        for item in payload.get("required_contexts", [])
        if item != "B2.2-P6 Merge-Blocking Closure + Downstream Readiness"
    ]
    mutated = tmp_path / "required_checks.regression.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = _run("--required-checks-file", str(mutated))
    assert proc.returncode != 0
    assert "required_checks_missing_context:B2.2-P6 Merge-Blocking Closure + Downstream Readiness" in (
        proc.stdout + proc.stderr
    )


def test_b22_p6_merge_blocking_closure_enforcer_negative_control_ci_wiring_missing(
    tmp_path: Path,
) -> None:
    mutated_ci = tmp_path / "ci.regression.yml"
    mutated_ci.write_text(
        CI_WORKFLOW_FILE.read_text(encoding="utf-8").replace(
            "pytest backend/tests/integration/test_b22_p6_end_to_end_truth_ingress.py -q",
            "pytest backend/tests/integration/test_removed_b22_p6_end_to_end_truth_ingress.py -q",
            1,
        ),
        encoding="utf-8",
    )
    proc = _run("--ci-workflow-file", str(mutated_ci))
    assert proc.returncode != 0
    assert "workflow_missing_token:pytest backend/tests/integration/test_b22_p6_end_to_end_truth_ingress.py -q" in (
        proc.stdout + proc.stderr
    )


def test_b22_p6_merge_blocking_closure_enforcer_negative_control_truth_suite_provider_drift(
    tmp_path: Path,
) -> None:
    mutated_truth = tmp_path / "truth_ingress.regression.py"
    mutated_truth.write_text(
        TRUTH_INGRESS_TEST_FILE.read_text(encoding="utf-8").replace(
            "/api/webhooks/paypal/sale_completed",
            "/api/webhooks/paypal/removed_sale_completed",
            1,
        ),
        encoding="utf-8",
    )
    proc = _run("--p6-truth-ingress-test-file", str(mutated_truth))
    assert proc.returncode != 0
    assert "truth_ingress_suite_missing_provider_route_token:paypal" in (
        proc.stdout + proc.stderr
    )


def test_b22_p6_merge_blocking_closure_enforcer_negative_control_b23_reconciliation_guard_missing(
    tmp_path: Path,
) -> None:
    mutated_b23 = tmp_path / "b23_compat.regression.py"
    mutated_b23.write_text(
        B23_COMPAT_TEST_FILE.read_text(encoding="utf-8").replace(
            "reconciliation_invocations[\"count\"] == 0",
            "reconciliation_invocations[\"count\"] == 1",
            1,
        ),
        encoding="utf-8",
    )
    proc = _run("--p6-b23-compat-test-file", str(mutated_b23))
    assert proc.returncode != 0
    assert "b23_readiness_suite_missing_token:reconciliation_invocations[\"count\"] == 0" in (
        proc.stdout + proc.stderr
    )

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ci.enforce_b21_p6_full_chain_closure import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p6_full_chain_closure.py"
REQUIRED_CHECKS_FILE = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b03_phase2_required_status_checks.main.json"
)
CI_WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
P6_RUNTIME_FILE = (
    REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p6_end_to_end_runtime.py"
)
P6_EVIDENCE_FILE = REPO_ROOT / "docs" / "forensics" / "B2.1-P6 Remediation Evidence Pack .md"
CONTEXT_REPORT_FILE = REPO_ROOT / "docs" / "forensics" / "B2.1_Context_Inventory_Report.md"
FORENSICS_INDEX_FILE = REPO_ROOT / "docs" / "forensics" / "INDEX.md"


def test_b21_p6_full_chain_closure_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        required_checks_file=REQUIRED_CHECKS_FILE,
        ci_workflow_file=CI_WORKFLOW_FILE,
        p6_runtime_file=P6_RUNTIME_FILE,
        p6_evidence_file=P6_EVIDENCE_FILE,
        context_report_file=CONTEXT_REPORT_FILE,
        forensics_index_file=FORENSICS_INDEX_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b21_p6_full_chain_closure_enforcer_negative_control_forced_regression() -> None:
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--simulate-regression"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b21_p6_full_chain_closure_enforcer_negative_control_missing_required_context(
    tmp_path: Path,
) -> None:
    payload = json.loads(REQUIRED_CHECKS_FILE.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        ctx
        for ctx in payload.get("required_contexts", [])
        if ctx != "B2.1-P6 Full End-to-End Closure + Downstream Readiness"
    ]
    mutated = tmp_path / "required_checks.regression.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--required-checks-file",
            str(mutated),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "required_checks_missing_context:B2.1-P6 Full End-to-End Closure + Downstream Readiness" in (
        proc.stdout + proc.stderr
    )


def test_b21_p6_full_chain_closure_enforcer_negative_control_missing_runtime_step(
    tmp_path: Path,
) -> None:
    workflow_regression = tmp_path / "ci.regression.yml"
    workflow_regression.write_text(
        CI_WORKFLOW_FILE.read_text(encoding="utf-8").replace(
            "pytest backend/tests/integration/test_b21_p6_end_to_end_runtime.py -q",
            "pytest backend/tests/integration/test_removed_b21_p6_end_to_end_runtime.py -q",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--ci-workflow-file", str(workflow_regression)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "workflow_missing_token:pytest backend/tests/integration/test_b21_p6_end_to_end_runtime.py -q" in (
        proc.stdout + proc.stderr
    )


def test_b21_p6_full_chain_closure_enforcer_negative_control_runtime_model_set_drift(
    tmp_path: Path,
) -> None:
    runtime_regression = tmp_path / "p6_runtime.regression.py"
    runtime_regression.write_text(
        P6_RUNTIME_FILE.read_text(encoding="utf-8").replace(
            "\"first_touch\", \"last_touch\", \"linear\", \"time_decay\"",
            "\"first_touch\", \"linear\"",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--p6-runtime-file", str(runtime_regression)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "p6_runtime_missing_token:\"first_touch\", \"last_touch\", \"linear\", \"time_decay\"" in (
        proc.stdout + proc.stderr
    )

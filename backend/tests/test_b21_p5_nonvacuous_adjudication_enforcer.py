from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from scripts.ci.enforce_b21_p5_nonvacuous_adjudication import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p5_nonvacuous_adjudication.py"
REQUIRED_CHECKS_FILE = (
    REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
)
CI_WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
TASK_FILE = REPO_ROOT / "backend" / "app" / "tasks" / "attribution.py"
P1_RUNTIME_FILE = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p1_semantic_replay_runtime.py"
P2_RUNTIME_FILE = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p2_strategy_runtime.py"
P5_RUNTIME_FILE = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p5_nonvacuous_runtime.py"
ROUTE_FIDELITY_FILE = REPO_ROOT / "tests" / "contract" / "test_route_fidelity.py"
CONTRACT_SEMANTICS_FILE = REPO_ROOT / "tests" / "contract" / "test_contract_semantics.py"
SEMANTICS_SKIP_ALLOWLIST_FILE = REPO_ROOT / "tests" / "contract" / "semantics_skip_allowlist.yaml"


def test_b21_p5_nonvacuous_adjudication_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        required_checks_file=REQUIRED_CHECKS_FILE,
        ci_workflow_file=CI_WORKFLOW_FILE,
        task_file=TASK_FILE,
        p1_runtime_file=P1_RUNTIME_FILE,
        p2_runtime_file=P2_RUNTIME_FILE,
        p5_runtime_file=P5_RUNTIME_FILE,
        route_fidelity_file=ROUTE_FIDELITY_FILE,
        contract_semantics_file=CONTRACT_SEMANTICS_FILE,
        semantics_skip_allowlist_file=SEMANTICS_SKIP_ALLOWLIST_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b21_p5_nonvacuous_adjudication_enforcer_negative_control_forced_regression() -> None:
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--simulate-regression"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b21_p5_nonvacuous_adjudication_enforcer_negative_control_missing_required_context(
    tmp_path: Path,
) -> None:
    payload = json.loads(REQUIRED_CHECKS_FILE.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        ctx
        for ctx in payload.get("required_contexts", [])
        if ctx != "B2.1-P5 Non-Vacuous Proof Harness + Merge-Blocking Adjudication"
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
    assert "required_checks_missing_context:B2.1-P5 Non-Vacuous Proof Harness + Merge-Blocking Adjudication" in (
        proc.stdout + proc.stderr
    )


def test_b21_p5_nonvacuous_adjudication_enforcer_negative_control_missing_workflow_runtime_command(
    tmp_path: Path,
) -> None:
    workflow_regression = tmp_path / "ci.regression.yml"
    workflow_regression.write_text(
        CI_WORKFLOW_FILE.read_text(encoding="utf-8").replace(
            "pytest backend/tests/integration/test_b21_p5_nonvacuous_runtime.py -q",
            "pytest backend/tests/integration/test_removed_nonvacuous_runtime.py -q",
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
    assert "workflow_missing_token:pytest backend/tests/integration/test_b21_p5_nonvacuous_runtime.py -q" in (
        proc.stdout + proc.stderr
    )


def test_b21_p5_nonvacuous_adjudication_enforcer_negative_control_missing_ordering_token(
    tmp_path: Path,
) -> None:
    task_regression = tmp_path / "attribution.regression.py"
    task_regression.write_text(
        TASK_FILE.read_text(encoding="utf-8").replace(
            "ORDER BY e.occurred_at ASC, e.id ASC",
            "ORDER BY e.occurred_at ASC",
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(ENFORCER), "--task-file", str(task_regression)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "task_missing_token:ORDER BY e.occurred_at ASC, e.id ASC" in (
        proc.stdout + proc.stderr
    )


def test_b21_p5_nonvacuous_adjudication_enforcer_negative_control_channels_bundle_allowlisted(
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(SEMANTICS_SKIP_ALLOWLIST_FILE.read_text(encoding="utf-8")) or {}
    payload.setdefault("bundles", {})["attribution.bundled.yaml"] = "regression fixture"
    mutated = tmp_path / "semantics_skip_allowlist.regression.yaml"
    mutated.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--semantics-skip-allowlist-file",
            str(mutated),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "semantics_skip_allowlist_forbidden_bundle:attribution.bundled.yaml" in (
        proc.stdout + proc.stderr
    )

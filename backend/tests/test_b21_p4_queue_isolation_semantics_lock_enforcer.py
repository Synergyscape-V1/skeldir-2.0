from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.enforce_b21_p4_queue_isolation_semantics_lock import run_enforcement


ENFORCER = (
    REPO_ROOT / "scripts" / "ci" / "enforce_b21_p4_queue_isolation_semantics_lock.py"
)
QUEUE_FILE = REPO_ROOT / "backend" / "app" / "core" / "queues.py"
CELERY_FILE = REPO_ROOT / "backend" / "app" / "celery_app.py"
PROCFILE = REPO_ROOT / "Procfile"
CONTAINER_STACK_FILE = REPO_ROOT / "".join(("dock", "er", "-compose.e2e.yml"))
BENCHMARK_FILE = (
    REPO_ROOT / "scripts" / "benchmarks" / "b21_p4_queue_isolation_benchmark.py"
)
BENCHMARK_ADJUDICATOR_FILE = (
    REPO_ROOT / "scripts" / "ci" / "enforce_b21_p4_benchmark_adjudication.py"
)
CI_WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS_FILE = REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"


def test_b21_p4_queue_isolation_semantics_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        queue_file=QUEUE_FILE,
        celery_file=CELERY_FILE,
        procfile=PROCFILE,
        container_stack_file=CONTAINER_STACK_FILE,
        benchmark_file=BENCHMARK_FILE,
        benchmark_adjudicator_file=BENCHMARK_ADJUDICATOR_FILE,
        ci_workflow_file=CI_WORKFLOW_FILE,
        required_checks_file=REQUIRED_CHECKS_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b21_p4_queue_isolation_semantics_lock_enforcer_negative_control_forced_regression() -> (
    None
):
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


def test_b21_p4_queue_isolation_semantics_lock_enforcer_negative_control_missing_bayesian_route(
    tmp_path: Path,
) -> None:
    celery_regression = tmp_path / "celery_app.regression.py"
    celery_regression.write_text(
        CELERY_FILE.read_text(encoding="utf-8").replace(
            "'app.tasks.bayesian.*': {'queue': QUEUE_BAYESIAN, 'routing_key': f'{QUEUE_BAYESIAN}.task'}",
            "'app.tasks.bayesian.*': {'queue': QUEUE_ATTRIBUTION, 'routing_key': f'{QUEUE_ATTRIBUTION}.task'}",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--celery-file",
            str(celery_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert (
        "celery_file_missing_token:'app.tasks.bayesian.*': {'queue': QUEUE_BAYESIAN, 'routing_key': f'{QUEUE_BAYESIAN}.task'}"
        in combined
    )


def test_b21_p4_queue_isolation_semantics_lock_enforcer_negative_control_missing_ci_workflow_hook(
    tmp_path: Path,
) -> None:
    workflow_regression = tmp_path / "ci.regression.yml"
    workflow_regression.write_text(
        CI_WORKFLOW_FILE.read_text(encoding="utf-8").replace(
            "Run B2.1-P4 isolated queue benchmark (real contention)",
            "Run B2.1-P4 isolated queue benchmark removed",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--ci-workflow-file",
            str(workflow_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert (
        "ci_workflow_missing_token:Run B2.1-P4 isolated queue benchmark (real contention)"
        in combined
    )


def test_b21_p4_queue_isolation_semantics_lock_enforcer_negative_control_missing_contract_gate_need(
    tmp_path: Path,
) -> None:
    workflow_regression = tmp_path / "ci.needs.regression.yml"
    workflow_regression.write_text(
        CI_WORKFLOW_FILE.read_text(encoding="utf-8").replace(
            "b21-p4-queue-isolation-performance-lock",
            "b21-p4-queue-isolation-performance-lock-regressed",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--ci-workflow-file",
            str(workflow_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert (
        "ci_workflow_missing_contract_gate_need:b21-p4-queue-isolation-performance-lock"
        in combined
    )


def test_b21_p4_queue_isolation_semantics_lock_enforcer_negative_control_missing_required_context(
    tmp_path: Path,
) -> None:
    checks_regression = tmp_path / "required_checks.regression.json"
    checks_regression.write_text(
        REQUIRED_CHECKS_FILE.read_text(encoding="utf-8").replace(
            '"B2.1-P4 Queue Isolation + Performance Semantics Lock",\n',
            "",
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--required-checks-file",
            str(checks_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "required_checks_missing_b21_p4_context" in combined

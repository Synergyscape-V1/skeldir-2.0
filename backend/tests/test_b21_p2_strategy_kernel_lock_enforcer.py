from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.ci.enforce_b21_p2_strategy_kernel_lock import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p2_strategy_kernel_lock.py"
TASK_FILE = REPO_ROOT / "backend" / "app" / "tasks" / "attribution.py"
STRATEGY_FILE = REPO_ROOT / "backend" / "app" / "attribution" / "strategy_kernel.py"
RUNTIME_FILE = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p2_strategy_runtime.py"
UNIT_FILE = REPO_ROOT / "backend" / "tests" / "test_b21_p2_strategy_kernel.py"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS_FILE = REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"


def test_b21_p2_strategy_kernel_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        task_file=TASK_FILE,
        strategy_file=STRATEGY_FILE,
        runtime_proof_file=RUNTIME_FILE,
        unit_proof_file=UNIT_FILE,
        workflow_file=WORKFLOW_FILE,
        required_checks_file=REQUIRED_CHECKS_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b21_p2_strategy_kernel_lock_enforcer_negative_control_forced_regression() -> None:
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


def test_b21_p2_strategy_kernel_lock_enforcer_negative_control_missing_strategy_surface(
    tmp_path: Path,
) -> None:
    strategy_regression = tmp_path / "strategy.regression.py"
    strategy_regression.write_text(
        STRATEGY_FILE.read_text(encoding="utf-8").replace(
            "def strategy_time_decay(",
            "def strategy_time_decay_removed(",
            1,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--strategy-file",
            str(strategy_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert "strategy_missing_token:strategy_time_decay(" in combined


def test_b21_p2_strategy_kernel_lock_enforcer_negative_control_inclusive_session_end(
    tmp_path: Path,
) -> None:
    task_regression = tmp_path / "task.regression.py"
    task_regression.write_text(
        TASK_FILE.read_text(encoding="utf-8").replace(
            "AND e.occurred_at < sa.expires_at",
            "AND e.occurred_at <= sa.expires_at",
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
    assert "task_missing_token:AND e.occurred_at < sa.expires_at" in combined


def test_b21_p2_strategy_kernel_lock_enforcer_negative_control_missing_runtime_test(
    tmp_path: Path,
) -> None:
    runtime_regression = tmp_path / "runtime.regression.py"
    runtime_regression.write_text(
        RUNTIME_FILE.read_text(encoding="utf-8").replace(
            "test_b21_p2_runtime_null_touchpoint_conversions_get_direct_full_mass",
            "test_b21_p2_runtime_null_touchpoint_removed",
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ENFORCER),
            "--runtime-proof-file",
            str(runtime_regression),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = f"{proc.stdout}\n{proc.stderr}"
    assert (
        "runtime_proof_missing_token:test_b21_p2_runtime_null_touchpoint_conversions_get_direct_full_mass"
        in combined
    )


def test_b21_p2_strategy_kernel_lock_enforcer_negative_control_missing_workflow_hook(
    tmp_path: Path,
) -> None:
    workflow_regression = tmp_path / "ci.regression.yml"
    workflow_regression.write_text(
        WORKFLOW_FILE.read_text(encoding="utf-8").replace(
            "Enforce B2.1-P2 strategy kernel lock",
            "Enforce B2.1-P2 strategy lock removed",
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
    assert "workflow_missing_token:Enforce B2.1-P2 strategy kernel lock" in combined


def test_b21_p2_strategy_kernel_lock_enforcer_negative_control_missing_required_context(
    tmp_path: Path,
) -> None:
    checks_regression = tmp_path / "required_checks.regression.json"
    checks_regression.write_text(
        REQUIRED_CHECKS_FILE.read_text(encoding="utf-8").replace(
            '"B2.1-P2 Strategy Kernel + Session Boundary Proofs",\n',
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
    assert "required_checks_missing_b21_p2_context" in combined

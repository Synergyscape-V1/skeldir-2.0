from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.ci.enforce_b21_p1_semantic_replay_lock import run_enforcement


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = REPO_ROOT / "scripts" / "ci" / "enforce_b21_p1_semantic_replay_lock.py"
TASK_FILE = REPO_ROOT / "backend" / "app" / "tasks" / "attribution.py"
SEMANTICS_FILE = REPO_ROOT / "backend" / "app" / "attribution" / "semantics.py"
RUNTIME_FILE = REPO_ROOT / "backend" / "tests" / "integration" / "test_b21_p1_semantic_replay_runtime.py"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS_FILE = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b03_phase2_required_status_checks.main.json"
)


def test_b21_p1_semantic_replay_lock_enforcer_passes_repo_state() -> None:
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        task_file=TASK_FILE,
        semantics_file=SEMANTICS_FILE,
        runtime_proof_file=RUNTIME_FILE,
        workflow_file=WORKFLOW_FILE,
        required_checks_file=REQUIRED_CHECKS_FILE,
    )
    assert status == 0, f"unexpected enforcement violations: {violations}"


def test_b21_p1_semantic_replay_lock_enforcer_negative_control_forced_regression() -> None:
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


def test_b21_p1_semantic_replay_lock_enforcer_negative_control_wall_clock_regression(
    tmp_path: Path,
) -> None:
    task_regression = tmp_path / "attribution.regression.py"
    task_regression.write_text(
        TASK_FILE.read_text(encoding="utf-8").replace(
            "sa.issued_at < :replay_window_end",
            "sa.expires_at > :authority_now",
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
    assert "task_missing_token:sa.issued_at < :replay_window_end" in combined


def test_b21_p1_semantic_replay_lock_enforcer_negative_control_missing_required_context(
    tmp_path: Path,
) -> None:
    checks_regression = tmp_path / "required-checks.regression.json"
    checks_regression.write_text(
        REQUIRED_CHECKS_FILE.read_text(encoding="utf-8").replace(
            '"B2.1-P1 Semantic Replay Lock",\n',
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
    assert "required_checks_missing_b21_p1_context" in combined


def test_b21_p1_semantic_replay_lock_enforcer_negative_control_missing_runtime_test_token(
    tmp_path: Path,
) -> None:
    runtime_regression = tmp_path / "runtime.regression.py"
    runtime_regression.write_text(
        RUNTIME_FILE.read_text(encoding="utf-8").replace(
            "test_b21_p1_runtime_historical_replay_uses_persisted_session_facts_not_wall_clock",
            "test_b21_p1_runtime_historical_replay_regressed",
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
    assert "runtime_proof_missing_token:test_b21_p1_runtime_historical_replay_uses_persisted_session_facts_not_wall_clock" in combined

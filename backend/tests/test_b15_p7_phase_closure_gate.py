"""B1.5-P7 phase closure gate tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "b15_p7_phase_closure_gate.py"


def _run_gate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _write_status(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_b15_p7_phase_gate_pending_passes_technical_mode(tmp_path: Path) -> None:
    status_file = tmp_path / "status.pending.json"
    _write_status(
        status_file,
        {
            "phase": "B1.5-P7",
            "study_status": "pending_human_execution",
            "participants_completed": 0,
            "participants_target": 10,
            "understood_async_review_count": 0,
            "result_claim_present": False,
            "full_phase_closure_claim_present": False,
        },
    )
    result = _run_gate("--mode", "technical", "--status-file", str(status_file))
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p7_phase_gate_pending_blocks_full_phase_mode(tmp_path: Path) -> None:
    status_file = tmp_path / "status.pending.json"
    _write_status(
        status_file,
        {
            "phase": "B1.5-P7",
            "study_status": "pending_human_execution",
            "participants_completed": 0,
            "participants_target": 10,
            "understood_async_review_count": 0,
            "result_claim_present": False,
            "full_phase_closure_claim_present": False,
        },
    )
    result = _run_gate("--mode", "full-phase", "--status-file", str(status_file))
    assert result.returncode != 0
    assert "deploy_blocked_study_status:pending_human_execution" in (
        result.stdout + result.stderr
    )


def test_b15_p7_phase_gate_validated_passes_full_phase_mode(tmp_path: Path) -> None:
    status_file = tmp_path / "status.validated.json"
    _write_status(
        status_file,
        {
            "phase": "B1.5-P7",
            "study_status": "validated_by_humans",
            "participants_completed": 10,
            "participants_target": 10,
            "understood_async_review_count": 8,
            "result_claim_present": True,
            "full_phase_closure_claim_present": True,
        },
    )
    result = _run_gate("--mode", "full-phase", "--status-file", str(status_file))
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout

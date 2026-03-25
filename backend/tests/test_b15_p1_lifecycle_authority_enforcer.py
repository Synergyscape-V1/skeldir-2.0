"""B1.5-P1 lifecycle authority enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b15_p1_lifecycle_authority.py"


def _contract_path() -> Path:
    return (
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b15_p1_lifecycle_authority.main.json"
    )


def test_b15_p1_enforcer_passes_repo_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path())],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p1_enforcer_negative_control_synthetic_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--simulate-regression"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b15_p1_enforcer_negative_control_worker_direct_terminalization(tmp_path: Path) -> None:
    original_workers = (
        _repo_root() / "backend" / "app" / "workers" / "llm.py"
    ).read_text(encoding="utf-8")
    mutated_workers = tmp_path / "llm.regression.py"
    mutated_workers.write_text(
        original_workers
        + "\n\n"
        + "def _synthetic_regression() -> None:\n"
        + "    status = 'completed'\n"
        + "    _ = status\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--workers-file",
            str(mutated_workers),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "forbidden_worker_terminalization" in (result.stdout + result.stderr)


def test_b15_p1_enforcer_negative_control_missing_canonical_state(tmp_path: Path) -> None:
    contract = json.loads(_contract_path().read_text(encoding="utf-8"))
    contract["canonical_lifecycle_states"] = [
        value
        for value in contract.get("canonical_lifecycle_states", [])
        if value != "ready_for_review"
    ]
    mutated_contract = tmp_path / "b15_p1.contract.regression.json"
    mutated_contract.write_text(json.dumps(contract, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--contract-file",
            str(mutated_contract),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "contract_canonical_lifecycle_mismatch" in (result.stdout + result.stderr)


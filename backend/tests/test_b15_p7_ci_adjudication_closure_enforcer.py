"""B1.5-P7 closure enforcer tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return (
        _repo_root()
        / "scripts"
        / "ci"
        / "enforce_b15_p7_ci_adjudication_closure.py"
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _contract_file() -> Path:
    return (
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b15_p7_ci_adjudication_closure.main.json"
    )


def test_b15_p7_enforcer_passes_repo_baseline() -> None:
    result = _run_enforcer()
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p7_enforcer_negative_control_synthetic_regression() -> None:
    result = _run_enforcer("--simulate-regression")
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b15_p7_enforcer_negative_control_pending_study_cannot_claim_success(
    tmp_path: Path,
) -> None:
    contract = _load_json(_contract_file())
    status_file = tmp_path / "status.regression.json"
    status_file.write_text(
        json.dumps(
            {
                "phase": "B1.5-P7",
                "study_status": "pending_human_execution",
                "participants_completed": 0,
                "participants_target": 10,
                "result_claim_present": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    mental = contract["mental_model_study"]
    original_status = str(mental["status_file"])
    mental["status_file"] = str(status_file)
    required_files = [str(item) for item in mental["required_files"]]
    mental["required_files"] = [
        str(status_file) if item == original_status else item for item in required_files
    ]

    contract_file = tmp_path / "contract.json"
    _write_json(contract_file, contract)

    result = _run_enforcer("--contract-file", str(contract_file))
    assert result.returncode != 0
    assert "mental_model_pending_claims_success_without_human_execution" in (
        result.stdout + result.stderr
    )


def test_b15_p7_enforcer_negative_control_p6_active_override_blocks_closure(
    tmp_path: Path,
) -> None:
    contract = _load_json(_contract_file())
    overrides = _load_json(
        _repo_root()
        / "contracts-internal"
        / "governance"
        / "b15_p6_escalation_overrides.main.json"
    )
    overrides["active_overrides"] = [
        {
            "override_id": "OVERRIDE-B15-P7-TEST",
            "status": "active",
            "ticket": "B15-P7-TEST",
            "approved_by": ["test"],
            "expires_on": "2099-12-31",
            "decision_surface_globs": ["frontend/src/budget/**"],
            "allowed_violation_ids": ["transport.websocket.new_expression"],
            "justification": "test",
        }
    ]

    overrides_file = tmp_path / "overrides.regression.json"
    _write_json(overrides_file, overrides)
    contract["p6_dependency"]["overrides_file"] = str(overrides_file)

    contract_file = tmp_path / "contract.json"
    _write_json(contract_file, contract)

    result = _run_enforcer("--contract-file", str(contract_file))
    assert result.returncode != 0
    assert "p6_dependency_active_overrides_present" in (result.stdout + result.stderr)


def test_b15_p7_enforcer_negative_control_ci_job_must_include_required_commands(
    tmp_path: Path,
) -> None:
    ci_file = _repo_root() / ".github" / "workflows" / "ci.yml"
    mutated_ci = tmp_path / "ci.regression.yml"
    text = ci_file.read_text(encoding="utf-8")
    mutated_ci.write_text(
        text.replace(
            "pytest backend/tests/test_b15_p7_ci_adjudication_closure.py -q",
            "echo 'regression: removed required p7 runtime proofs'",
            1,
        ),
        encoding="utf-8",
    )

    result = _run_enforcer("--ci-file", str(mutated_ci))
    assert result.returncode != 0
    assert (
        "ci_job_missing_command:pytest backend/tests/test_b15_p7_ci_adjudication_closure.py -q"
        in (result.stdout + result.stderr)
    )


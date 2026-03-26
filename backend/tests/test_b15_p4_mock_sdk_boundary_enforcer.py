"""B1.5-P4 mock/SDK typed-boundary enforcer tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b15_p4_mock_sdk_boundary.py"


def test_b15_p4_enforcer_passes_repo_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path())],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p4_enforcer_negative_control_synthetic_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--simulate-regression"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b15_p4_enforcer_negative_control_missing_budget_mock_startup(
    tmp_path: Path,
) -> None:
    original_start = (_repo_root() / "scripts" / "start-mocks.sh").read_text(
        encoding="utf-8"
    )
    mutated_start = tmp_path / "start-mocks.regression.sh"
    mutated_start.write_text(
        original_start.replace("llm-budget.bundled.yaml", "llm-budget-missing.bundled.yaml"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--start-mocks-file",
            str(mutated_start),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "start_mocks_missing_bundle:llm-budget.bundled.yaml" in (
        result.stdout + result.stderr
    )


def test_b15_p4_enforcer_negative_control_wrapper_stale_path(tmp_path: Path) -> None:
    original_budget_wrapper = (
        _repo_root() / "frontend" / "src" / "api" / "contracts" / "llmBudgetClient.ts"
    ).read_text(encoding="utf-8")
    mutated_budget_wrapper = tmp_path / "llmBudgetClient.regression.ts"
    mutated_budget_wrapper.write_text(
        original_budget_wrapper
        + "\n"
        + "const regressionPath = '/api/budget/optimization';\n"
        + "void regressionPath;\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--budget-wrapper-file",
            str(mutated_budget_wrapper),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "wrapper_contains_forbidden_marker:/api/budget/optimization" in (
        result.stdout + result.stderr
    )


def test_b15_p4_enforcer_negative_control_missing_flattening_probe(
    tmp_path: Path,
) -> None:
    original_negative_control = (
        _repo_root() / "frontend" / "src" / "contract-consumption-negative-control.ts"
    ).read_text(encoding="utf-8")
    mutated_negative_control = tmp_path / "contract-consumption-negative-control.regression.ts"
    mutated_negative_control.write_text(
        original_negative_control.replace("flattenedShouldFail", "flattenedBypass"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--contract-negative-control-file",
            str(mutated_negative_control),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "negative_control_missing_flattening_probe" in (
        result.stdout + result.stderr
    )

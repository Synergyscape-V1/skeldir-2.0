"""B1.5-P5 frontend control grammar enforcer tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return (
        _repo_root()
        / "scripts"
        / "ci"
        / "enforce_b15_p5_frontend_control_grammar.py"
    )


def test_b15_p5_enforcer_passes_repo_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path())],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b15_p5_enforcer_negative_control_synthetic_regression() -> None:
    result = subprocess.run(
        [sys.executable, str(_script_path()), "--simulate-regression"],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "synthetic_regression" in (result.stdout + result.stderr)


def test_b15_p5_enforcer_negative_control_review_gate_regression(tmp_path: Path) -> None:
    original_helper = (
        _repo_root() / "frontend" / "src" / "components" / "llm" / "controlPlane.ts"
    ).read_text(encoding="utf-8")
    mutated_helper = tmp_path / "controlPlane.regression.ts"
    mutated_helper.write_text(
        original_helper.replace("snapshot.reviewRequired", "snapshot.reviewOptional"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--lifecycle-helper-file",
            str(mutated_helper),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "review_gating_helper_missing_review_required_check" in (
        result.stdout + result.stderr
    )


def test_b15_p5_enforcer_negative_control_results_polling_regression(
    tmp_path: Path,
) -> None:
    original_budget_hook = (
        _repo_root()
        / "frontend"
        / "src"
        / "components"
        / "llm"
        / "useBudgetCentaurController.ts"
    ).read_text(encoding="utf-8")
    mutated_budget_hook = tmp_path / "useBudgetCentaurController.regression.ts"
    insertion = (
        "        const _regression = await client.getBudgetRecommendation(jobId, {\n"
        "        correlationId: createStableUuid(),\n"
        "        authorization,\n"
        "      });\n"
        "        void _regression;\n"
    )
    mutated_budget_hook.write_text(
        original_budget_hook.replace(
            "        await fetchStatus(jobId);\n",
            insertion + "        await fetchStatus(jobId);\n",
            1,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--budget-hook-file",
            str(mutated_budget_hook),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "budget_poll_block_calls_result_route" in (result.stdout + result.stderr)


def test_b15_p5_enforcer_negative_control_missing_idempotency_regression(
    tmp_path: Path,
) -> None:
    original_budget_hook = (
        _repo_root()
        / "frontend"
        / "src"
        / "components"
        / "llm"
        / "useBudgetCentaurController.ts"
    ).read_text(encoding="utf-8")
    mutated_budget_hook = tmp_path / "useBudgetCentaurController.idempotency.regression.ts"
    mutated_budget_hook.write_text(
        original_budget_hook.replace(
            "idempotencyKey: createStableUuid(),",
            "idempotencyKey: undefined as unknown as string,",
            1,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--budget-hook-file",
            str(mutated_budget_hook),
        ],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "budget_hook_missing_idempotency_key" in (result.stdout + result.stderr)

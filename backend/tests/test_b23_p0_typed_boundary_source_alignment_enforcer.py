from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENFORCER = (
    REPO_ROOT / "scripts" / "ci" / "enforce_b23_p0_typed_boundary_source_alignment.py"
)
INVESTIGATIONS_SPEC = REPO_ROOT / "api-contracts" / "openapi" / "v1" / "llm-investigations.yaml"
BUDGET_SPEC = REPO_ROOT / "api-contracts" / "openapi" / "v1" / "llm-budget.yaml"
GENERATED_INVESTIGATIONS_TYPES = (
    REPO_ROOT / "frontend" / "src" / "types" / "api" / "llm-investigations.ts"
)
GENERATED_BUDGET_TYPES = REPO_ROOT / "frontend" / "src" / "types" / "api" / "llm-budget.ts"
CONTRACT_GATE = REPO_ROOT / "frontend" / "src" / "contract-consumption-gate.ts"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENFORCER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_b23_p0_typed_boundary_source_alignment_enforcer_passes_repo_state() -> None:
    proc = _run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "result=PASS" in (proc.stdout + proc.stderr)


def test_b23_p0_typed_boundary_source_alignment_enforcer_negative_control_forced_regression() -> None:
    proc = _run("--simulate-regression")
    assert proc.returncode != 0
    assert "synthetic_regression=forced_failure_path" in (proc.stdout + proc.stderr)


def test_b23_p0_typed_boundary_source_alignment_enforcer_negative_control_missing_runtime_route(
    tmp_path: Path,
) -> None:
    mutated_budget_spec = tmp_path / "llm-budget.regression.yaml"
    mutated_budget_spec.write_text(
        BUDGET_SPEC.read_text(encoding="utf-8").replace(
            "/api/budget/optimize:",
            "/api/budget/optimize-shadow:",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--budget-spec-file", str(mutated_budget_spec))
    assert proc.returncode != 0
    assert "missing_runtime_route:POST:/api/budget/optimize-shadow:createBudgetOptimization" in (
        proc.stdout + proc.stderr
    )


def test_b23_p0_typed_boundary_source_alignment_enforcer_negative_control_missing_generated_operation(
    tmp_path: Path,
) -> None:
    mutated_budget_types = tmp_path / "llm-budget.regression.ts"
    mutated_budget_types.write_text(
        GENERATED_BUDGET_TYPES.read_text(encoding="utf-8").replace(
            "createBudgetOptimization",
            "submitBudgetPlan",
        ),
        encoding="utf-8",
    )

    proc = _run("--generated-budget-types-file", str(mutated_budget_types))
    assert proc.returncode != 0
    assert "missing_generated_operation:createBudgetOptimization" in (proc.stdout + proc.stderr)


def test_b23_p0_typed_boundary_source_alignment_enforcer_negative_control_missing_contract_gate_operation(
    tmp_path: Path,
) -> None:
    mutated_contract_gate = tmp_path / "contract-consumption-gate.regression.ts"
    mutated_contract_gate.write_text(
        CONTRACT_GATE.read_text(encoding="utf-8").replace(
            "createInvestigation",
            "submitInvestigation",
            1,
        ),
        encoding="utf-8",
    )

    proc = _run("--contract-gate-file", str(mutated_contract_gate))
    assert proc.returncode != 0
    assert "missing_contract_gate_operation:createInvestigation" in (proc.stdout + proc.stderr)

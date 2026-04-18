#!/usr/bin/env python3
"""B2.1-P2 strategy-kernel lock enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_FILE = "backend/app/tasks/attribution.py"
STRATEGY_FILE = "backend/app/attribution/strategy_kernel.py"
RUNTIME_PROOF_FILE = "backend/tests/integration/test_b21_p2_strategy_runtime.py"
UNIT_PROOF_FILE = "backend/tests/test_b21_p2_strategy_kernel.py"
WORKFLOW_FILE = ".github/workflows/ci.yml"
REQUIRED_CHECKS_FILE = "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
REQUIRED_CONTEXT = "B2.1-P2 Strategy Kernel + Session Boundary Proofs"


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def run_enforcement(
    *,
    repo_root: Path,
    task_file: Path,
    strategy_file: Path,
    runtime_proof_file: Path,
    unit_proof_file: Path,
    workflow_file: Path,
    required_checks_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        task_file,
        strategy_file,
        runtime_proof_file,
        unit_proof_file,
        workflow_file,
        required_checks_file,
    )
    for file_path in required_files:
        if not file_path.exists():
            violations.append(f"missing_required_file:{file_path}")
    if violations:
        return 1, violations

    task_text = _read_text(task_file)
    strategy_text = _read_text(strategy_file)
    runtime_text = _read_text(runtime_proof_file)
    unit_text = _read_text(unit_proof_file)
    workflow_text = _read_text(workflow_file)
    required_checks = _read_json(required_checks_file)

    required_strategy_tokens = (
        "FIRST_TOUCH_MODEL",
        "LAST_TOUCH_MODEL",
        "LINEAR_MODEL",
        "TIME_DECAY_MODEL",
        "_HALF_LIFE_SECONDS = Decimal(\"604800\")",
        "strategy_first_touch(",
        "strategy_last_touch(",
        "strategy_linear(",
        "strategy_time_decay(",
        "assert_ratio_conservation(",
        "build_channel_allocations_for_conversion(",
    )
    for token in required_strategy_tokens:
        if token not in strategy_text:
            violations.append(f"strategy_missing_token:{token}")

    required_task_tokens = (
        "_compute_allocations_strategy_kernel(",
        "_load_semantic_events_for_replay(",
        "_derive_conversion_contexts(",
        "AND e.occurred_at >= sa.issued_at",
        "AND e.occurred_at < sa.expires_at",
        "model_type: str = DETERMINISTIC_BASELINE_MODEL",
        "if canonical_model_type == DETERMINISTIC_BASELINE_MODEL:",
    )
    for token in required_task_tokens:
        if token not in task_text:
            violations.append(f"task_missing_token:{token}")

    forbidden_task_tokens = (
        "BETWEEN sa.issued_at AND sa.expires_at",
    )
    for token in forbidden_task_tokens:
        if token in task_text:
            violations.append(f"task_forbidden_token_present:{token}")

    required_runtime_tokens = (
        "test_b21_p2_runtime_four_strategies_are_separately_executable",
        "test_b21_p2_runtime_session_half_open_boundary_proofs",
        "test_b21_p2_runtime_null_touchpoint_conversions_get_direct_full_mass",
        "23:59:59 included",
        "24:00:00 excluded",
        "24:00:01 excluded",
    )
    for token in required_runtime_tokens:
        if token not in runtime_text:
            violations.append(f"runtime_proof_missing_token:{token}")

    required_unit_tokens = (
        "test_b21_p2_first_touch_and_last_touch_use_total_tie_break_order",
        "test_b21_p2_linear_and_time_decay_match_expected_math",
        "test_b21_p2_null_touchpoint_fallback_and_conservation",
        "test_b21_p2_known_bad_ratio_fixture_fails_conservation_guard",
    )
    for token in required_unit_tokens:
        if token not in unit_text:
            violations.append(f"unit_proof_missing_token:{token}")

    required_workflow_tokens = (
        "name: B2.1-P2 Strategy Kernel + Session Boundary Proofs",
        "Enforce B2.1-P2 strategy kernel lock",
        "Run B2.1-P2 strategy kernel lock negative controls",
        "Run B2.1-P2 strategy runtime proofs",
        "pytest backend/tests/integration/test_b21_p2_strategy_runtime.py -q",
        "pytest backend/tests/test_b21_p2_strategy_kernel.py -q",
    )
    for token in required_workflow_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_token:{token}")

    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
    elif REQUIRED_CONTEXT not in required_contexts:
        violations.append("required_checks_missing_b21_p2_context")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.1-P2 strategy kernel mathematical lock."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--task-file", default=TASK_FILE)
    parser.add_argument("--strategy-file", default=STRATEGY_FILE)
    parser.add_argument("--runtime-proof-file", default=RUNTIME_PROOF_FILE)
    parser.add_argument("--unit-proof-file", default=UNIT_PROOF_FILE)
    parser.add_argument("--workflow-file", default=WORKFLOW_FILE)
    parser.add_argument("--required-checks-file", default=REQUIRED_CHECKS_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b21_p2_strategy_kernel_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        task_file=_resolve(repo_root, args.task_file),
        strategy_file=_resolve(repo_root, args.strategy_file),
        runtime_proof_file=_resolve(repo_root, args.runtime_proof_file),
        unit_proof_file=_resolve(repo_root, args.unit_proof_file),
        workflow_file=_resolve(repo_root, args.workflow_file),
        required_checks_file=_resolve(repo_root, args.required_checks_file),
    )
    lines = ["b21_p2_strategy_kernel_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=strategy_surfaces_math_boundaries_conservation_locked")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

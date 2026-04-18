#!/usr/bin/env python3
"""B2.1-P5 non-vacuous proof harness + merge-blocking adjudication enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CHECKS_FILE = "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
CI_WORKFLOW_FILE = ".github/workflows/ci.yml"
TASK_FILE = "backend/app/tasks/attribution.py"
P1_RUNTIME_FILE = "backend/tests/integration/test_b21_p1_semantic_replay_runtime.py"
P2_RUNTIME_FILE = "backend/tests/integration/test_b21_p2_strategy_runtime.py"
P5_RUNTIME_FILE = "backend/tests/integration/test_b21_p5_nonvacuous_runtime.py"
ROUTE_FIDELITY_FILE = "tests/contract/test_route_fidelity.py"
CONTRACT_SEMANTICS_FILE = "tests/contract/test_contract_semantics.py"
SEMANTICS_SKIP_ALLOWLIST_FILE = "tests/contract/semantics_skip_allowlist.yaml"

REQUIRED_CONTEXT_P2 = "B2.1-P2 Strategy Kernel + Session Boundary Proofs"
REQUIRED_CONTEXT_P4 = "B2.1-P4 Queue Isolation + Performance Semantics Lock"
REQUIRED_CONTEXT_P5 = "B2.1-P5 Non-Vacuous Proof Harness + Merge-Blocking Adjudication"


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


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(path)) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML payload must be an object: {path}")
    return payload


def run_enforcement(
    *,
    repo_root: Path,
    required_checks_file: Path,
    ci_workflow_file: Path,
    task_file: Path,
    p1_runtime_file: Path,
    p2_runtime_file: Path,
    p5_runtime_file: Path,
    route_fidelity_file: Path,
    contract_semantics_file: Path,
    semantics_skip_allowlist_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        required_checks_file,
        ci_workflow_file,
        task_file,
        p1_runtime_file,
        p2_runtime_file,
        p5_runtime_file,
        route_fidelity_file,
        contract_semantics_file,
        semantics_skip_allowlist_file,
    )
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        return 1, [f"missing_required_file:{path}" for path in missing_files]

    required_checks = _read_json(required_checks_file)
    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
        required_contexts = []
    for context in (REQUIRED_CONTEXT_P2, REQUIRED_CONTEXT_P4, REQUIRED_CONTEXT_P5):
        if context not in required_contexts:
            violations.append(f"required_checks_missing_context:{context}")

    future_contexts = required_checks.get("future_required_context_declarations", [])
    if isinstance(future_contexts, list):
        future_names = {
            item.get("name")
            for item in future_contexts
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        for context in (REQUIRED_CONTEXT_P2, REQUIRED_CONTEXT_P4, REQUIRED_CONTEXT_P5):
            if context in future_names:
                violations.append(f"required_checks_context_must_not_be_future_declared:{context}")

    workflow_text = _read_text(ci_workflow_file)
    required_workflow_tokens = (
        f"name: {REQUIRED_CONTEXT_P2}",
        f"name: {REQUIRED_CONTEXT_P4}",
        f"name: {REQUIRED_CONTEXT_P5}",
        "pytest backend/tests/integration/test_b21_p1_semantic_replay_runtime.py::test_b21_p1_runtime_replay_identity_freezes_late_arriving_historical_events -q",
        "pytest backend/tests/integration/test_b21_p2_strategy_runtime.py::test_b21_p2_runtime_session_half_open_boundary_proofs -q",
        "pytest backend/tests/integration/test_b21_p5_nonvacuous_runtime.py -q",
        "pytest tests/contract/test_route_fidelity.py::test_b21_channels_route_mounted_and_runtime_openapi_converged -q",
        "pytest tests/contract/test_contract_semantics.py::test_contract_semantics_skip_prefixes_do_not_mask_core_attribution_surface -q",
        "python scripts/ci/enforce_b21_p5_nonvacuous_adjudication.py",
    )
    for token in required_workflow_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_token:{token}")

    task_text = _read_text(task_file)
    required_task_tokens = (
        "ORDER BY e.occurred_at ASC, e.id ASC",
        "e.created_at <= :replay_event_created_ceiling",
    )
    for token in required_task_tokens:
        if token not in task_text:
            violations.append(f"task_missing_token:{token}")

    p1_runtime_text = _read_text(p1_runtime_file)
    if (
        "test_b21_p1_runtime_replay_identity_freezes_late_arriving_historical_events"
        not in p1_runtime_text
    ):
        violations.append("p1_runtime_missing_replay_freeze_test")

    p2_runtime_text = _read_text(p2_runtime_file)
    required_p2_runtime_tokens = (
        "test_b21_p2_runtime_session_half_open_boundary_proofs",
        "23:59:59 included",
        "24:00:00 excluded",
        "24:00:01 excluded",
    )
    for token in required_p2_runtime_tokens:
        if token not in p2_runtime_text:
            violations.append(f"p2_runtime_missing_token:{token}")

    p5_runtime_text = _read_text(p5_runtime_file)
    required_p5_runtime_tokens = (
        "test_b21_p5_equal_timestamp_ties_replay_determinism_is_stable_across_time_separated_reruns",
        "test_b21_p5_precision_and_fractional_conservation_hold_db_to_api_roundtrip",
        "ratio_mass == Decimal(\"1.00000\")",
    )
    for token in required_p5_runtime_tokens:
        if token not in p5_runtime_text:
            violations.append(f"p5_runtime_missing_token:{token}")

    route_fidelity_text = _read_text(route_fidelity_file)
    required_route_fidelity_tokens = (
        "test_b21_channels_route_mounted_and_runtime_openapi_converged",
        "allocation_ratio_schema.get(\"pattern\") == \"^(0|1)\\\\.\\\\d{5}$\"",
        "attribution_weight_schema.get(\"pattern\") == \"^(0|1)\\\\.\\\\d{5}$\"",
    )
    for token in required_route_fidelity_tokens:
        if token not in route_fidelity_text:
            violations.append(f"route_fidelity_missing_token:{token}")

    contract_semantics_text = _read_text(contract_semantics_file)
    required_contract_semantics_tokens = (
        "test_contract_semantics_skip_prefixes_do_not_mask_core_attribution_surface",
        "/api/attribution/channels",
    )
    for token in required_contract_semantics_tokens:
        if token not in contract_semantics_text:
            violations.append(f"contract_semantics_missing_token:{token}")

    skip_allowlist_doc = _read_yaml(semantics_skip_allowlist_file)
    bundles = skip_allowlist_doc.get("bundles", {})
    if not isinstance(bundles, dict):
        violations.append("semantics_skip_allowlist_bundles_invalid")
    elif "attribution.bundled.yaml" in bundles:
        violations.append("semantics_skip_allowlist_forbidden_bundle:attribution.bundled.yaml")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.1-P5 non-vacuous proof harness + merge-blocking adjudication."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--required-checks-file", default=REQUIRED_CHECKS_FILE)
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument("--task-file", default=TASK_FILE)
    parser.add_argument("--p1-runtime-file", default=P1_RUNTIME_FILE)
    parser.add_argument("--p2-runtime-file", default=P2_RUNTIME_FILE)
    parser.add_argument("--p5-runtime-file", default=P5_RUNTIME_FILE)
    parser.add_argument("--route-fidelity-file", default=ROUTE_FIDELITY_FILE)
    parser.add_argument("--contract-semantics-file", default=CONTRACT_SEMANTICS_FILE)
    parser.add_argument("--semantics-skip-allowlist-file", default=SEMANTICS_SKIP_ALLOWLIST_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b21_p5_nonvacuous_adjudication_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        required_checks_file=_resolve(repo_root, args.required_checks_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        task_file=_resolve(repo_root, args.task_file),
        p1_runtime_file=_resolve(repo_root, args.p1_runtime_file),
        p2_runtime_file=_resolve(repo_root, args.p2_runtime_file),
        p5_runtime_file=_resolve(repo_root, args.p5_runtime_file),
        route_fidelity_file=_resolve(repo_root, args.route_fidelity_file),
        contract_semantics_file=_resolve(repo_root, args.contract_semantics_file),
        semantics_skip_allowlist_file=_resolve(repo_root, args.semantics_skip_allowlist_file),
    )

    lines = ["b21_p5_nonvacuous_adjudication_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=replay_session_channels_queue_precision_required_checks_merge_blocking"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

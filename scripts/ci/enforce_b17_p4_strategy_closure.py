#!/usr/bin/env python3
"""B1.7-P4 strategy-closure structural enforcer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_PATH = "/api/attribution/explain/{entity_type}/{entity_id}"


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def run_enforcement(
    *,
    source_contract_file: Path,
    bundled_contract_file: Path,
    ci_workflow_file: Path,
    benchmark_workflow_file: Path,
    runtime_proof_file: Path,
    enforcer_test_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        source_contract_file,
        bundled_contract_file,
        ci_workflow_file,
        benchmark_workflow_file,
        runtime_proof_file,
        enforcer_test_file,
    )
    for required in required_files:
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    source = _read_yaml(source_contract_file)
    bundled = _read_yaml(bundled_contract_file)

    source_op = _as_dict(_as_dict(_as_dict(source.get("paths")).get(CANONICAL_PATH)).get("get"))
    bundled_op = _as_dict(
        _as_dict(_as_dict(bundled.get("paths")).get(CANONICAL_PATH)).get("get")
    )

    for label, operation in (("source", source_op), ("bundled", bundled_op)):
        lock = _as_dict(operation.get("x-skeldir-b17-p4"))
        if not lock:
            violations.append(f"{label}_missing_b17_p4_lock")
            continue
        if (
            lock.get("implementation_status")
            != "cold_path_strategy_closed_with_bounded_event_prewarm"
        ):
            violations.append(f"{label}_p4_implementation_status_mismatch")

        strategy = _as_dict(lock.get("cold_path_strategy"))
        if strategy.get("decision") != "prewarm_required":
            violations.append(f"{label}_cold_path_strategy_decision_mismatch")
        if strategy.get("warm_path_only_proof_forbidden") is not True:
            violations.append(f"{label}_warm_path_only_proof_not_forbidden")
        if strategy.get("ordinary_pr_ci_live_vendor_load_forbidden") is not True:
            violations.append(f"{label}_ordinary_pr_ci_live_vendor_load_not_forbidden")

        execution_metadata = _as_dict(lock.get("execution_metadata"))
        required_fields = set(_as_list(execution_metadata.get("schema_required_fields")))
        for field in ("execution_path_state", "cold_path_strategy", "prewarm_state"):
            if field not in required_fields:
                violations.append(f"{label}_missing_schema_required_field:{field}")
        path_classes = set(_as_list(execution_metadata.get("path_classes")))
        for state in (
            "warm_cache_hit",
            "cold_path_generated",
            "stale_rejected_provider_blocked",
            "prewarm_assisted_cache_hit",
        ):
            if state not in path_classes:
                violations.append(f"{label}_missing_execution_path_class:{state}")

        prewarm_policy = _as_dict(lock.get("prewarm_policy"))
        if prewarm_policy.get("trigger_mode") != "deterministic_truth_change_event":
            violations.append(f"{label}_prewarm_trigger_mode_mismatch")
        if prewarm_policy.get("default_cron_forbidden") is not True:
            violations.append(f"{label}_default_cron_not_forbidden")

    schemas = _as_dict(_as_dict(bundled.get("components")).get("schemas"))
    explanation_schema = _as_dict(schemas.get("AttributionNonAuthoritativeExplanation"))
    explanation_required = set(_as_list(explanation_schema.get("required")))
    for field in ("execution_path_state", "cold_path_strategy", "prewarm_state"):
        if field not in explanation_required:
            violations.append(f"schema_missing_required_explanation_field:{field}")
    contract_versions = _as_list(
        _as_dict(_as_dict(explanation_schema.get("properties")).get("explanation_contract_version")).get("enum")
    )
    if "b1.7-p4" not in contract_versions:
        violations.append("schema_missing_b1_7_p4_contract_version")

    prewarm_schema = _as_dict(schemas.get("AttributionPrewarmState"))
    trigger_reason_enum = set(
        _as_list(_as_dict(_as_dict(prewarm_schema.get("properties")).get("trigger_reason")).get("enum"))
    )
    for reason in (
        "triggered",
        "already_prewarmed_for_watermark",
        "tenant_hourly_cap_reached",
        "stale_replay_path_suppressed",
    ):
        if reason not in trigger_reason_enum:
            violations.append(f"prewarm_schema_missing_trigger_reason:{reason}")

    ci_text = ci_workflow_file.read_text(encoding="utf-8", errors="replace")
    if "test_b17_p4_strategy_closure_runtime.py" not in ci_text:
        violations.append("ci_missing_b17_p4_runtime_proof_step")
    if "enforce_b17_p4_strategy_closure.py" not in ci_text:
        violations.append("ci_missing_b17_p4_enforcer_step")
    if "test_b17_p4_strategy_closure_enforcer.py" not in ci_text:
        violations.append("ci_missing_b17_p4_enforcer_negative_controls")

    benchmark_workflow = _read_yaml(benchmark_workflow_file)
    on_payload = benchmark_workflow.get("on")
    if on_payload is None and True in benchmark_workflow:
        on_payload = benchmark_workflow.get(True)
    triggers = _as_dict(on_payload)
    if "workflow_dispatch" not in triggers:
        violations.append("benchmark_workflow_missing_workflow_dispatch_trigger")
    if "schedule" not in triggers:
        violations.append("benchmark_workflow_missing_schedule_trigger")
    if "pull_request" in triggers:
        violations.append("benchmark_workflow_must_not_run_on_pull_request")
    benchmark_text = benchmark_workflow_file.read_text(encoding="utf-8", errors="replace")
    if "scripts/benchmarks/b17_p4_mixed_workload.py" not in benchmark_text:
        violations.append("benchmark_workflow_missing_mixed_workload_harness")

    runtime_proof_text = runtime_proof_file.read_text(encoding="utf-8", errors="replace")
    for token in (
        "prewarm_assisted_cache_hit",
        "stale_replay_path_suppressed",
        "test_b17_p4_prewarm_assisted_cache_hit_is_observable",
    ):
        if token not in runtime_proof_text:
            violations.append(f"runtime_proof_missing_token:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.7-P4 strategy-closure enforcer")
    parser.add_argument(
        "--source-contract-file",
        default="api-contracts/openapi/v1/attribution.yaml",
    )
    parser.add_argument(
        "--bundled-contract-file",
        default="api-contracts/dist/openapi/v1/attribution.bundled.yaml",
    )
    parser.add_argument("--ci-workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--benchmark-workflow-file",
        default=".github/workflows/b17-p4-mixed-workload-benchmark.yml",
    )
    parser.add_argument(
        "--runtime-proof-file",
        default="backend/tests/test_b17_p4_strategy_closure_runtime.py",
    )
    parser.add_argument(
        "--enforcer-test-file",
        default="backend/tests/test_b17_p4_strategy_closure_enforcer.py",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b17_p4_strategy_closure_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=execution_state_metadata_removed\n"
        )
        return 1

    status, violations = run_enforcement(
        source_contract_file=(REPO_ROOT / args.source_contract_file).resolve(),
        bundled_contract_file=(REPO_ROOT / args.bundled_contract_file).resolve(),
        ci_workflow_file=(REPO_ROOT / args.ci_workflow_file).resolve(),
        benchmark_workflow_file=(REPO_ROOT / args.benchmark_workflow_file).resolve(),
        runtime_proof_file=(REPO_ROOT / args.runtime_proof_file).resolve(),
        enforcer_test_file=(REPO_ROOT / args.enforcer_test_file).resolve(),
    )

    lines = ["b17_p4_strategy_closure_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=b17_p4_strategy_closure_invariants_satisfied")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

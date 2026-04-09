#!/usr/bin/env python3
"""B1.7-P6 adjudication-plane structural enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW_JOB_ID = "b17-explanation-runtime-adjudication"
CI_WORKFLOW_NAME = "B1.7 Explanation Runtime Adjudication"
BENCHMARK_REQUIRED_CONTEXT = "B1.7 P4 Mixed Workload Benchmark"


def _extract_job_block(ci_text: str, job_id: str) -> str:
    lines = ci_text.splitlines()
    capture = False
    captured: list[str] = []
    for line in lines:
        if line.startswith(f"  {job_id}:"):
            capture = True
        elif capture and line.startswith("  ") and not line.startswith("    "):
            break
        if capture:
            captured.append(line)
    return "\n".join(captured)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_enforcement(
    *,
    ci_workflow_file: Path,
    benchmark_workflow_file: Path,
    required_checks_contract_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    if not ci_workflow_file.exists():
        violations.append(f"missing_file:{ci_workflow_file}")
    if not benchmark_workflow_file.exists():
        violations.append(f"missing_file:{benchmark_workflow_file}")
    if not required_checks_contract_file.exists():
        violations.append(f"missing_file:{required_checks_contract_file}")
    if violations:
        return 1, violations

    ci_text = ci_workflow_file.read_text(encoding="utf-8", errors="replace")
    job_block = _extract_job_block(ci_text, CI_WORKFLOW_JOB_ID)
    if not job_block:
        violations.append("ci_missing_b17_required_job")
    else:
        if f"name: {CI_WORKFLOW_NAME}" not in job_block:
            violations.append("ci_missing_b17_required_job_name")
        for token in (
            "test_b17_p6_end_to_end_runtime.py",
            "scripts/benchmarks/b17_p4_mixed_workload.py",
        ):
            if token not in job_block:
                violations.append(f"ci_missing_required_token:{token}")

    benchmark_workflow = _load_yaml(benchmark_workflow_file)
    on_payload = benchmark_workflow.get("on")
    if on_payload is None and True in benchmark_workflow:
        on_payload = benchmark_workflow.get(True)
    triggers = on_payload if isinstance(on_payload, dict) else {}

    push = triggers.get("push", {}) if isinstance(triggers, dict) else {}
    branches = push.get("branches", []) if isinstance(push, dict) else []
    if "main" not in branches:
        violations.append("benchmark_missing_push_main_trigger")
    if "schedule" not in triggers:
        violations.append("benchmark_missing_schedule_trigger")
    if "workflow_dispatch" not in triggers:
        violations.append("benchmark_missing_workflow_dispatch_trigger")
    pull_request = triggers.get("pull_request", {}) if isinstance(triggers, dict) else {}
    pr_branches = pull_request.get("branches", []) if isinstance(pull_request, dict) else []
    if "main" not in pr_branches:
        violations.append("benchmark_missing_pull_request_main_trigger")

    benchmark_text = benchmark_workflow_file.read_text(encoding="utf-8", errors="replace")
    for token in (
        f"name: {BENCHMARK_REQUIRED_CONTEXT}",
        "baseline_no_prewarm.json",
        "prewarm_enabled.json",
        "scripts/ci/enforce_b17_p6_benchmark_adjudication.py",
        "b17_p6_benchmark_latency_model.main.json",
        "--max-requests-per-determinant",
        "--max-duplicate-request-ratio",
        "--min-unique-determinant-ratio",
        "--min-total-requests",
        "--min-cold-path-samples",
        "Upload benchmark artifacts",
    ):
        if token not in benchmark_text:
            violations.append(f"benchmark_missing_required_token:{token}")

    required_checks = _load_json(required_checks_contract_file)
    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
    elif BENCHMARK_REQUIRED_CONTEXT not in required_contexts:
        violations.append("required_checks_missing_b17_p4_benchmark_context")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.7-P6 adjudication-plane structural enforcer")
    parser.add_argument("--ci-workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--benchmark-workflow-file",
        default=".github/workflows/b17-p4-mixed-workload-benchmark.yml",
    )
    parser.add_argument(
        "--required-checks-contract-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b17_p6_adjudication_plane_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=required_p6_adjudication_removed\n"
        )
        return 1

    status, violations = run_enforcement(
        ci_workflow_file=(REPO_ROOT / args.ci_workflow_file).resolve(),
        benchmark_workflow_file=(REPO_ROOT / args.benchmark_workflow_file).resolve(),
        required_checks_contract_file=(REPO_ROOT / args.required_checks_contract_file).resolve(),
    )
    lines = ["b17_p6_adjudication_plane_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=b17_p6_pr_and_main_adjudication_plane_bound")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

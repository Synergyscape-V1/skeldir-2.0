#!/usr/bin/env python3
"""Validate M3 CI governance registry, topology, and structural reduction."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "docs/ci/enforcer_registry.yaml"
SUBSUMPTION_PATH = ROOT / "docs/ci/gate_subsumption_matrix.yaml"
TOPOLOGY_PATH = ROOT / "docs/ci/ci_topology_map.md"
COMPLETION_PATH = ROOT / "docs/maintainability/m3_completion_record.md"
REQUIRED_CONTEXTS_PATH = (
    ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)
BASELINE_CI_LINES = 6080
BASELINE_CI_DB_SETUP_BLOCKS = 11
BASELINE_CI_ENFORCER_INVOCATIONS = 97


REQUIRED_REGISTRY_FIELDS = {
    "id",
    "path",
    "status",
    "owning_phase",
    "protected_invariant",
    "command",
    "workflow_references",
    "local_reproduction_command",
    "expected_failure_meaning",
    "first_diagnostic_command",
    "depends_on_db",
    "depends_on_celery",
    "depends_on_pooler",
    "default_execution",
    "execution_cohort",
    "ci_visibility",
    "replacement",
    "deprecation_reason",
    "subsumed_by",
    "registry_action",
}

REQUIRED_SUBSUMPTION_FIELDS = {
    "gate_id",
    "workflow",
    "job",
    "script",
    "owning_phase",
    "protected_invariant",
    "current_status",
    "default_execution",
    "candidate_action",
    "subsuming_gate",
    "subsumption_evidence",
    "negative_control_preserved_by",
    "local_reproduction_command",
    "risk_if_removed",
    "decision",
}


@dataclass
class Validation:
    failures: list[str] = field(default_factory=list)

    def require(self, condition: bool, failure: str) -> None:
        if not condition:
            self.failures.append(failure)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_yaml(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(read(path))
    if not isinstance(data, list):
        raise SystemExit(f"{path} must contain a YAML list")
    return data


def workflow_texts() -> dict[Path, str]:
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
    workflows += sorted((ROOT / ".github/workflows").glob("*.yaml"))
    return {path: read(path) for path in workflows}


def script_paths() -> set[str]:
    return {
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "scripts/ci").glob("*.py"))
    }


def workflow_script_calls() -> set[str]:
    calls: set[str] = set()
    for text in workflow_texts().values():
        calls.update(re.findall(r"scripts/ci/[A-Za-z0-9_./-]+\.py", text))
    return calls


def _iter_workflow_run_blocks(payload: dict[str, Any]) -> list[str]:
    runs: list[str] = []
    for job in (payload.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                runs.append(step["run"])
    return runs


def _count_run_block_token(payload: dict[str, Any], token: str) -> int:
    return sum(run_block.count(token) for run_block in _iter_workflow_run_blocks(payload))


def required_contexts() -> list[str]:
    contract = json.loads(read(REQUIRED_CONTEXTS_PATH))
    return list(contract["required_contexts"])


def ci_metrics() -> dict[str, Any]:
    ci = ROOT / ".github/workflows/ci.yml"
    text = read(ci)
    ci_data = yaml.safe_load(text)
    workflows = workflow_texts()
    registry = load_yaml(REGISTRY_PATH) if REGISTRY_PATH.exists() else []
    required = set(required_contexts()) if REQUIRED_CONTEXTS_PATH.exists() else set()
    return {
        "ci_yml_total_line_count": len(text.splitlines()),
        "ci_yml_active_line_count": len(
            [
                line
                for line in text.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        ),
        "ci_yml_active_job_count": len(ci_data.get("jobs", {})),
        "total_default_ci_workflow_count": sum(
            1
            for workflow_text in workflows.values()
            if "pull_request:" in workflow_text or "push:" in workflow_text
        ),
        "total_workflow_file_count": len(workflows),
        "scripts_ci_file_count": len(script_paths()),
        "active_enforcer_count": sum(
            1
            for gate in registry
            if gate.get("registry_action") != "utility"
            and str(gate.get("path", "")).startswith("scripts/ci/")
        ),
        "required_enforcer_count": sum(
            1 for gate in registry if gate.get("status") == "required"
        ),
        "legacy_historical_enforcer_count": sum(
            1
            for gate in registry
            if gate.get("status") in {"historical", "legacy", "deprecated"}
        ),
        "scripts_ci_invocations_on_default_ci_path": sum(
            len(re.findall(r"scripts/ci/[A-Za-z0-9_./-]+\.py", run_block))
            for run_block in _iter_workflow_run_blocks(ci_data)
        ),
        "duplicated_db_setup_blocks": _count_run_block_token(
            ci_data,
            "scripts/database/prepare_migration_authority_boundary.py"
        ),
        "db_setup_action_uses": text.count("./.github/actions/setup-postgres-ci"),
        "db_setup_executions_on_default_ci_path": text.count("./.github/actions/setup-postgres-ci")
        + _count_run_block_token(ci_data, "scripts/database/prepare_migration_authority_boundary.py"),
        "execution_cohorts": sorted(
            {str(gate.get("execution_cohort")) for gate in registry if gate.get("execution_cohort")}
        ),
        "maximum_ci_nesting_depth": 2 if "./.github/actions/setup-postgres-ci" in text else 1,
        "required_branch_contexts": sorted(required),
        "historical_legacy_gates_still_executing_by_default": [
            gate["id"]
            for gate in registry
            if gate.get("default_execution")
            and gate.get("status") in {"historical", "legacy", "deprecated"}
        ],
    }


def validate_registry(v: Validation) -> None:
    v.require(REGISTRY_PATH.exists(), "M3_BLOCKED_BY_PASSIVE_REGISTRY_ONLY")
    registry = load_yaml(REGISTRY_PATH)
    registered_paths = {str(gate.get("path")) for gate in registry}
    registered_ids = {str(gate.get("id")) for gate in registry}
    v.require(len(registered_ids) == len(registry), "duplicate_registry_gate_ids")

    for gate in registry:
        missing = REQUIRED_REGISTRY_FIELDS - set(gate)
        v.require(not missing, f"registry_missing_fields:{gate.get('id')}:{sorted(missing)}")
        for key in (
            "id",
            "path",
            "owning_phase",
            "protected_invariant",
            "command",
            "local_reproduction_command",
            "expected_failure_meaning",
            "first_diagnostic_command",
            "execution_cohort",
            "ci_visibility",
            "registry_action",
        ):
            v.require(bool(gate.get(key)), f"registry_empty_field:{gate.get('id')}:{key}")

    missing_scripts = sorted(script_paths() - registered_paths)
    v.require(not missing_scripts, f"M3_BLOCKED_BY_UNREGISTERED_ENFORCERS:{missing_scripts}")

    unregistered_calls = sorted(workflow_script_calls() - registered_paths)
    v.require(not unregistered_calls, f"workflow_calls_unregistered_enforcers:{unregistered_calls}")

    v.require(
        "m3_b24_gate_dry_run" in registered_ids,
        "M3_BLOCKED_BY_B24_GATE_INSERTION_UNSAFETY",
    )


def validate_subsumption(v: Validation) -> None:
    v.require(SUBSUMPTION_PATH.exists(), "M3_BLOCKED_BY_UNDISPOSITIONED_HISTORICAL_GATES")
    matrix = load_yaml(SUBSUMPTION_PATH)
    registry_ids = {gate["id"] for gate in load_yaml(REGISTRY_PATH)}
    matrix_ids = {entry.get("gate_id") for entry in matrix}
    v.require(
        registry_ids <= matrix_ids,
        f"M3_BLOCKED_BY_UNDISPOSITIONED_HISTORICAL_GATES:{sorted(registry_ids - matrix_ids)}",
    )
    for entry in matrix:
        missing = REQUIRED_SUBSUMPTION_FIELDS - set(entry)
        v.require(not missing, f"subsumption_missing_fields:{entry.get('gate_id')}:{sorted(missing)}")
        v.require(bool(entry.get("decision")), f"subsumption_missing_decision:{entry.get('gate_id')}")
        if entry.get("current_status") in {"historical", "legacy", "deprecated"}:
            evidence = str(entry.get("subsumption_evidence", ""))
            v.require(
                len(evidence) > 20,
                f"M3_BLOCKED_BY_UNSUPPORTED_KEEP_ALL_CLAIM:{entry.get('gate_id')}",
            )


def validate_topology(v: Validation) -> None:
    v.require(TOPOLOGY_PATH.exists(), "M3_BLOCKED_BY_UNINDEXED_CI_TOPOLOGY")
    text = read(TOPOLOGY_PATH)
    for token in (
        "Required Branch Contexts",
        "M0 Maintainability Scope Lock",
        "M1 Local Development Authority",
        "M2 Test Feedback Loop",
        "B2.4 Insertion Lane",
        "Execution Cohorts",
    ):
        v.require(token in text, f"M3_BLOCKED_BY_UNINDEXED_CI_TOPOLOGY:missing:{token}")
    for context in required_contexts():
        v.require(
            context in text,
            f"M3_BLOCKED_BY_BRANCH_PROTECTION_CONTEXT_DRIFT:missing:{context}",
        )


def validate_structural_reduction(v: Validation) -> None:
    metrics = ci_metrics()
    ci_text = read(ROOT / ".github/workflows/ci.yml")
    runner_text = read(ROOT / "scripts/ci/run_ci_governance_cohort.py")
    action_text = read(ROOT / ".github/actions/setup-postgres-ci/action.yml")
    v.require(
        metrics["duplicated_db_setup_blocks"] <= BASELINE_CI_DB_SETUP_BLOCKS // 4,
        "M3_BLOCKED_BY_DUPLICATED_DB_SETUP_SURFACE",
    )
    v.require(
        metrics["db_setup_action_uses"] >= 8,
        "M3_BLOCKED_BY_TRIVIAL_MONOLITH_REDUCTION:db_setup_action_underused",
    )
    v.require(
        metrics["scripts_ci_invocations_on_default_ci_path"]
        < BASELINE_CI_ENFORCER_INVOCATIONS,
        "M3_BLOCKED_BY_UNTOUCHED_CI_MONOLITH:enforcer_invocations_not_reduced",
    )
    v.require(
        "run_ci_governance_cohort.py --cohort contract-governance" in ci_text,
        "M3_BLOCKED_BY_PASSIVE_REGISTRY_ONLY",
    )
    contract_cohort_size = sum(
        1
        for gate in load_yaml(REGISTRY_PATH)
        if gate.get("execution_cohort") == "contract-governance"
        and gate.get("default_execution")
    )
    v.require(
        contract_cohort_size >= 24,
        f"M3_BLOCKED_BY_OPAQUE_REGISTRY_RUNNER:contract_cohort_too_small:{contract_cohort_size}",
    )
    v.require(
        "gate_id" in runner_text
        and "local_reproduction_command" in runner_text
        and "::error title=" in runner_text,
        "M3_BLOCKED_BY_OPAQUE_REGISTRY_RUNNER",
    )
    v.require(
        len(action_text.splitlines()) < 120,
        "M3_BLOCKED_BY_COMPLEXITY_DISPLACEMENT:oversized_setup_action",
    )
    v.require(
        metrics["ci_yml_total_line_count"] < BASELINE_CI_LINES,
        "M3_BLOCKED_BY_UNTOUCHED_CI_MONOLITH:ci_yml_not_reduced",
    )


def validate_b24(v: Validation) -> None:
    workflow = ROOT / ".github/workflows/b2_4-gate-dry-run.yml"
    policy = ROOT / "docs/ci/b2_4_gate_insertion_policy.md"
    v.require(workflow.exists(), "M3_BLOCKED_BY_B24_GATE_INSERTION_UNSAFETY")
    v.require(policy.exists(), "M3_BLOCKED_BY_B24_GATE_INSERTION_UNSAFETY")
    workflow_text = read(workflow) if workflow.exists() else ""
    policy_text = read(policy) if policy.exists() else ""
    forbidden = ("pymc-marketing", "pm.sample")
    v.require(
        not any(token in policy_text.lower() for token in forbidden),
        "M3_BLOCKED_BY_PHASE_CONTAMINATION",
    )
    v.require(
        "B2.4-P5 Bayesian Runtime Harness" in workflow_text
        and "validate-b24-p5-runtime-harness" in workflow_text,
        "M3_BLOCKED_BY_B24_GATE_INSERTION_UNSAFETY:p5_runtime_harness_missing",
    )
    v.require(
        "m3_b24_gate_dry_run" in {gate["id"] for gate in load_yaml(REGISTRY_PATH)},
        "M3_BLOCKED_BY_B24_GATE_INSERTION_UNSAFETY",
    )


def validate_runtime_harness(v: Validation) -> None:
    workflow = ROOT / ".github/workflows/m3-ci-governance.yml"
    v.require(workflow.exists(), "M3_BLOCKED_BY_RUNTIME_PROOF_GAP")
    text = read(workflow) if workflow.exists() else ""
    for target in (
        "make validate-ci-governance",
        "make ci-enforcer-registry-check",
        "make ci-gate-subsumption-check",
        "make ci-b24-gate-dry-run",
        "make ci-metrics",
        "make ci-cohort-summary",
    ):
        v.require(target in text, f"M3_BLOCKED_BY_RUNTIME_PROOF_GAP:missing:{target}")


def validate_completion_record(v: Validation) -> None:
    v.require(COMPLETION_PATH.exists(), "missing_m3_completion_record")
    if not COMPLETION_PATH.exists():
        return
    text = read(COMPLETION_PATH)
    for token in (
        "CI Complexity Metrics",
        "Complexity-Displacement Analysis",
        "DB Setup Rationalization Proof",
        "Branch Protection / Required Context Mapping",
        "M0/M1/M2 Preservation Proof",
        "Final Verdict",
    ):
        v.require(token in text, f"m3_completion_record_missing:{token}")


def run_selected(args: argparse.Namespace) -> int:
    v = Validation()
    if args.registry or args.all:
        validate_registry(v)
    if args.subsumption or args.all:
        validate_subsumption(v)
    if args.topology or args.all:
        validate_topology(v)
    if args.structural_reduction or args.all:
        validate_structural_reduction(v)
    if args.b24_dry_run or args.all:
        validate_b24(v)
    if args.runtime_harness or args.all:
        validate_runtime_harness(v)
    if args.completion_record or args.all:
        validate_completion_record(v)

    if args.metrics:
        print(json.dumps(ci_metrics(), indent=2, sort_keys=True))

    if v.failures:
        for failure in v.failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("M3_CI_GOVERNANCE_VALIDATION_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--registry", action="store_true")
    parser.add_argument("--subsumption", action="store_true")
    parser.add_argument("--topology", action="store_true")
    parser.add_argument("--structural-reduction", action="store_true")
    parser.add_argument("--b24-dry-run", action="store_true")
    parser.add_argument("--runtime-harness", action="store_true")
    parser.add_argument("--completion-record", action="store_true")
    parser.add_argument("--metrics", action="store_true")
    args = parser.parse_args()
    if not any(vars(args).values()):
        args.all = True
    return run_selected(args)


if __name__ == "__main__":
    raise SystemExit(main())

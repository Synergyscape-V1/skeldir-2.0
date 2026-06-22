#!/usr/bin/env python3
"""Validate B2.4-P11 CI gate coverage and negative-control governance."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/ci/b24_p11_phase_validator_matrix.yaml"
WORKFLOW = ROOT / ".github/workflows/b2_4-gate-dry-run.yml"
MAKEFILE = ROOT / "Makefile"
REGISTRY = ROOT / "docs/ci/enforcer_registry.yaml"
SUBSUMPTION = ROOT / "docs/ci/gate_subsumption_matrix.yaml"
REQUIRED_STATUS = ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
CI_README = ROOT / "docs/ci/README.md"
CI_TOPOLOGY = ROOT / "docs/ci/ci_topology_map.md"
EVIDENCE_PACK = ROOT / "docs/forensics/B2.4-P11 Remediation Evidence Pack .md"
EXECUTION_MANIFEST = ROOT / "docs/ci/b24_p11_execution_manifest.yaml"
EXECUTION_VALIDATOR = ROOT / "scripts/ci/validate_b24_p11_execution_artifacts.py"
LIVE_BRANCH_VALIDATOR = ROOT / "scripts/ci/validate_live_branch_protection.py"
WORKFLOW_VACUITY_VALIDATOR = ROOT / "scripts/ci/validate_b24_p11_workflow_vacuity.py"
COMMAND_JUNIT_WRITER = ROOT / "scripts/ci/write_b24_p11_command_junit.py"
DEFAULT_SUMMARY = ROOT / "artifacts/b24_p11_ci_gate_matrix.json"

EXPECTED_PHASES = tuple(f"B2.4-P{i}" for i in range(1, 12))
P1_TO_P10 = set(EXPECTED_PHASES[:10])
REQUIRED_MATRIX_FIELDS = {
    "phase_id",
    "phase_name",
    "load_bearing_invariant",
    "validator_target",
    "workflow_job",
    "make_target",
    "negative_control_command",
    "required_status_name",
    "registry_id",
    "evidence_artifact",
    "non_vacuity_status",
    "non_overclaim_boundary",
}
LOAD_BEARING_REQUIRED_CONTEXTS = {
    "B2.4 Gate Dry Run",
    "B2.4-P1 DB Proof",
    "B2.4-P4 PostgreSQL Runtime Proof",
    "B2.4-P5 Bayesian Runtime Harness",
    "B2.4-P5 PostgreSQL Runtime Proof",
    "B2.4-P6 Real Fit Worker Proof",
    "B2.4-P7 Diagnostic Semantics Proof",
    "B2.4-P8 Artifact Lifecycle Proof",
    "B2.4-P9 Worker Tenant Hygiene Proof",
    "B2.4-P10 Read-Only Projection Proof",
    "B2.4-P11 CI Gates and Negative Control Harness",
}
NON_OVERCLAIM_PHRASE = (
    "P11 proves merge-blocking CI enforcement, not production-topology trust closure"
)


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise ValidationError(f"missing required file: {path.relative_to(ROOT).as_posix()}")
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _load_yaml_text(text: str, label: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValidationError(f"{label} is not valid YAML: {exc}") from exc


def _load_json_text(text: str, label: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{label} is not valid JSON: {exc}") from exc
    _require(isinstance(data, dict), f"{label} must be a JSON object")
    return data


def _workflow_job_names(workflow_text: str) -> set[str]:
    workflow = _load_yaml_text(workflow_text, "B2.4 workflow")
    jobs = workflow.get("jobs") if isinstance(workflow, dict) else None
    _require(isinstance(jobs, dict), "B2.4 workflow has no jobs mapping")
    names: set[str] = set()
    for job_id, job in jobs.items():
        _require(isinstance(job, dict), f"workflow job is not a mapping: {job_id}")
        name = str(job.get("name") or job_id)
        names.add(name)
        if name in LOAD_BEARING_REQUIRED_CONTEXTS:
            _require(job.get("if") not in {False, "false", "${{ false }}"}, f"required job is statically skipped: {name}")
    return names


def _load_registry(registry_text: str) -> dict[str, dict[str, Any]]:
    data = _load_yaml_text(registry_text, "enforcer registry")
    _require(isinstance(data, list), "enforcer registry must be a YAML list")
    registry: dict[str, dict[str, Any]] = {}
    for entry in data:
        _require(isinstance(entry, dict), "registry entry must be a mapping")
        gate_id = str(entry.get("id", ""))
        _require(gate_id, "registry entry missing id")
        _require(gate_id not in registry, f"duplicate registry id: {gate_id}")
        registry[gate_id] = entry
    return registry


def _load_subsumption_ids(subsumption_text: str) -> set[str]:
    data = _load_yaml_text(subsumption_text, "gate subsumption matrix")
    _require(isinstance(data, list), "gate subsumption matrix must be a YAML list")
    return {str(entry.get("gate_id", "")) for entry in data if isinstance(entry, dict)}


def _required_contexts(required_text: str) -> set[str]:
    data = _load_json_text(required_text, "required status contract")
    contexts = data.get("required_contexts")
    _require(isinstance(contexts, list), "required status contract missing required_contexts list")
    return {str(context) for context in contexts}


def _load_execution_manifest(manifest_text: str) -> list[dict[str, Any]]:
    data = _load_yaml_text(manifest_text, "P11 execution manifest")
    _require(isinstance(data, list), "P11 execution manifest must be a YAML list")
    required = {
        "phase_id",
        "workflow_job",
        "required_status",
        "test_artifact_path",
        "expected_test_modules",
        "expected_test_cases",
        "minimum_test_count",
        "allowed_skips",
        "allowed_xfails",
        "required_markers",
        "execution_required",
        "required_command_fragments",
        "non_overclaim_boundary",
    }
    rows: list[dict[str, Any]] = []
    for row in data:
        _require(isinstance(row, dict), "P11 execution manifest row must be a mapping")
        missing = required - set(row)
        _require(not missing, f"execution manifest row missing fields:{row.get('workflow_job')}:{sorted(missing)}")
        _require(row["execution_required"] is True, f"execution manifest row must be required: {row.get('workflow_job')}")
        _require(_as_list(row["expected_test_cases"]), f"execution manifest row lacks expected cases: {row.get('workflow_job')}")
        _require(int(row["minimum_test_count"]) > 0, f"execution manifest row has non-positive minimum count: {row.get('workflow_job')}")
        _require(not _as_list(row["allowed_skips"]), f"execution manifest allows skips: {row.get('workflow_job')}")
        _require(not _as_list(row["allowed_xfails"]), f"execution manifest allows xfails: {row.get('workflow_job')}")
        rows.append(row)
    return rows


def _load_matrix(matrix_text: str) -> list[dict[str, Any]]:
    data = _load_yaml_text(matrix_text, "P11 phase matrix")
    _require(isinstance(data, list), "P11 phase matrix must be a YAML list")
    matrix: list[dict[str, Any]] = []
    for row in data:
        _require(isinstance(row, dict), "P11 matrix row must be a mapping")
        missing = REQUIRED_MATRIX_FIELDS - set(row)
        _require(not missing, f"matrix row missing fields:{row.get('phase_id')}:{sorted(missing)}")
        matrix.append(row)
    phase_ids = [str(row["phase_id"]) for row in matrix]
    _require(tuple(phase_ids) == EXPECTED_PHASES, f"matrix phases must be ordered P1-P11: {phase_ids}")
    return matrix


def _validate_registry_entry(row: dict[str, Any], registry: dict[str, dict[str, Any]]) -> None:
    phase = str(row["phase_id"])
    gate_id = str(row["registry_id"])
    _require(gate_id in registry, f"{phase} registry entry missing: {gate_id}")
    entry = registry[gate_id]
    _require(str(entry.get("owning_phase")) == phase, f"{phase} registry owning_phase mismatch")
    _require(str(entry.get("path")) == str(row["validator_target"]), f"{phase} registry path mismatch")
    _require(str(entry.get("command")) == str(row["negative_control_command"]), f"{phase} registry command mismatch")
    _require(str(entry.get("local_reproduction_command")) == f"make {row['make_target']}", f"{phase} registry make target mismatch")
    _require(entry.get("default_execution") is True, f"{phase} registry default_execution must be true")
    _require(str(entry.get("execution_cohort")) == "b2-4-dry-run", f"{phase} registry cohort mismatch")
    _require(str(entry.get("registry_action")) == "keep", f"{phase} registry_action must be keep")


def validate_all(
    *,
    matrix_text: str | None = None,
    workflow_text: str | None = None,
    makefile_text: str | None = None,
    registry_text: str | None = None,
    subsumption_text: str | None = None,
    required_text: str | None = None,
    readme_text: str | None = None,
    topology_text: str | None = None,
    evidence_text: str | None = None,
    manifest_text: str | None = None,
    summary_path: Path | None = DEFAULT_SUMMARY,
) -> dict[str, Any]:
    matrix_text = matrix_text if matrix_text is not None else _read(MATRIX)
    workflow_text = workflow_text if workflow_text is not None else _read(WORKFLOW)
    makefile_text = makefile_text if makefile_text is not None else _read(MAKEFILE)
    registry_text = registry_text if registry_text is not None else _read(REGISTRY)
    subsumption_text = subsumption_text if subsumption_text is not None else _read(SUBSUMPTION)
    required_text = required_text if required_text is not None else _read(REQUIRED_STATUS)
    readme_text = readme_text if readme_text is not None else _read(CI_README)
    topology_text = topology_text if topology_text is not None else _read(CI_TOPOLOGY)
    evidence_text = evidence_text if evidence_text is not None else _read(EVIDENCE_PACK)
    manifest_text = manifest_text if manifest_text is not None else _read(EXECUTION_MANIFEST)

    matrix = _load_matrix(matrix_text)
    execution_manifest = _load_execution_manifest(manifest_text)
    workflow_jobs = _workflow_job_names(workflow_text)
    registry = _load_registry(registry_text)
    subsumption_ids = _load_subsumption_ids(subsumption_text)
    required_contexts = _required_contexts(required_text)

    _require("pull_request:" in workflow_text and "push:" in workflow_text, "B2.4 workflow must run on push and pull_request")
    _require("paths-ignore" not in workflow_text and "paths:" not in workflow_text, "B2.4 workflow must not path-filter docs/evidence commits")
    _require(LOAD_BEARING_REQUIRED_CONTEXTS <= workflow_jobs, f"workflow missing required B2.4 jobs: {sorted(LOAD_BEARING_REQUIRED_CONTEXTS - workflow_jobs)}")
    _require(LOAD_BEARING_REQUIRED_CONTEXTS <= required_contexts, f"required-status contract missing B2.4 contexts: {sorted(LOAD_BEARING_REQUIRED_CONTEXTS - required_contexts)}")
    b24_required = {context for context in required_contexts if context.startswith("B2.4")}
    _require(b24_required == LOAD_BEARING_REQUIRED_CONTEXTS, f"obsolete or missing B2.4 required contexts: {sorted(b24_required ^ LOAD_BEARING_REQUIRED_CONTEXTS)}")

    for path in (
        EXECUTION_VALIDATOR,
        LIVE_BRANCH_VALIDATOR,
        WORKFLOW_VACUITY_VALIDATOR,
        COMMAND_JUNIT_WRITER,
    ):
        _require(path.exists(), f"P11 execution-physical validator missing: {path.relative_to(ROOT).as_posix()}")

    manifest_jobs = {str(row["workflow_job"]) for row in execution_manifest}
    _require(
        LOAD_BEARING_REQUIRED_CONTEXTS <= manifest_jobs,
        f"execution manifest missing required B2.4 contexts: {sorted(LOAD_BEARING_REQUIRED_CONTEXTS - manifest_jobs)}",
    )
    manifest_statuses = {str(row["required_status"]) for row in execution_manifest}
    _require(
        LOAD_BEARING_REQUIRED_CONTEXTS <= manifest_statuses,
        f"execution manifest missing required statuses: {sorted(LOAD_BEARING_REQUIRED_CONTEXTS - manifest_statuses)}",
    )
    for command in (
        "validate-b24-p11-workflow-vacuity",
        "validate-b24-p11-live-branch-protection",
        "validate-b24-p11-execution-artifacts",
    ):
        _require(command in makefile_text, f"P11 Makefile target missing: {command}")
    for fragment in (
        "actions/download-artifact@v4",
        "validate_b24_p11_workflow_vacuity.py --negative-control",
        "validate_live_branch_protection.py --negative-control",
        "validate_b24_p11_execution_artifacts.py --negative-control",
        "validate_b24_p11_execution_artifacts.py",
        "b24-p11-execution-physical-proof",
    ):
        _require(fragment in workflow_text, f"P11 workflow missing execution-physical fragment: {fragment}")

    registry_b24_count = sum(
        1
        for entry in registry.values()
        if entry.get("execution_cohort") == "b2-4-dry-run"
        and entry.get("default_execution") is True
        and entry.get("registry_action") != "utility"
    )
    _require(f"`b2-4-dry-run`: {registry_b24_count} registered gate(s)" in readme_text, "CI README has stale b2-4-dry-run cohort count")
    _require(f"`b2-4-dry-run`: {registry_b24_count} registered gate(s)" in topology_text, "CI topology has stale b2-4-dry-run cohort count")
    for context in LOAD_BEARING_REQUIRED_CONTEXTS:
        _require(context in topology_text, f"CI topology missing required context: {context}")

    for row in matrix:
        phase = str(row["phase_id"])
        validator = ROOT / str(row["validator_target"])
        _require(validator.exists(), f"{phase} validator missing: {row['validator_target']}")
        _require(str(row["make_target"]) in makefile_text, f"{phase} Makefile target missing")
        _require(str(row["negative_control_command"]) in makefile_text, f"{phase} Makefile command missing")
        for job in _as_list(row["workflow_job"]):
            _require(job in workflow_jobs, f"{phase} workflow job missing: {job}")
        for status in _as_list(row["required_status_name"]):
            _require(status in required_contexts, f"{phase} required status missing: {status}")
        _validate_registry_entry(row, registry)
        _require(str(row["registry_id"]) in subsumption_ids, f"{phase} subsumption entry missing")
        _require("--negative-control" in str(row["negative_control_command"]), f"{phase} negative control is not normalized")
        _require("behavioral_negative_control" in str(row["non_vacuity_status"]), f"{phase} non-vacuity status is weak")
        _require("production-topology trust closure" in str(row["non_overclaim_boundary"]), f"{phase} non-overclaim boundary missing")
        if phase in P1_TO_P10:
            _require(phase.replace("B2.4-", "P") not in str(row["load_bearing_invariant"]), f"{phase} invariant is too token-like")

    _require(NON_OVERCLAIM_PHRASE in evidence_text, "P11 evidence pack missing non-overclaim statement")

    summary = build_summary(matrix, execution_manifest)
    validate_summary_shape(summary)
    if summary_path:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _git_sha() -> str:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "local-unknown"
    return completed.stdout.strip()


def build_summary(matrix: list[dict[str, Any]], execution_manifest: list[dict[str, Any]]) -> dict[str, Any]:
    timestamp = datetime.now(UTC).isoformat()
    commit_sha = _git_sha()
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    rows: list[dict[str, Any]] = []
    manifest_by_job: dict[str, list[dict[str, Any]]] = {}
    for execution_row in execution_manifest:
        manifest_by_job.setdefault(str(execution_row["workflow_job"]), []).append(execution_row)
    for row in matrix:
        execution_rows: list[dict[str, Any]] = []
        for job in _as_list(row["workflow_job"]):
            execution_rows.extend(manifest_by_job.get(job, []))
        expected_count = sum(len(_as_list(item["expected_test_cases"])) for item in execution_rows)
        rows.append(
            {
                "phase_id": row["phase_id"],
                "validator": row["validator_target"],
                "workflow_job": _as_list(row["workflow_job"]),
                "required_status": _as_list(row["required_status_name"]),
                "negative_control_status": "registered_and_validator_checked",
                "positive_proof_status": "awaiting_execution_artifact_parser",
                "non_vacuity_status": row["non_vacuity_status"],
                "execution_artifact_path": [item["test_artifact_path"] for item in execution_rows],
                "expected_test_count": expected_count,
                "actual_test_count": 0,
                "skipped_count": 0,
                "xfail_count": 0,
                "failed_count": 0,
                "missing_expected_cases": [],
                "live_required_status_verified": False,
                "path_filter_status": "pending_workflow_vacuity_validator",
                "commit_sha": commit_sha,
                "run_id": run_id,
                "timestamp": timestamp,
            }
        )
    return {
        "schema_version": "b24-p11-ci-gate-matrix-v2",
        "commit_sha": commit_sha,
        "run_id": run_id,
        "timestamp": timestamp,
        "non_overclaim_boundary": NON_OVERCLAIM_PHRASE,
        "required_context_count": len(LOAD_BEARING_REQUIRED_CONTEXTS),
        "execution_manifest_path": EXECUTION_MANIFEST.relative_to(ROOT).as_posix(),
        "execution_artifact_status": "pending_execution_parser",
        "live_enforcement_status": "pending_live_validator",
        "workflow_vacuity_status": "pending_workflow_vacuity_validator",
        "phase_count": len(rows),
        "phases": rows,
    }


def validate_summary_shape(summary: dict[str, Any]) -> None:
    for key in ("commit_sha", "run_id", "timestamp", "non_overclaim_boundary", "phases"):
        _require(key in summary, f"summary missing field: {key}")
    _require(summary["non_overclaim_boundary"] == NON_OVERCLAIM_PHRASE, "summary overclaim boundary drift")
    phases = summary["phases"]
    _require(isinstance(phases, list) and len(phases) == 11, "summary must include P1-P11")
    required = {
        "phase_id",
        "validator",
        "workflow_job",
        "required_status",
        "negative_control_status",
        "positive_proof_status",
        "non_vacuity_status",
        "execution_artifact_path",
        "expected_test_count",
        "actual_test_count",
        "skipped_count",
        "xfail_count",
        "failed_count",
        "missing_expected_cases",
        "live_required_status_verified",
        "path_filter_status",
        "commit_sha",
        "run_id",
        "timestamp",
    }
    for row in phases:
        _require(isinstance(row, dict), "summary phase row must be object")
        missing = required - set(row)
        _require(not missing, f"summary phase row missing fields:{row.get('phase_id')}:{sorted(missing)}")


def _expect_failure(name: str, runner: Any, expected: str) -> None:
    try:
        runner()
    except ValidationError as exc:
        _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
    else:
        raise ValidationError(f"negative control did not fail: {name}")


def run_negative_controls() -> None:
    matrix_text = _read(MATRIX)
    workflow_text = _read(WORKFLOW)
    makefile_text = _read(MAKEFILE)
    registry_text = _read(REGISTRY)
    required_text = _read(REQUIRED_STATUS)
    evidence_text = _read(EVIDENCE_PACK)
    manifest_text = _read(EXECUTION_MANIFEST)
    matrix = _load_matrix(matrix_text)
    without_p10 = [deepcopy(row) for row in matrix if row["phase_id"] != "B2.4-P10"]
    weak_p7 = [deepcopy(row) for row in matrix]
    for row in weak_p7:
        if row["phase_id"] == "B2.4-P7":
            row["negative_control_command"] = "python scripts/ci/validate_b24_p7_diagnostics.py"
    _expect_failure(
        "phase_removed",
        lambda: validate_all(matrix_text=yaml.safe_dump(without_p10, sort_keys=False), summary_path=None),
        "ordered P1-P11",
    )
    _expect_failure(
        "negative_control_removed",
        lambda: validate_all(matrix_text=yaml.safe_dump(weak_p7, sort_keys=False), summary_path=None),
        "registry command mismatch",
    )
    _expect_failure(
        "workflow_job_removed",
        lambda: validate_all(workflow_text=workflow_text.replace("B2.4-P11 CI Gates and Negative Control Harness", "B2.4-P11 Missing"), summary_path=None),
        "workflow missing",
    )
    _expect_failure(
        "make_target_removed",
        lambda: validate_all(makefile_text=makefile_text.replace("validate-b24-p11-ci-gates", "validate-b24-p11-removed"), summary_path=None),
        "Makefile",
    )
    _expect_failure(
        "registry_entry_removed",
        lambda: validate_all(registry_text=registry_text.replace("validate-b24-p11-ci-gates", "validate-b24-p11-removed"), summary_path=None),
        "registry",
    )
    _expect_failure(
        "required_status_removed",
        lambda: validate_all(required_text=required_text.replace("B2.4-P11 CI Gates and Negative Control Harness", "B2.4-P11 Missing"), summary_path=None),
        "required-status",
    )
    _expect_failure(
        "overclaim_statement_removed",
        lambda: validate_all(evidence_text=evidence_text.replace(NON_OVERCLAIM_PHRASE, "P11 proves production topology trust closure"), summary_path=None),
        "non-overclaim",
    )
    _expect_failure(
        "execution_manifest_execution_disabled",
        lambda: validate_all(manifest_text=manifest_text.replace("execution_required: true", "execution_required: false", 1), summary_path=None),
        "must be required",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY))
    args = parser.parse_args()
    try:
        validate_all(summary_path=ROOT / args.summary_path)
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B24_P11_CI_GATE_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P11_CI_GATE_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

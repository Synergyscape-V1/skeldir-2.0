#!/usr/bin/env python3
"""B1.4-P6 merge-blocking privacy proof-plane binding enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DEFERRED_PHASE = "B1.4-P7"
EXPECTED_P6_CONTEXT = "B1.4 P6 Merge-Blocking Privacy Proof Plane Binding"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected YAML object in {path}")
    return payload


def _normalize_branches(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _trigger_branches(on_section: Any, key: str) -> list[str]:
    if isinstance(on_section, dict):
        trigger = on_section.get(key)
    else:
        trigger = None

    if trigger is None:
        return []
    if isinstance(trigger, list):
        # Rare syntax form where event names are listed.
        return []
    if isinstance(trigger, str):
        return []
    if isinstance(trigger, dict):
        return _normalize_branches(trigger.get("branches"))
    return []


def _job_steps(job: Any) -> list[dict[str, Any]]:
    if not isinstance(job, dict):
        return []
    steps = job.get("steps")
    if isinstance(steps, list):
        return [step for step in steps if isinstance(step, dict)]
    return []


def _job_run_text(steps: list[dict[str, Any]]) -> str:
    run_fragments: list[str] = []
    for step in steps:
        run_value = step.get("run")
        if isinstance(run_value, str):
            run_fragments.append(run_value)
    return "\n".join(run_fragments)


def _find_artifact_step(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    for step in steps:
        uses_value = step.get("uses")
        if isinstance(uses_value, str) and uses_value.strip() == "actions/upload-artifact@v4":
            return step
    return None


def _validate_job_binding(
    *,
    workflow_jobs: dict[str, Any],
    job_contract: dict[str, Any],
    errors: list[str],
    report_items: list[dict[str, Any]],
) -> None:
    job_id = str(job_contract.get("job_id", "")).strip()
    required_context = str(job_contract.get("required_context", "")).strip()
    enforcer_token = str(job_contract.get("enforcer_command_token", "")).strip()
    negative_token = str(job_contract.get("negative_control_command_token", "")).strip()
    runtime_token = str(job_contract.get("runtime_proof_command_token", "")).strip()
    artifact_dir = str(job_contract.get("artifact_dir", "")).strip()
    artifact_name = str(job_contract.get("artifact_upload_name", "")).strip()

    item_report: dict[str, Any] = {
        "job_id": job_id,
        "required_context": required_context,
        "status": "PASS",
        "checks": [],
    }
    report_items.append(item_report)

    if not job_id:
        errors.append("proof job contract missing job_id")
        item_report["status"] = "FAIL"
        return

    job = workflow_jobs.get(job_id)
    if not isinstance(job, dict):
        errors.append(f"workflow_missing_job:{job_id}")
        item_report["status"] = "FAIL"
        return

    observed_name = str(job.get("name", "")).strip()
    if observed_name != required_context:
        errors.append(
            f"job_context_mismatch:{job_id}:expected={required_context}:observed={observed_name}"
        )
        item_report["status"] = "FAIL"

    steps = _job_steps(job)
    run_text = _job_run_text(steps)

    if enforcer_token and enforcer_token not in run_text:
        errors.append(f"job_missing_enforcer_command:{job_id}:{enforcer_token}")
        item_report["status"] = "FAIL"
    if negative_token and negative_token not in run_text:
        errors.append(f"job_missing_negative_control:{job_id}:{negative_token}")
        item_report["status"] = "FAIL"
    if runtime_token and runtime_token not in run_text:
        errors.append(f"job_missing_runtime_proof:{job_id}:{runtime_token}")
        item_report["status"] = "FAIL"

    artifact_step = _find_artifact_step(steps)
    if artifact_step is None:
        errors.append(f"job_missing_artifact_upload:{job_id}")
        item_report["status"] = "FAIL"
        return

    artifact_with = artifact_step.get("with")
    if not isinstance(artifact_with, dict):
        errors.append(f"job_artifact_upload_missing_with_block:{job_id}")
        item_report["status"] = "FAIL"
        return

    observed_artifact_name = str(artifact_with.get("name", "")).strip()
    observed_artifact_path = str(artifact_with.get("path", "")).strip()
    observed_missing_mode = str(artifact_with.get("if-no-files-found", "")).strip().lower()
    observed_if = str(artifact_step.get("if", "")).strip()

    if observed_artifact_name != artifact_name:
        errors.append(
            f"job_artifact_name_mismatch:{job_id}:expected={artifact_name}:observed={observed_artifact_name}"
        )
        item_report["status"] = "FAIL"
    if observed_artifact_path != artifact_dir:
        errors.append(
            f"job_artifact_path_mismatch:{job_id}:expected={artifact_dir}:observed={observed_artifact_path}"
        )
        item_report["status"] = "FAIL"
    if observed_missing_mode != "error":
        errors.append(f"job_artifact_if_no_files_found_not_error:{job_id}")
        item_report["status"] = "FAIL"
    if observed_if != "always()":
        errors.append(f"job_artifact_if_condition_not_always:{job_id}:observed={observed_if}")
        item_report["status"] = "FAIL"


def run_enforcement(
    *,
    workflow_file: Path,
    required_checks_file: Path,
    proof_plane_contract_file: Path,
    branch_protection_contract_file: Path,
) -> tuple[int, list[str], dict[str, Any]]:
    errors: list[str] = []
    report: dict[str, Any] = {
        "enforcer": "b14_p6_proof_plane_binding",
        "result": "PASS",
        "workflow_file": str(workflow_file),
        "required_checks_file": str(required_checks_file),
        "proof_plane_contract_file": str(proof_plane_contract_file),
        "branch_protection_contract_file": str(branch_protection_contract_file),
        "jobs": [],
    }

    for required_file in (
        workflow_file,
        required_checks_file,
        proof_plane_contract_file,
        branch_protection_contract_file,
    ):
        if not required_file.exists():
            errors.append(f"missing_file:{required_file}")

    if errors:
        report["result"] = "FAIL"
        report["errors"] = errors
        return 1, errors, report

    workflow_payload = _load_yaml(workflow_file)
    required_checks = _load_json(required_checks_file)
    proof_plane_contract = _load_json(proof_plane_contract_file)
    branch_protection_contract = _load_json(branch_protection_contract_file)

    on_section = workflow_payload.get("on")
    if on_section is None and True in workflow_payload:
        # PyYAML follows YAML 1.1 where plain "on" can be parsed as boolean true.
        on_section = workflow_payload.get(True)
    push_branches = _trigger_branches(on_section, "push")
    pr_branches = _trigger_branches(on_section, "pull_request")
    required_triggers = proof_plane_contract.get("workflow_trigger_requirements", {})
    required_push = _normalize_branches(
        required_triggers.get("push_branches") if isinstance(required_triggers, dict) else []
    )
    required_pr = _normalize_branches(
        required_triggers.get("pull_request_branches")
        if isinstance(required_triggers, dict)
        else []
    )

    for branch in required_push:
        if branch not in push_branches:
            errors.append(f"workflow_missing_push_branch:{branch}")
    for branch in required_pr:
        if branch not in pr_branches:
            errors.append(f"workflow_missing_pull_request_branch:{branch}")

    workflow_jobs = workflow_payload.get("jobs")
    if not isinstance(workflow_jobs, dict):
        errors.append("workflow_missing_jobs_map")
        workflow_jobs = {}

    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        errors.append("required_checks_contract_missing_required_contexts")
        required_contexts = []

    proof_jobs = proof_plane_contract.get("proof_jobs", [])
    if not isinstance(proof_jobs, list) or not proof_jobs:
        errors.append("proof_plane_contract_missing_proof_jobs")
        proof_jobs = []

    for proof_job in proof_jobs:
        if not isinstance(proof_job, dict):
            errors.append("proof_plane_contract_invalid_job_entry")
            continue
        _validate_job_binding(
            workflow_jobs=workflow_jobs,
            job_contract=proof_job,
            errors=errors,
            report_items=report["jobs"],
        )
        context_name = str(proof_job.get("required_context", "")).strip()
        if context_name and context_name not in required_contexts:
            errors.append(f"required_checks_missing_context:{context_name}")

    p6_binding = proof_plane_contract.get("p6_binding_job")
    if not isinstance(p6_binding, dict):
        errors.append("proof_plane_contract_missing_p6_binding_job")
    else:
        _validate_job_binding(
            workflow_jobs=workflow_jobs,
            job_contract={
                "job_id": p6_binding.get("job_id"),
                "required_context": p6_binding.get("required_context", EXPECTED_P6_CONTEXT),
                "enforcer_command_token": p6_binding.get("enforcer_command_token"),
                "negative_control_command_token": p6_binding.get("negative_control_command_token"),
                "runtime_proof_command_token": p6_binding.get("test_command_token"),
                "artifact_dir": p6_binding.get("artifact_dir"),
                "artifact_upload_name": p6_binding.get("artifact_upload_name"),
            },
            errors=errors,
            report_items=report["jobs"],
        )

        p6_context = str(p6_binding.get("required_context", "")).strip()
        if p6_context != EXPECTED_P6_CONTEXT:
            errors.append(
                f"p6_context_mismatch:expected={EXPECTED_P6_CONTEXT}:observed={p6_context}"
            )
        if p6_context and p6_context not in required_contexts:
            errors.append(f"required_checks_missing_context:{p6_context}")

        p6_job_id = str(p6_binding.get("job_id", "")).strip()
        p6_job = workflow_jobs.get(p6_job_id) if p6_job_id else None
        if isinstance(p6_job, dict):
            needs = p6_job.get("needs")
            needs_list: list[str] = []
            if isinstance(needs, str):
                needs_list = [needs]
            elif isinstance(needs, list):
                needs_list = [entry for entry in needs if isinstance(entry, str)]
            expected_needs = [str(item.get("job_id", "")).strip() for item in proof_jobs]
            for dependency in expected_needs:
                if dependency and dependency not in needs_list:
                    errors.append(f"p6_job_missing_dependency:{dependency}")

    deferral = proof_plane_contract.get("branch_protection_hardware_enforcement", {})
    if not isinstance(deferral, dict):
        errors.append("proof_plane_contract_missing_branch_protection_hardware_enforcement")
    else:
        if str(deferral.get("status", "")).strip().lower() != "deferred":
            errors.append("branch_protection_hardware_enforcement_status_must_be_deferred")
        if str(deferral.get("deferred_to_phase", "")).strip() != EXPECTED_DEFERRED_PHASE:
            errors.append(
                "branch_protection_hardware_enforcement_deferred_phase_mismatch:"
                f"{deferral.get('deferred_to_phase')}"
            )
        if bool(deferral.get("blocking_for_p6", True)):
            errors.append("branch_protection_hardware_enforcement_blocking_for_p6_must_be_false")
        if not bool(deferral.get("required_for_p7_closure", False)):
            errors.append("branch_protection_hardware_enforcement_required_for_p7_closure_must_be_true")

    branch_protection_live_required = bool(
        branch_protection_contract.get("require_live_on_main", True)
    )
    if branch_protection_live_required:
        errors.append(
            "main_branch_protection_integrity.require_live_on_main must be false while P7 deferral is active"
        )

    contract_deferral = required_checks.get("hardware_enforcement", {})
    if not isinstance(contract_deferral, dict):
        errors.append("required_checks_contract_missing_hardware_enforcement")
    else:
        if str(contract_deferral.get("status", "")).strip().lower() != "deferred":
            errors.append("required_checks_contract_hardware_enforcement_status_must_be_deferred")
        if str(contract_deferral.get("deferred_to_phase", "")).strip() != EXPECTED_DEFERRED_PHASE:
            errors.append("required_checks_contract_hardware_enforcement_deferred_phase_mismatch")
        deferred_contexts = contract_deferral.get("deferred_contexts", [])
        if not isinstance(deferred_contexts, list) or EXPECTED_P6_CONTEXT not in deferred_contexts:
            errors.append(
                "required_checks_contract_hardware_enforcement_missing_p6_deferred_context"
            )

    if errors:
        report["result"] = "FAIL"
        report["errors"] = errors
        return 1, errors, report

    report["result"] = "PASS"
    report["push_branches"] = push_branches
    report["pull_request_branches"] = pr_branches
    return 0, [], report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.4-P6 proof-plane binding enforcer")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--proof-plane-contract-file",
        default="contracts-internal/governance/b14_p6_privacy_proof_plane.main.json",
    )
    parser.add_argument(
        "--branch-protection-contract-file",
        default="contracts-internal/governance/main_branch_protection_integrity.main.json",
    )
    parser.add_argument("--report-json", default=None)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv)

    if args.simulate_regression:
        sys.stdout.write(
            "b14_p6_proof_plane_binding_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=proof_plane_binding_removed\n"
        )
        return 1

    status, violations, report = run_enforcement(
        workflow_file=(REPO_ROOT / args.workflow_file).resolve(),
        required_checks_file=(REPO_ROOT / args.required_checks_file).resolve(),
        proof_plane_contract_file=(REPO_ROOT / args.proof_plane_contract_file).resolve(),
        branch_protection_contract_file=(REPO_ROOT / args.branch_protection_contract_file).resolve(),
    )

    lines = ["b14_p6_proof_plane_binding_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=proof plane topology, non-vacuity, artifacts, and governance bound")

    if args.report_json:
        report_path = Path(args.report_json)
        if not report_path.is_absolute():
            report_path = (REPO_ROOT / report_path).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines.append(f"report_json={report_path}")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

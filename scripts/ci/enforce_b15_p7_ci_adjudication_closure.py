#!/usr/bin/env python3
"""B1.5-P7 closure enforcer: CI adjudication, E2E truth, and mental-model honesty."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_job_block(ci_text: str, job_id: str) -> str:
    pattern = re.compile(
        rf"(?ms)^  {re.escape(job_id)}:\n(.*?)(?=^  [a-z0-9][a-z0-9-]*:\n|\Z)"
    )
    match = pattern.search(ci_text)
    return match.group(1) if match else ""


def run_enforcement(
    *,
    contract_file: Path,
    ci_file: Path,
    runtime_tests_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (contract_file, ci_file, runtime_tests_file)
    missing = [path for path in required_files if not path.exists()]
    if missing:
        return 1, [f"missing_file:{path}" for path in missing]

    contract = _read_json(contract_file)
    if contract.get("phase") != "B1.5-P7":
        violations.append("contract_invalid_phase")

    ci_text = ci_file.read_text(encoding="utf-8")
    runtime_tests_text = runtime_tests_file.read_text(encoding="utf-8")

    runtime_markers = contract.get("required_runtime_test_markers", [])
    if not isinstance(runtime_markers, list) or not runtime_markers:
        violations.append("contract_missing_runtime_test_markers")
    else:
        for marker in runtime_markers:
            if marker not in runtime_tests_text:
                violations.append(f"runtime_marker_missing:{marker}")

    ci_job = contract.get("required_ci_job")
    if not isinstance(ci_job, dict):
        violations.append("contract_missing_required_ci_job")
    else:
        job_id = str(ci_job.get("job_id", "")).strip()
        job_name = str(ci_job.get("job_name", "")).strip()
        if not job_id:
            violations.append("ci_job_missing_job_id")
        if not job_name:
            violations.append("ci_job_missing_job_name")

        job_block = _extract_job_block(ci_text, job_id) if job_id else ""
        if not job_block:
            violations.append(f"ci_job_block_missing:{job_id or 'unknown'}")
        else:
            if f"name: {job_name}" not in job_block:
                violations.append("ci_job_name_mismatch")

            needs = ci_job.get("needs", [])
            if not isinstance(needs, list) or not needs:
                violations.append("ci_job_missing_needs_contract")
            else:
                for needed in needs:
                    if str(needed) not in job_block:
                        violations.append(f"ci_job_missing_need:{needed}")

            commands = ci_job.get("required_commands", [])
            if not isinstance(commands, list) or not commands:
                violations.append("ci_job_missing_required_commands_contract")
            else:
                for command in commands:
                    if str(command) not in job_block:
                        violations.append(f"ci_job_missing_command:{command}")

    mental = contract.get("mental_model_study")
    if not isinstance(mental, dict):
        violations.append("contract_missing_mental_model_study")
    else:
        required_mental_files = mental.get("required_files", [])
        if not isinstance(required_mental_files, list) or not required_mental_files:
            violations.append("mental_model_missing_required_files_contract")
        else:
            for raw_path in required_mental_files:
                path = _resolve(REPO_ROOT, str(raw_path))
                if not path.exists():
                    violations.append(f"mental_model_missing_file:{raw_path}")

        status_path_raw = str(mental.get("status_file", "")).strip()
        if not status_path_raw:
            violations.append("mental_model_missing_status_file_contract")
        else:
            status_path = _resolve(REPO_ROOT, status_path_raw)
            if not status_path.exists():
                violations.append("mental_model_status_file_missing")
            else:
                status_payload = _read_json(status_path)
                status = str(status_payload.get("study_status", "")).strip()
                allowed = mental.get("allowed_statuses", [])
                if not isinstance(allowed, list) or not allowed:
                    violations.append("mental_model_missing_allowed_statuses_contract")
                elif status not in {str(item) for item in allowed}:
                    violations.append(f"mental_model_invalid_status:{status}")

                if bool(mental.get("pending_requires_zero_participants", False)):
                    if status == "pending_human_execution":
                        completed = int(status_payload.get("participants_completed", -1))
                        if completed != 0:
                            violations.append(
                                f"mental_model_pending_non_zero_participants:{completed}"
                            )

                if bool(mental.get("pending_must_not_claim_success", False)):
                    if status == "pending_human_execution":
                        if bool(status_payload.get("result_claim_present", True)):
                            violations.append(
                                "mental_model_pending_claims_success_without_human_execution"
                            )

        marker_paths = [
            _resolve(REPO_ROOT, "docs/forensics/evidence/b15_p7/mental_model_study/README.md"),
            _resolve(REPO_ROOT, "docs/forensics/evidence/b15_p7/mental_model_study/protocol.md"),
        ]
        marker_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in marker_paths
            if path.exists()
        )
        markers = mental.get("required_human_execution_markers", [])
        if not isinstance(markers, list) or not markers:
            violations.append("mental_model_missing_execution_markers_contract")
        else:
            for marker in markers:
                if str(marker) not in marker_text:
                    violations.append(f"mental_model_marker_missing:{marker}")

    p6_dep = contract.get("p6_dependency")
    if not isinstance(p6_dep, dict):
        violations.append("contract_missing_p6_dependency")
    else:
        overrides_raw = str(p6_dep.get("overrides_file", "")).strip()
        if not overrides_raw:
            violations.append("p6_dependency_missing_overrides_file")
        else:
            overrides_path = _resolve(REPO_ROOT, overrides_raw)
            if not overrides_path.exists():
                violations.append("p6_dependency_overrides_file_missing")
            else:
                overrides = _read_json(overrides_path)
                active = overrides.get("active_overrides")
                if not isinstance(active, list):
                    violations.append("p6_dependency_active_overrides_not_list")
                elif bool(p6_dep.get("active_overrides_must_be_empty", False)) and active:
                    violations.append("p6_dependency_active_overrides_present")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B1.5-P7 CI adjudication closure enforcer"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--contract-file",
        default="contracts-internal/governance/b15_p7_ci_adjudication_closure.main.json",
    )
    parser.add_argument("--ci-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--runtime-tests-file",
        default="backend/tests/test_b15_p7_ci_adjudication_closure.py",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b15_p7_ci_adjudication_closure_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        contract_file=_resolve(repo_root, args.contract_file),
        ci_file=_resolve(repo_root, args.ci_file),
        runtime_tests_file=_resolve(repo_root, args.runtime_tests_file),
    )

    lines = ["b15_p7_ci_adjudication_closure_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=b15_p7_closure_dependencies_and_honesty_verified")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

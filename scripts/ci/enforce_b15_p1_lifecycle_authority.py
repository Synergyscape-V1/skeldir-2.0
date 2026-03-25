#!/usr/bin/env python3
"""B1.5-P1 lifecycle authority and subordination enforcement."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CANONICAL_STATES = [
    "submitted",
    "validating",
    "investigating",
    "ready_for_review",
    "approved",
    "rejected",
    "refine_requested",
    "rerun_requested",
    "completed",
    "failed",
    "timeout",
    "cancelled",
]
FORBIDDEN_WORKER_TERMINAL_PATTERNS = [
    r"status\s*=\s*['\"]completed['\"]",
    r"status\s*=\s*['\"]approved['\"]",
]
REQUIRED_WORKER_CALL_SNIPPETS = [
    "_INVESTIGATION_SERVICE.mark_ready_for_review",
    "_INVESTIGATION_SERVICE.fail_job",
    "_BUDGET_JOB_SERVICE.mark_ready_for_review",
    "_BUDGET_JOB_SERVICE.fail_job",
]
REQUIRED_MIGRATION_SNIPPETS = [
    "CREATE TABLE IF NOT EXISTS budget_jobs",
    "ck_investigations_internal_trace_only",
    "ck_budget_optimization_jobs_internal_trace_only",
    "ck_investigation_jobs_status_valid",
    "COMMENT ON TABLE budget_optimization_jobs IS",
    "COMMENT ON TABLE investigations IS",
]


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_lifecycle_enum_values(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "LifecycleStatus":
            continue
        values: list[str] = []
        for class_node in node.body:
            if not isinstance(class_node, ast.Assign):
                continue
            if len(class_node.targets) != 1:
                continue
            if not isinstance(class_node.targets[0], ast.Name):
                continue
            if isinstance(class_node.value, ast.Constant) and isinstance(class_node.value.value, str):
                values.append(class_node.value.value)
        return values
    return []


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    lifecycle_file: Path,
    workers_file: Path,
    models_file: Path,
    migration_file: Path,
    budget_service_file: Path,
    investigation_service_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    for required in (
        contract_file,
        lifecycle_file,
        workers_file,
        models_file,
        migration_file,
        budget_service_file,
        investigation_service_file,
    ):
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    contract = _read_json(contract_file)
    if contract.get("phase") != "B1.5-P1":
        violations.append("contract_invalid_phase")

    domains = contract.get("domains", {})
    if not isinstance(domains, dict):
        violations.append("contract_missing_domains")
    else:
        investigation = domains.get("investigations", {})
        budget = domains.get("budget", {})
        if investigation.get("public_owner_table") != "investigation_jobs":
            violations.append("investigation_owner_table_mismatch")
        if budget.get("public_owner_table") != "budget_jobs":
            violations.append("budget_owner_table_mismatch")
        if investigation.get("competing_store") != "investigations":
            violations.append("investigation_competing_store_mismatch")
        if budget.get("competing_store") != "budget_optimization_jobs":
            violations.append("budget_competing_store_mismatch")

    canonical_states = contract.get("canonical_lifecycle_states")
    if canonical_states != EXPECTED_CANONICAL_STATES:
        violations.append("contract_canonical_lifecycle_mismatch")

    enum_values = _extract_lifecycle_enum_values(lifecycle_file)
    if enum_values != EXPECTED_CANONICAL_STATES:
        violations.append("lifecycle_enum_mismatch")

    workers_text = workers_file.read_text(encoding="utf-8")
    for snippet in REQUIRED_WORKER_CALL_SNIPPETS:
        if snippet not in workers_text:
            violations.append(f"workers_missing_required_call:{snippet}")
    for pattern in FORBIDDEN_WORKER_TERMINAL_PATTERNS:
        if re.search(pattern, workers_text):
            violations.append(f"forbidden_worker_terminalization:{pattern}")

    models_text = models_file.read_text(encoding="utf-8")
    if "class BudgetJob(" not in models_text:
        violations.append("models_missing_budget_job_authority")
    if "compute_succeeded" not in models_text:
        violations.append("models_missing_internal_compute_statuses")
    if "ck_budget_optimization_jobs_internal_trace_only" not in models_text:
        violations.append("models_missing_budget_internal_trace_constraint")
    if "ck_investigations_internal_trace_only" not in models_text:
        violations.append("models_missing_investigation_internal_trace_constraint")

    migration_text = migration_file.read_text(encoding="utf-8")
    for snippet in REQUIRED_MIGRATION_SNIPPETS:
        if snippet not in migration_text:
            violations.append(f"migration_missing_snippet:{snippet}")

    budget_service_text = budget_service_file.read_text(encoding="utf-8")
    if "FROM budget_jobs" not in budget_service_text:
        violations.append("budget_service_not_bound_to_budget_jobs")

    investigation_service_text = investigation_service_file.read_text(encoding="utf-8")
    if "FROM investigation_jobs" not in investigation_service_text:
        violations.append("investigation_service_not_bound_to_investigation_jobs")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.5-P1 lifecycle authority enforcer")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--contract-file",
        default="contracts-internal/governance/b15_p1_lifecycle_authority.main.json",
    )
    parser.add_argument(
        "--lifecycle-file",
        default="backend/app/services/centaur_lifecycle.py",
    )
    parser.add_argument(
        "--workers-file",
        default="backend/app/workers/llm.py",
    )
    parser.add_argument(
        "--models-file",
        default="backend/app/models/llm.py",
    )
    parser.add_argument(
        "--migration-file",
        default="alembic/versions/007_skeldir_foundation/202603251200_b15_p1_lifecycle_authority.py",
    )
    parser.add_argument(
        "--budget-service-file",
        default="backend/app/services/budget_job.py",
    )
    parser.add_argument(
        "--investigation-service-file",
        default="backend/app/services/investigation.py",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b15_p1_lifecycle_authority_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=_resolve(repo_root, args.contract_file),
        lifecycle_file=_resolve(repo_root, args.lifecycle_file),
        workers_file=_resolve(repo_root, args.workers_file),
        models_file=_resolve(repo_root, args.models_file),
        migration_file=_resolve(repo_root, args.migration_file),
        budget_service_file=_resolve(repo_root, args.budget_service_file),
        investigation_service_file=_resolve(repo_root, args.investigation_service_file),
    )

    lines = ["b15_p1_lifecycle_authority_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=lifecycle_authority_subordination_verified")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))


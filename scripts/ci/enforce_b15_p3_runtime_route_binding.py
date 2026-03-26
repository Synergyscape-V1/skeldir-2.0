#!/usr/bin/env python3
"""B1.5-P3 runtime route binding and review-state enforcement checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _extract_function_block(text: str, function_name: str) -> str:
    match = re.search(rf"async def {re.escape(function_name)}\(", text)
    if match is None:
        return ""
    start = match.start()
    next_match = re.search(r"\nasync def |\ndef ", text[start + 1 :])
    if next_match is None:
        return text[start:]
    end = start + 1 + next_match.start()
    return text[start:end]


def _extract_select_clause(function_block: str, table_name: str) -> str:
    pattern = re.compile(
        rf"SELECT(?P<select>[\s\S]*?)FROM\s+{re.escape(table_name)}",
        re.IGNORECASE,
    )
    match = pattern.search(function_block)
    if match is None:
        return ""
    return match.group("select")


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    main_file: Path,
    contract_scope_file: Path,
    semantics_skip_file: Path,
    investigations_api_file: Path,
    budget_api_file: Path,
    investigation_service_file: Path,
    budget_service_file: Path,
    mutation_ledger_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        contract_file,
        main_file,
        contract_scope_file,
        semantics_skip_file,
        investigations_api_file,
        budget_api_file,
        investigation_service_file,
        budget_service_file,
        mutation_ledger_file,
    )
    missing = [path for path in required_files if not path.exists()]
    if missing:
        return 1, [f"missing_file:{path}" for path in missing]

    contract = _read_json(contract_file)
    if contract.get("phase") != "B1.5-P3":
        violations.append("contract_invalid_phase")

    main_text = main_file.read_text(encoding="utf-8")
    if "from app.api import (" not in main_text:
        violations.append("main_missing_api_import_block")
    if "investigations," not in main_text:
        violations.append("main_missing_investigations_import")
    if "budget," not in main_text:
        violations.append("main_missing_budget_import")
    if "app.include_router(investigations.router" not in main_text:
        violations.append("main_missing_investigations_router_mount")
    if "app.include_router(budget.router" not in main_text:
        violations.append("main_missing_budget_router_mount")

    scope = _read_yaml(contract_scope_file)
    in_scope_prefixes = set(scope.get("in_scope_prefixes", []) or [])
    required_prefixes = set(
        contract.get("runtime_conformance_requirements", {}).get(
            "contract_scope_prefixes", []
        )
    )
    for prefix in required_prefixes:
        if prefix not in in_scope_prefixes:
            violations.append(f"contract_scope_missing_prefix:{prefix}")

    spec_mappings = scope.get("spec_mappings", {}) or {}
    required_mappings = (
        contract.get("runtime_conformance_requirements", {}).get("contract_scope_mapping", {})
        or {}
    )
    for prefix, expected_spec in required_mappings.items():
        if spec_mappings.get(prefix) != expected_spec:
            violations.append(f"contract_scope_mapping_mismatch:{prefix}")

    skip_allowlist = _read_yaml(semantics_skip_file).get("bundles", {}) or {}
    forbidden_skips = (
        contract.get("runtime_conformance_requirements", {}).get(
            "semantics_skip_allowlist_must_not_include", []
        )
        or []
    )
    for bundle in forbidden_skips:
        if bundle in skip_allowlist:
            violations.append(f"semantics_allowlist_still_skips_bundle:{bundle}")

    investigation_service_text = investigation_service_file.read_text(encoding="utf-8")
    budget_service_text = budget_service_file.read_text(encoding="utf-8")
    if "async def get_status_projection(" not in investigation_service_text:
        violations.append("investigation_service_missing_status_projection")
    if "async def get_status_projection(" not in budget_service_text:
        violations.append("budget_service_missing_status_projection")
    if "async def request_retry(" not in investigation_service_text:
        violations.append("investigation_service_missing_request_retry")
    if "async def request_retry(" not in budget_service_text:
        violations.append("budget_service_missing_request_retry")

    inv_projection_block = _extract_function_block(
        investigation_service_text, "get_status_projection"
    ).lower()
    if inv_projection_block:
        if "from investigation_jobs" not in inv_projection_block:
            violations.append("investigation_projection_missing_authority_table")
        inv_select = _extract_select_clause(inv_projection_block, "investigation_jobs")
        if re.search(r"\bresult\b", inv_select):
            violations.append("investigation_projection_hydrates_result_payload")
    budget_projection_block = _extract_function_block(
        budget_service_text, "get_status_projection"
    ).lower()
    if budget_projection_block:
        if "from budget_jobs" not in budget_projection_block:
            violations.append("budget_projection_missing_authority_table")
        budget_select = _extract_select_clause(budget_projection_block, "budget_jobs")
        if re.search(r"\bresult\b", budget_select) or re.search(
            r"\brecommendations\b", budget_select
        ):
            violations.append("budget_projection_hydrates_result_payload")

    investigations_api_text = investigations_api_file.read_text(encoding="utf-8")
    budget_api_text = budget_api_file.read_text(encoding="utf-8")
    if "ConfigDict(extra=\"forbid\")" not in investigations_api_text:
        violations.append("investigations_api_missing_strict_boundary_models")
    if "ConfigDict(extra=\"forbid\")" not in budget_api_text:
        violations.append("budget_api_missing_strict_boundary_models")
    if "get_status_projection(" not in investigations_api_text:
        violations.append("investigations_api_not_using_status_projection")
    if "get_status_projection(" not in budget_api_text:
        violations.append("budget_api_not_using_status_projection")
    if "ReviewMutationLedger" not in investigations_api_text:
        violations.append("investigations_api_missing_postgres_mutation_ledger")
    if "ReviewMutationLedger" not in budget_api_text:
        violations.append("budget_api_missing_postgres_mutation_ledger")

    mutation_ledger_text = mutation_ledger_file.read_text(encoding="utf-8").lower()
    if "compliance_audit_ledger" not in mutation_ledger_text:
        violations.append("mutation_ledger_not_backed_by_postgres_audit_table")
    if "redis" in mutation_ledger_text or "kafka" in mutation_ledger_text:
        violations.append("mutation_ledger_uses_forbidden_infra")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B1.5-P3 runtime route binding and review-state enforcer"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--contract-file",
        default="contracts-internal/governance/b15_p3_runtime_route_binding.main.json",
    )
    parser.add_argument("--main-file", default="backend/app/main.py")
    parser.add_argument(
        "--contract-scope-file",
        default="backend/app/config/contract_scope.yaml",
    )
    parser.add_argument(
        "--semantics-skip-file",
        default="tests/contract/semantics_skip_allowlist.yaml",
    )
    parser.add_argument(
        "--investigations-api-file",
        default="backend/app/api/investigations.py",
    )
    parser.add_argument("--budget-api-file", default="backend/app/api/budget.py")
    parser.add_argument(
        "--investigation-service-file",
        default="backend/app/services/investigation.py",
    )
    parser.add_argument(
        "--budget-service-file",
        default="backend/app/services/budget_job.py",
    )
    parser.add_argument(
        "--mutation-ledger-file",
        default="backend/app/services/review_mutation_ledger.py",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b15_p3_runtime_route_binding_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=_resolve(repo_root, args.contract_file),
        main_file=_resolve(repo_root, args.main_file),
        contract_scope_file=_resolve(repo_root, args.contract_scope_file),
        semantics_skip_file=_resolve(repo_root, args.semantics_skip_file),
        investigations_api_file=_resolve(repo_root, args.investigations_api_file),
        budget_api_file=_resolve(repo_root, args.budget_api_file),
        investigation_service_file=_resolve(repo_root, args.investigation_service_file),
        budget_service_file=_resolve(repo_root, args.budget_service_file),
        mutation_ledger_file=_resolve(repo_root, args.mutation_ledger_file),
    )

    lines = ["b15_p3_runtime_route_binding_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=runtime_route_binding_review_state_enforced")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

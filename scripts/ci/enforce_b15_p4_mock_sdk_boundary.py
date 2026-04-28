#!/usr/bin/env python3
"""B1.5-P4 mock plane, SDK regeneration, and typed boundary enforcement checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(_read_text(path))


def run_enforcement(
    *,
    contract_file: Path,
    start_mocks_file: Path,
    health_check_file: Path,
    mock_registry_file: Path,
    typegen_script_file: Path,
    ci_workflow_file: Path,
    frontend_package_file: Path,
    contract_gate_tsconfig_file: Path,
    contract_negative_tsconfig_file: Path,
    contract_gate_file: Path,
    contract_negative_control_file: Path,
    contract_negative_script_file: Path,
    investigations_wrapper_file: Path,
    budget_wrapper_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        contract_file,
        start_mocks_file,
        health_check_file,
        mock_registry_file,
        typegen_script_file,
        ci_workflow_file,
        frontend_package_file,
        contract_gate_tsconfig_file,
        contract_negative_tsconfig_file,
        contract_gate_file,
        contract_negative_control_file,
        contract_negative_script_file,
        investigations_wrapper_file,
        budget_wrapper_file,
    )
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        return 1, [f"missing_file:{path}" for path in missing_files]

    contract = _read_json(contract_file)
    if contract.get("phase") != "B1.5-P4":
        violations.append("contract_invalid_phase")

    start_text = _read_text(start_mocks_file)
    for required_bundle in contract.get("required_typegen_bundles", []):
        if required_bundle not in start_text:
            violations.append(f"start_mocks_missing_bundle:{required_bundle}")
    for port in contract.get("required_mock_ports", []):
        if f" {port} " not in f" {start_text} ":
            violations.append(f"start_mocks_missing_port:{port}")
    required_start_markers = (
        "llm-investigations.bundled.yaml",
        "llm-budget.bundled.yaml",
    )
    for marker in required_start_markers:
        if marker not in start_text:
            violations.append(f"start_mocks_missing_b15_surface:{marker}")

    health_text = _read_text(health_check_file)
    for port in (4024, 4025):
        if f" {port} " not in f" {health_text} ":
            violations.append(f"health_check_missing_b15_port:{port}")
    if "/api/investigations/" not in health_text:
        violations.append("health_check_missing_investigations_probe")
    if "/api/budget/recommendations/" not in health_text:
        violations.append("health_check_missing_budget_probe")

    registry = _read_json(mock_registry_file)
    primary_mocks = set(registry.get("primary_mocks", []))
    port_mapping = registry.get("port_mapping", {})
    required_domain_to_port = {
        "llm-investigations": 4024,
        "llm-budget": 4025,
        "llm-explanations": 4026,
    }
    for domain in contract.get("required_mock_domains", []):
        if domain not in primary_mocks:
            violations.append(f"mock_registry_not_primary:{domain}")
        expected_port = required_domain_to_port.get(domain)
        if expected_port is not None and port_mapping.get(domain) != expected_port:
            violations.append(f"mock_registry_port_mismatch:{domain}")

    typegen_text = _read_text(typegen_script_file)
    if "frontend/src/types/api" not in typegen_text:
        violations.append("typegen_output_dir_mismatch")
    for required_bundle in contract.get("required_typegen_bundles", []):
        if required_bundle not in typegen_text:
            violations.append(f"typegen_missing_bundle:{required_bundle}")
    if "rm -rf \"$OUTPUT_DIR\"" not in typegen_text:
        violations.append("typegen_missing_clean_output")

    ci_text = _read_text(ci_workflow_file)
    if "frontend-contract-consumption:" not in ci_text:
        violations.append("ci_missing_frontend_contract_consumption_job")
    if "npm run contract:compile" not in ci_text:
        violations.append("ci_missing_contract_compile_step")
    if "npm run contract:compile:negative" not in ci_text:
        violations.append("ci_missing_contract_negative_control_step")
    if "mock-usability-gate:" not in ci_text:
        violations.append("ci_missing_mock_usability_job")
    if "scripts/start-mocks.sh" not in ci_text:
        violations.append("ci_mock_usability_not_using_canonical_start_script")
    if "4024/api/investigations" not in ci_text:
        violations.append("ci_mock_usability_missing_investigation_probe")
    if "4025/api/budget/recommendations" not in ci_text:
        violations.append("ci_mock_usability_missing_budget_probe")

    frontend_package = _read_json(frontend_package_file)
    scripts = frontend_package.get("scripts", {})
    if "contract:compile" not in scripts:
        violations.append("frontend_package_missing_contract_compile_script")
    if "contract:compile:negative" not in scripts:
        violations.append("frontend_package_missing_contract_negative_script")

    contract_gate_tsconfig = _read_json(contract_gate_tsconfig_file)
    contract_gate_include = set(contract_gate_tsconfig.get("include", []))
    required_gate_entries = {
        "src/contract-consumption-gate.ts",
        "src/api/contracts/**/*.ts",
        "src/types/api/**/*.ts",
    }
    for entry in required_gate_entries:
        if entry not in contract_gate_include:
            violations.append(f"contract_gate_tsconfig_missing_include:{entry}")

    negative_tsconfig = _read_json(contract_negative_tsconfig_file)
    negative_include = set(negative_tsconfig.get("include", []))
    required_negative_entries = {
        "src/contract-consumption-negative-control.ts",
        "src/api/contracts/**/*.ts",
        "src/types/api/**/*.ts",
    }
    for entry in required_negative_entries:
        if entry not in negative_include:
            violations.append(f"contract_negative_tsconfig_missing_include:{entry}")

    investigations_wrapper = _read_text(investigations_wrapper_file)
    budget_wrapper = _read_text(budget_wrapper_file)
    for marker in contract.get("forbidden_wrapper_markers", []):
        if marker in investigations_wrapper or marker in budget_wrapper:
            violations.append(f"wrapper_contains_forbidden_marker:{marker}")

    required_investigation_markers = (
        'operations["createInvestigation"]',
        "/api/investigations",
        "deterministic_findings",
        "llm_synthesis",
        "authority",
        "synthesis",
    )
    for marker in required_investigation_markers:
        if marker not in investigations_wrapper:
            violations.append(f"investigations_wrapper_missing_marker:{marker}")

    required_budget_markers = (
        'operations["createBudgetOptimization"]',
        "/api/budget/optimize",
        "deterministic_recommendation",
        "llm_synthesis",
        "authority",
        "synthesis",
    )
    for marker in required_budget_markers:
        if marker not in budget_wrapper:
            violations.append(f"budget_wrapper_missing_marker:{marker}")

    contract_gate_text = _read_text(contract_gate_file)
    if "createInvestigation" not in contract_gate_text:
        violations.append("contract_gate_missing_investigation_operation_assertion")
    if "createBudgetOptimization" not in contract_gate_text:
        violations.append("contract_gate_missing_budget_operation_assertion")
    if "BudgetSeparatedResult" not in contract_gate_text:
        violations.append("contract_gate_missing_budget_typed_separation")
    if "InvestigationSeparatedResult" not in contract_gate_text:
        violations.append("contract_gate_missing_investigation_typed_separation")

    negative_control_text = _read_text(contract_negative_control_file)
    if "startInvestigation" not in negative_control_text:
        violations.append("negative_control_missing_stale_operation_probe")
    if "/api/budget/optimization" not in negative_control_text:
        violations.append("negative_control_missing_stale_path_probe")
    if "flattenedShouldFail" not in negative_control_text:
        violations.append("negative_control_missing_flattening_probe")

    negative_control_script_text = _read_text(contract_negative_script_file)
    required_negative_script_markers = (
        "Unexpected TypeScript diagnostics outside the controlled negative-control surface:",
        "requiredDiagnosticPatterns",
        "Property 'startInvestigation'",
        "Property '\\/api\\/budget\\/optimization'",
        "error TS2739:",
    )
    for marker in required_negative_script_markers:
        if marker not in negative_control_script_text:
            violations.append(f"negative_control_script_missing_marker:{marker}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B1.5-P4 mock plane + SDK boundary enforcer"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--contract-file",
        default="contracts-internal/governance/b15_p4_mock_sdk_boundary.main.json",
    )
    parser.add_argument("--start-mocks-file", default="scripts/start-mocks.sh")
    parser.add_argument("--health-check-file", default="scripts/health-check-mocks.sh")
    parser.add_argument("--mock-registry-file", default="scripts/contracts/mock_registry.json")
    parser.add_argument(
        "--typegen-script-file",
        default="scripts/contracts/generate_frontend_types.sh",
    )
    parser.add_argument("--ci-workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument("--frontend-package-file", default="frontend/package.json")
    parser.add_argument(
        "--contract-gate-tsconfig-file",
        default="frontend/tsconfig.contract-gate.json",
    )
    parser.add_argument(
        "--contract-negative-tsconfig-file",
        default="frontend/tsconfig.contract-gate.negative.json",
    )
    parser.add_argument(
        "--contract-gate-file",
        default="frontend/src/contract-consumption-gate.ts",
    )
    parser.add_argument(
        "--contract-negative-control-file",
        default="frontend/src/contract-consumption-negative-control.ts",
    )
    parser.add_argument(
        "--contract-negative-script-file",
        default="frontend/scripts/contractNegativeControl.mjs",
    )
    parser.add_argument(
        "--investigations-wrapper-file",
        default="frontend/src/api/contracts/llmInvestigationsClient.ts",
    )
    parser.add_argument(
        "--budget-wrapper-file",
        default="frontend/src/api/contracts/llmBudgetClient.ts",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b15_p4_mock_sdk_boundary_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        contract_file=_resolve(repo_root, args.contract_file),
        start_mocks_file=_resolve(repo_root, args.start_mocks_file),
        health_check_file=_resolve(repo_root, args.health_check_file),
        mock_registry_file=_resolve(repo_root, args.mock_registry_file),
        typegen_script_file=_resolve(repo_root, args.typegen_script_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        frontend_package_file=_resolve(repo_root, args.frontend_package_file),
        contract_gate_tsconfig_file=_resolve(
            repo_root, args.contract_gate_tsconfig_file
        ),
        contract_negative_tsconfig_file=_resolve(
            repo_root, args.contract_negative_tsconfig_file
        ),
        contract_gate_file=_resolve(repo_root, args.contract_gate_file),
        contract_negative_control_file=_resolve(
            repo_root, args.contract_negative_control_file
        ),
        contract_negative_script_file=_resolve(
            repo_root, args.contract_negative_script_file
        ),
        investigations_wrapper_file=_resolve(
            repo_root, args.investigations_wrapper_file
        ),
        budget_wrapper_file=_resolve(repo_root, args.budget_wrapper_file),
    )

    lines = ["b15_p4_mock_sdk_boundary_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=mock_plane_sdk_typed_boundary_enforced")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

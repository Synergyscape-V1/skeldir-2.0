#!/usr/bin/env python3
"""B1.7-P0 explanation surface lock and governance closure enforcer."""

from __future__ import annotations

import argparse
import importlib
import json
import os
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


def _extract_operations(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return operations
    for path, methods in paths.items():
        if not isinstance(path, str) or not isinstance(methods, dict):
            continue
        for method, payload in methods.items():
            method_upper = str(method).upper()
            if method_upper not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if not isinstance(payload, dict):
                continue
            operations[f"{method_upper} {path}"] = payload
    return operations


def _manifest_requirements_for_operation(
    manifest: dict[str, Any], operation_id: str
) -> list[tuple[str, dict[str, Any]]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for domain, payload in manifest.items():
        if not isinstance(payload, dict):
            continue
        requirements = payload.get("requirements", [])
        if not isinstance(requirements, list):
            continue
        for requirement in requirements:
            if not isinstance(requirement, dict):
                continue
            if requirement.get("operation_id") == operation_id:
                matches.append((str(domain), requirement))
    return matches


def _load_runtime_routes(repo_root: Path) -> set[str]:
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    os.environ.setdefault("MIGRATION_DATABASE_URL", os.environ["DATABASE_URL"])
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("CONTRACT_TESTING", "1")

    backend_path = str((repo_root / "backend").resolve())
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    app_module = importlib.import_module("app.main")
    app = getattr(app_module, "app")

    routes: set[str] = set()
    for route in app.routes:
        if not hasattr(route, "methods") or not hasattr(route, "path"):
            continue
        methods = set(route.methods) - {"HEAD", "OPTIONS"}
        for method in methods:
            routes.add(f"{str(method).upper()} {route.path}")
    return routes


def _file_contains_literal(path: Path, literal: str) -> bool:
    return literal in path.read_text(encoding="utf-8", errors="ignore")


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    contract_scope_file: Path,
    semantics_skip_file: Path,
    attribution_bundle_file: Path,
    generic_explain_bundle_file: Path,
    coverage_manifest_file: Path,
    ci_workflow_file: Path,
    required_checks_contract_file: Path,
    llm_model_file: Path,
    canonical_schema_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        contract_file,
        contract_scope_file,
        semantics_skip_file,
        attribution_bundle_file,
        generic_explain_bundle_file,
        coverage_manifest_file,
        ci_workflow_file,
        required_checks_contract_file,
        llm_model_file,
        canonical_schema_file,
    )
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        return 1, [f"missing_file:{path}" for path in missing_files]

    contract = _read_json(contract_file)
    if contract.get("phase") != "B1.7-P0":
        violations.append("contract_invalid_phase")

    canonical = contract.get("canonical_explanation_surface", {})
    if not isinstance(canonical, dict):
        violations.append("canonical_explanation_surface_missing")
        canonical = {}

    canonical_method = str(canonical.get("method", "")).upper()
    canonical_path = str(canonical.get("path", ""))
    canonical_operation_id = str(canonical.get("operation_id", ""))
    canonical_bundle = str(canonical.get("bundle", ""))
    canonical_key = f"{canonical_method} {canonical_path}".strip()
    canonical_status = str(canonical.get("implementation_status", ""))

    if canonical.get("public_route_family") != "attribution":
        violations.append("canonical_route_family_not_attribution")
    if canonical_method != "GET":
        violations.append("canonical_method_must_be_get")
    if canonical_path != "/api/attribution/explain/{entity_type}/{entity_id}":
        violations.append("canonical_path_mismatch")
    if canonical_operation_id != "explainAttributionEntity":
        violations.append("canonical_operation_id_mismatch")
    if canonical_bundle != "attribution.bundled.yaml":
        violations.append("canonical_bundle_mismatch")
    if canonical_status not in {"deferred_authoritative_future_scope", "implemented_now"}:
        violations.append("canonical_implementation_status_invalid")

    noncanonical_surfaces = contract.get("noncanonical_surfaces", [])
    if not isinstance(noncanonical_surfaces, list):
        violations.append("noncanonical_surfaces_invalid")
        noncanonical_surfaces = []

    expected_noncanonical_key = "GET /api/v1/explain/{entity_type}/{entity_id}"
    expected_noncanonical_operation_id = "getEntityExplanation"
    expected_noncanonical_bundle = "llm-explanations.bundled.yaml"
    matched_noncanonical: dict[str, Any] | None = None

    for surface in noncanonical_surfaces:
        if not isinstance(surface, dict):
            continue
        key = f"{str(surface.get('method', '')).upper()} {surface.get('path', '')}".strip()
        if key == expected_noncanonical_key:
            matched_noncanonical = surface
            break

    if matched_noncanonical is None:
        violations.append("missing_noncanonical_surface_lock")
    else:
        if matched_noncanonical.get("operation_id") != expected_noncanonical_operation_id:
            violations.append("noncanonical_operation_id_mismatch")
        if matched_noncanonical.get("bundle") != expected_noncanonical_bundle:
            violations.append("noncanonical_bundle_mismatch")
        if matched_noncanonical.get("implementation_status") != "invalid_noncanonical_blueprint":
            violations.append("noncanonical_status_mismatch")

    governed_skip_bundles_raw = contract.get("governed_runtime_skip_bundles", [])
    if not isinstance(governed_skip_bundles_raw, list) or not all(
        isinstance(item, str) for item in governed_skip_bundles_raw
    ):
        violations.append("governed_runtime_skip_bundles_invalid")
        governed_skip_bundles: set[str] = set()
    else:
        governed_skip_bundles = set(governed_skip_bundles_raw)

    if expected_noncanonical_bundle not in governed_skip_bundles:
        violations.append("noncanonical_bundle_missing_from_governed_runtime_skip")

    forbidden_skip_bundles_raw = contract.get("governed_skip_forbidden_bundles", [])
    if not isinstance(forbidden_skip_bundles_raw, list) or not all(
        isinstance(item, str) for item in forbidden_skip_bundles_raw
    ):
        violations.append("governed_skip_forbidden_bundles_invalid")
        forbidden_skip_bundles: set[str] = set()
    else:
        forbidden_skip_bundles = set(forbidden_skip_bundles_raw)

    scope = _read_yaml(contract_scope_file)
    contract_scope_allowlist = scope.get("contract_only_allowlist", [])
    if not isinstance(contract_scope_allowlist, list):
        violations.append("contract_scope_allowlist_invalid")
        contract_scope_allowlist = []

    required_scope = contract.get("contract_scope_requirements", {})
    if not isinstance(required_scope, dict):
        violations.append("contract_scope_requirements_invalid")
        required_scope = {}

    expected_mappings = required_scope.get("required_spec_mapping", {})
    if not isinstance(expected_mappings, dict):
        violations.append("contract_scope_required_spec_mapping_invalid")
        expected_mappings = {}

    scope_mappings = scope.get("spec_mappings", {})
    if not isinstance(scope_mappings, dict):
        violations.append("contract_scope_spec_mappings_invalid")
        scope_mappings = {}

    for prefix, expected_path in expected_mappings.items():
        if scope_mappings.get(prefix) != expected_path:
            violations.append(f"contract_scope_mapping_mismatch:{prefix}")

    required_allowlist_entries = required_scope.get("required_contract_only_allowlist", [])
    if not isinstance(required_allowlist_entries, list):
        violations.append("contract_scope_required_allowlist_invalid")
        required_allowlist_entries = []

    for operation in required_allowlist_entries:
        if operation not in contract_scope_allowlist:
            violations.append(f"contract_scope_allowlist_missing:{operation}")

    if canonical_status == "deferred_authoritative_future_scope" and canonical_key not in contract_scope_allowlist:
        violations.append("canonical_deferred_route_missing_allowlist_entry")
    if canonical_status == "implemented_now" and canonical_key in contract_scope_allowlist:
        violations.append("canonical_implemented_route_must_not_be_allowlisted")
    if expected_noncanonical_key in contract_scope_allowlist:
        violations.append("noncanonical_route_must_not_be_allowlisted")

    explicit_skip = _read_yaml(semantics_skip_file).get("bundles", {})
    if not isinstance(explicit_skip, dict):
        violations.append("semantics_skip_allowlist_invalid")
        explicit_skip = {}

    explicit_skip_bundles = set(explicit_skip.keys())
    for bundle in governed_skip_bundles:
        if bundle in explicit_skip_bundles:
            violations.append(f"governed_bundle_present_in_explicit_skip_allowlist:{bundle}")
    for bundle in forbidden_skip_bundles:
        if bundle in explicit_skip_bundles:
            violations.append(f"forbidden_bundle_present_in_explicit_skip_allowlist:{bundle}")

    attribution_spec = _read_yaml(attribution_bundle_file)
    attribution_operations = _extract_operations(attribution_spec)
    canonical_contract_operation = attribution_operations.get(canonical_key)
    if canonical_contract_operation is None:
        violations.append("canonical_operation_missing_from_attribution_contract")
    elif canonical_contract_operation.get("operationId") != canonical_operation_id:
        violations.append("canonical_operation_id_drift_in_attribution_contract")

    generic_explain_spec = _read_yaml(generic_explain_bundle_file)
    generic_explain_operations = _extract_operations(generic_explain_spec)
    noncanonical_contract_operation = generic_explain_operations.get(expected_noncanonical_key)
    if noncanonical_contract_operation is None:
        violations.append("noncanonical_operation_missing_from_generic_explain_contract")
    elif noncanonical_contract_operation.get("operationId") != expected_noncanonical_operation_id:
        violations.append("noncanonical_operation_id_drift_in_generic_explain_contract")

    coverage_manifest = _read_yaml(coverage_manifest_file)
    canonical_manifest_entries = _manifest_requirements_for_operation(
        coverage_manifest, canonical_operation_id
    )
    if not canonical_manifest_entries:
        violations.append("coverage_manifest_missing_canonical_operation")
    else:
        expected_manifest_status = {
            "deferred_authoritative_future_scope": "deferred",
            "implemented_now": "implemented",
        }.get(canonical_status)
        if expected_manifest_status is None:
            violations.append("canonical_status_missing_manifest_mapping")
        else:
            for domain, requirement in canonical_manifest_entries:
                if requirement.get("status") != expected_manifest_status:
                    violations.append(
                        "coverage_manifest_status_mismatch:"
                        f"{domain}:{requirement.get('requirement_id', 'UNKNOWN')}"
                    )

    noncanonical_manifest_entries = _manifest_requirements_for_operation(
        coverage_manifest, expected_noncanonical_operation_id
    )
    if noncanonical_manifest_entries:
        violations.append("coverage_manifest_contains_noncanonical_operation")

    try:
        runtime_routes = _load_runtime_routes(repo_root)
    except Exception as exc:  # pragma: no cover - defensive runtime path
        violations.append(f"runtime_route_load_failed:{exc}")
        runtime_routes = set()

    canonical_is_mounted = canonical_key in runtime_routes
    noncanonical_is_mounted = expected_noncanonical_key in runtime_routes

    if canonical_status == "deferred_authoritative_future_scope" and canonical_is_mounted:
        violations.append("canonical_route_mounted_while_deferred")
    if canonical_status == "implemented_now" and not canonical_is_mounted:
        violations.append("canonical_route_not_mounted_while_implemented")
    if noncanonical_is_mounted:
        violations.append("noncanonical_route_mounted")

    authority_lock = contract.get("authority_model_lock", {})
    if not isinstance(authority_lock, dict):
        violations.append("authority_model_lock_invalid")
        authority_lock = {}

    truth_domain = authority_lock.get("deterministic_truth_domain")
    if truth_domain != "attribution_authority":
        violations.append("authority_truth_domain_mismatch")

    truth_sources = authority_lock.get("required_truth_sources", [])
    if not isinstance(truth_sources, list) or not truth_sources or not all(
        isinstance(item, str) and item for item in truth_sources
    ):
        violations.append("authority_required_truth_sources_invalid")
        truth_sources = []

    response_separation = authority_lock.get("required_response_separation", {})
    if not isinstance(response_separation, dict):
        violations.append("authority_response_separation_invalid")
        response_separation = {}

    if response_separation.get("authoritative_metric_payload_required") is not True:
        violations.append("authority_metric_payload_flag_not_true")
    if response_separation.get("non_authoritative_explanation_payload_required") is not True:
        violations.append("authority_explanation_payload_flag_not_true")

    for source in truth_sources:
        if not _file_contains_literal(canonical_schema_file, source):
            violations.append(f"authority_truth_source_missing_from_schema:{source}")

    cache_lock = contract.get("cache_substrate_lock", {})
    if not isinstance(cache_lock, dict):
        violations.append("cache_substrate_lock_invalid")
        cache_lock = {}

    if cache_lock.get("active_substrate") != "postgres.llm_semantic_cache":
        violations.append("cache_substrate_active_value_mismatch")
    if cache_lock.get("external_cache_dependency_allowed") is not False:
        violations.append("cache_substrate_external_dependency_must_be_false")
    if cache_lock.get("external_cache_dependency_exception_ticket") is not None:
        violations.append("cache_substrate_exception_ticket_must_be_null")

    if not _file_contains_literal(llm_model_file, "llm_semantic_cache"):
        violations.append("cache_substrate_table_missing_from_model")
    if not _file_contains_literal(canonical_schema_file, "llm_semantic_cache"):
        violations.append("cache_substrate_table_missing_from_schema")

    performance_lock = contract.get("performance_semantics_lock", {})
    if not isinstance(performance_lock, dict):
        violations.append("performance_semantics_lock_invalid")
        performance_lock = {}

    if performance_lock.get("overall_endpoint_p95_ms") != 500:
        violations.append("performance_p95_target_mismatch")

    cache_hit_rate = performance_lock.get("minimum_cache_hit_rate")
    if not isinstance(cache_hit_rate, (int, float)) or float(cache_hit_rate) <= 0.6:
        violations.append("performance_cache_hit_rate_must_be_strictly_greater_than_60pct")

    if performance_lock.get("require_warm_path_diagnostics") is not True:
        violations.append("performance_warm_path_diagnostics_required")
    if performance_lock.get("require_cold_path_diagnostics") is not True:
        violations.append("performance_cold_path_diagnostics_required")
    if performance_lock.get("warm_path_only_pass_forbidden") is not True:
        violations.append("performance_warm_only_forbidden_flag_missing")

    future_gate = contract.get("future_merge_blocking_gate_category", {})
    if not isinstance(future_gate, dict):
        violations.append("future_merge_blocking_gate_category_invalid")
        future_gate = {}

    if future_gate.get("name") != "B1.7 Explanation Runtime Adjudication":
        violations.append("future_gate_name_mismatch")
    if future_gate.get("status") != "declared_for_p5":
        violations.append("future_gate_status_mismatch")

    required_dimensions = future_gate.get("required_proof_dimensions", [])
    if not isinstance(required_dimensions, list) or not required_dimensions:
        violations.append("future_gate_required_proof_dimensions_invalid")

    required_checks_contract = _read_json(required_checks_contract_file)
    future_context_declarations = required_checks_contract.get(
        "future_required_context_declarations", []
    )
    if not isinstance(future_context_declarations, list):
        violations.append("required_checks_future_context_declarations_invalid")
        future_context_declarations = []
    matched_context = None
    for declaration in future_context_declarations:
        if not isinstance(declaration, dict):
            continue
        if declaration.get("name") == "B1.7 Explanation Runtime Adjudication":
            matched_context = declaration
            break
    if matched_context is None:
        violations.append("required_checks_missing_b17_future_context_declaration")
    else:
        if matched_context.get("activation_phase") != "B1.7-P5":
            violations.append("required_checks_future_context_phase_mismatch")
        if matched_context.get("source_contract") != "contracts-internal/governance/b17_p0_explanation_surface_lock.main.json":
            violations.append("required_checks_future_context_source_contract_mismatch")

    workflow_text = ci_workflow_file.read_text(encoding="utf-8", errors="ignore")
    if "enforce_b17_p0_explanation_surface_lock.py" not in workflow_text:
        violations.append("ci_missing_b17_p0_enforcer_step")
    if "test_b17_p0_explanation_surface_lock_enforcer.py" not in workflow_text:
        violations.append("ci_missing_b17_p0_negative_control_test_step")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B1.7-P0 explanation surface lock and governance closure enforcer"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--contract-file",
        default="contracts-internal/governance/b17_p0_explanation_surface_lock.main.json",
    )
    parser.add_argument(
        "--contract-scope-file",
        default="backend/app/config/contract_scope.yaml",
    )
    parser.add_argument(
        "--semantics-skip-file",
        default="tests/contract/semantics_skip_allowlist.yaml",
    )
    parser.add_argument(
        "--attribution-bundle-file",
        default="api-contracts/dist/openapi/v1/attribution.bundled.yaml",
    )
    parser.add_argument(
        "--generic-explain-bundle-file",
        default="api-contracts/dist/openapi/v1/llm-explanations.bundled.yaml",
    )
    parser.add_argument(
        "--coverage-manifest-file",
        default="api-contracts/governance/coverage-manifest.yaml",
    )
    parser.add_argument(
        "--ci-workflow-file",
        default=".github/workflows/ci.yml",
    )
    parser.add_argument(
        "--required-checks-contract-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--llm-model-file",
        default="backend/app/models/llm.py",
    )
    parser.add_argument(
        "--canonical-schema-file",
        default="db/schema/canonical_schema.sql",
    )
    parser.add_argument("--simulate-regression", action="store_true")

    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b17_p0_explanation_surface_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=_resolve(repo_root, args.contract_file),
        contract_scope_file=_resolve(repo_root, args.contract_scope_file),
        semantics_skip_file=_resolve(repo_root, args.semantics_skip_file),
        attribution_bundle_file=_resolve(repo_root, args.attribution_bundle_file),
        generic_explain_bundle_file=_resolve(repo_root, args.generic_explain_bundle_file),
        coverage_manifest_file=_resolve(repo_root, args.coverage_manifest_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        required_checks_contract_file=_resolve(repo_root, args.required_checks_contract_file),
        llm_model_file=_resolve(repo_root, args.llm_model_file),
        canonical_schema_file=_resolve(repo_root, args.canonical_schema_file),
    )

    lines = ["b17_p0_explanation_surface_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=route_family_status_authority_cache_performance_lock_enforced")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

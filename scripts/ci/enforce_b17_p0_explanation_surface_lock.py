#!/usr/bin/env python3
"""B1.7-P0 explanation surface lock enforcer.

Primary authority for endpoint-specific B1.7-P0 semantics is the canonical
OpenAPI source operation:
  api-contracts/openapi/v1/attribution.yaml
  /api/attribution/explain/{entity_type}/{entity_id} GET
  x-skeldir-b17-p0
"""

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

CANONICAL_METHOD = "GET"
CANONICAL_PATH = "/api/attribution/explain/{entity_type}/{entity_id}"
CANONICAL_OPERATION_ID = "explainAttributionEntity"
CANONICAL_BUNDLE = "attribution.bundled.yaml"
NONCANONICAL_METHOD = "GET"
NONCANONICAL_PATH = "/api/v1/explain/{entity_type}/{entity_id}"
NONCANONICAL_OPERATION_ID = "getEntityExplanation"
NONCANONICAL_BUNDLE = "llm-explanations.bundled.yaml"
B17_LOCK_KEY = "x-skeldir-b17-p0"


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_json_or_yaml(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _read_json(path)
    return _read_yaml(path)


def _extract_operations(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for path, methods in (spec.get("paths") or {}).items():
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


def _load_runtime_routes(repo_root: Path) -> set[str]:
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    os.environ.setdefault(
        "MIGRATION_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
    )
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


def _load_runtime_openapi(repo_root: Path) -> dict[str, Any]:
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    os.environ.setdefault(
        "MIGRATION_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
    )
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("CONTRACT_TESTING", "1")

    backend_path = str((repo_root / "backend").resolve())
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    app_module = importlib.import_module("app.main")
    app = getattr(app_module, "app")
    return app.openapi()


def _load_route_set_from_file(path: Path) -> set[str]:
    payload = _read_json(path)
    items = payload.get("routes")
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise ValueError("runtime routes file must be JSON object with string list 'routes'")
    return set(items)


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
            if isinstance(requirement, dict) and requirement.get("operation_id") == operation_id:
                matches.append((str(domain), requirement))
    return matches


def _file_contains_literal(path: Path, literal: str) -> bool:
    return literal in path.read_text(encoding="utf-8", errors="ignore")


def _normalized_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _extract_lock_from_spec(
    *,
    spec: dict[str, Any],
    violations: list[str],
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    key = f"{CANONICAL_METHOD} {CANONICAL_PATH}"
    operations = _extract_operations(spec)
    operation = operations.get(key)
    if operation is None:
        violations.append(f"canonical_operation_missing_from_{label}")
        return {}, {}
    if operation.get("operationId") != CANONICAL_OPERATION_ID:
        violations.append(f"canonical_operation_id_mismatch_in_{label}")
    lock = operation.get(B17_LOCK_KEY)
    if not isinstance(lock, dict):
        violations.append(f"missing_b17_lock_extension_in_{label}")
        return operation, {}
    return operation, lock


def run_enforcement(
    *,
    repo_root: Path,
    attribution_source_file: Path,
    attribution_bundle_file: Path,
    noncanonical_source_file: Path,
    noncanonical_bundle_file: Path,
    contract_scope_file: Path,
    semantics_skip_file: Path,
    coverage_manifest_file: Path,
    ci_workflow_file: Path,
    required_checks_contract_file: Path,
    llm_model_file: Path,
    canonical_schema_file: Path,
    runtime_routes_file: Path | None,
    runtime_openapi_file: Path | None,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        attribution_source_file,
        attribution_bundle_file,
        noncanonical_source_file,
        noncanonical_bundle_file,
        contract_scope_file,
        semantics_skip_file,
        coverage_manifest_file,
        ci_workflow_file,
        required_checks_contract_file,
        llm_model_file,
        canonical_schema_file,
    )
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        return 1, [f"missing_file:{path}" for path in missing_files]

    attribution_source = _read_yaml(attribution_source_file)
    attribution_bundle = _read_yaml(attribution_bundle_file)
    noncanonical_source = _read_yaml(noncanonical_source_file)
    noncanonical_bundle = _read_yaml(noncanonical_bundle_file)

    source_operation, source_lock = _extract_lock_from_spec(
        spec=attribution_source,
        violations=violations,
        label="source_openapi",
    )
    bundle_operation, bundle_lock = _extract_lock_from_spec(
        spec=attribution_bundle,
        violations=violations,
        label="bundled_openapi",
    )
    if source_lock and bundle_lock and _normalized_json(source_lock) != _normalized_json(bundle_lock):
        violations.append("b17_lock_extension_drift_between_source_and_bundle")

    if source_operation:
        responses = source_operation.get("responses", {})
        if not isinstance(responses, dict) or "503" not in responses:
            violations.append("source_openapi_missing_503_non_operational_response")
    if bundle_operation:
        responses = bundle_operation.get("responses", {})
        if not isinstance(responses, dict) or "503" not in responses:
            violations.append("bundled_openapi_missing_503_non_operational_response")

    implementation_status = source_lock.get("implementation_status")
    if implementation_status != "mounted_not_operational":
        violations.append("b17_lock_implementation_status_must_be_mounted_not_operational")

    authority_surface = source_lock.get("authority_surface", {})
    if not isinstance(authority_surface, dict):
        violations.append("b17_lock_authority_surface_invalid")
        authority_surface = {}

    canonical_route = authority_surface.get("canonical_route", {})
    if not isinstance(canonical_route, dict):
        violations.append("b17_lock_canonical_route_invalid")
        canonical_route = {}
    if canonical_route.get("method") != CANONICAL_METHOD:
        violations.append("b17_lock_canonical_method_mismatch")
    if canonical_route.get("path") != CANONICAL_PATH:
        violations.append("b17_lock_canonical_path_mismatch")
    if canonical_route.get("operation_id") != CANONICAL_OPERATION_ID:
        violations.append("b17_lock_canonical_operation_id_mismatch")
    if canonical_route.get("bundle") != CANONICAL_BUNDLE:
        violations.append("b17_lock_canonical_bundle_mismatch")

    noncanonical_route = authority_surface.get("noncanonical_route", {})
    if not isinstance(noncanonical_route, dict):
        violations.append("b17_lock_noncanonical_route_invalid")
        noncanonical_route = {}
    if noncanonical_route.get("method") != NONCANONICAL_METHOD:
        violations.append("b17_lock_noncanonical_method_mismatch")
    if noncanonical_route.get("path") != NONCANONICAL_PATH:
        violations.append("b17_lock_noncanonical_path_mismatch")
    if noncanonical_route.get("operation_id") != NONCANONICAL_OPERATION_ID:
        violations.append("b17_lock_noncanonical_operation_id_mismatch")
    if noncanonical_route.get("bundle") != NONCANONICAL_BUNDLE:
        violations.append("b17_lock_noncanonical_bundle_mismatch")
    if noncanonical_route.get("authority_status") != "invalid_noncanonical_blueprint":
        violations.append("b17_lock_noncanonical_authority_status_mismatch")

    governed_skip_bundles = authority_surface.get("governed_runtime_skip_bundles", [])
    if not isinstance(governed_skip_bundles, list) or not all(
        isinstance(item, str) for item in governed_skip_bundles
    ):
        violations.append("b17_lock_governed_runtime_skip_bundles_invalid")
        governed_skip_bundles = []
    if NONCANONICAL_BUNDLE not in governed_skip_bundles:
        violations.append("b17_lock_missing_noncanonical_runtime_skip_bundle")

    runtime_mode = source_lock.get("runtime_contract_mode", {})
    if not isinstance(runtime_mode, dict):
        violations.append("b17_lock_runtime_contract_mode_invalid")
        runtime_mode = {}
    if runtime_mode.get("type") != "problem_details":
        violations.append("b17_lock_runtime_mode_type_mismatch")
    if runtime_mode.get("status_code") != 503:
        violations.append("b17_lock_runtime_mode_status_code_mismatch")
    if runtime_mode.get("code") != "EXPLAIN_SURFACE_NOT_READY":
        violations.append("b17_lock_runtime_mode_code_mismatch")
    if runtime_mode.get("mounted_route_required") is not True:
        violations.append("b17_lock_mounted_route_required_flag_missing")
    if runtime_mode.get("runtime_openapi_presence_required") is not True:
        violations.append("b17_lock_runtime_openapi_presence_flag_missing")

    authority_model = source_lock.get("authority_model", {})
    if not isinstance(authority_model, dict):
        violations.append("b17_lock_authority_model_invalid")
        authority_model = {}
    if authority_model.get("deterministic_truth_domain") != "attribution_authority":
        violations.append("b17_lock_truth_domain_mismatch")
    truth_sources = authority_model.get("required_truth_sources", [])
    if not isinstance(truth_sources, list) or not truth_sources:
        violations.append("b17_lock_required_truth_sources_invalid")
        truth_sources = []
    for source in truth_sources:
        if not isinstance(source, str) or not source:
            violations.append("b17_lock_required_truth_source_not_string")
            continue
        if not _file_contains_literal(canonical_schema_file, source):
            violations.append(f"authority_truth_source_missing_from_schema:{source}")

    response_separation = authority_model.get("required_response_separation", {})
    if not isinstance(response_separation, dict):
        violations.append("b17_lock_response_separation_invalid")
    else:
        if response_separation.get("authoritative_metric_payload_required") is not True:
            violations.append("b17_lock_authoritative_metric_payload_required_false")
        if response_separation.get("non_authoritative_explanation_payload_required") is not True:
            violations.append("b17_lock_non_authoritative_explanation_payload_required_false")

    cache_substrate = source_lock.get("cache_substrate", {})
    if not isinstance(cache_substrate, dict):
        violations.append("b17_lock_cache_substrate_invalid")
        cache_substrate = {}
    if cache_substrate.get("active_substrate") != "postgres.llm_semantic_cache":
        violations.append("b17_lock_cache_substrate_mismatch")
    if cache_substrate.get("external_cache_dependency_allowed") is not False:
        violations.append("b17_lock_external_cache_dependency_allowed_must_be_false")
    if cache_substrate.get("external_cache_dependency_exception_ticket") is not None:
        violations.append("b17_lock_external_cache_exception_ticket_must_be_null")
    if not _file_contains_literal(llm_model_file, "llm_semantic_cache"):
        violations.append("llm_model_missing_llm_semantic_cache")
    if not _file_contains_literal(canonical_schema_file, "llm_semantic_cache"):
        violations.append("canonical_schema_missing_llm_semantic_cache")

    performance = source_lock.get("performance_semantics", {})
    if not isinstance(performance, dict):
        violations.append("b17_lock_performance_semantics_invalid")
        performance = {}
    if performance.get("overall_endpoint_p95_ms") != 500:
        violations.append("b17_lock_performance_p95_mismatch")
    cache_hit_rate = performance.get("minimum_cache_hit_rate")
    if not isinstance(cache_hit_rate, (int, float)) or float(cache_hit_rate) <= 0.6:
        violations.append("b17_lock_performance_cache_hit_rate_must_be_gt_60pct")
    if performance.get("require_warm_path_diagnostics") is not True:
        violations.append("b17_lock_performance_require_warm_path_diagnostics_false")
    if performance.get("require_cold_path_diagnostics") is not True:
        violations.append("b17_lock_performance_require_cold_path_diagnostics_false")
    if performance.get("warm_path_only_pass_forbidden") is not True:
        violations.append("b17_lock_performance_warm_only_pass_forbidden_false")

    future_gate = source_lock.get("future_merge_blocking_gate_category", {})
    if not isinstance(future_gate, dict):
        violations.append("b17_lock_future_gate_invalid")
        future_gate = {}
    if future_gate.get("name") != "B1.7 Explanation Runtime Adjudication":
        violations.append("b17_lock_future_gate_name_mismatch")
    if future_gate.get("activation_phase") != "B1.7-P5":
        violations.append("b17_lock_future_gate_activation_phase_mismatch")
    if not isinstance(future_gate.get("required_proof_dimensions"), list):
        violations.append("b17_lock_future_gate_required_dimensions_invalid")

    noncanonical_ops_source = _extract_operations(noncanonical_source)
    noncanonical_key = f"{NONCANONICAL_METHOD} {NONCANONICAL_PATH}"
    noncanonical_source_op = noncanonical_ops_source.get(noncanonical_key)
    if noncanonical_source_op is None:
        violations.append("noncanonical_operation_missing_from_source_contract")
    else:
        if noncanonical_source_op.get("operationId") != NONCANONICAL_OPERATION_ID:
            violations.append("noncanonical_operation_id_mismatch_in_source_contract")
        lock = noncanonical_source_op.get(B17_LOCK_KEY, {})
        if not isinstance(lock, dict) or lock.get("authority_status") != "invalid_noncanonical_blueprint":
            violations.append("noncanonical_source_missing_invalid_authority_status")

    noncanonical_ops_bundle = _extract_operations(noncanonical_bundle)
    noncanonical_bundle_op = noncanonical_ops_bundle.get(noncanonical_key)
    if noncanonical_bundle_op is None:
        violations.append("noncanonical_operation_missing_from_bundled_contract")
    else:
        if noncanonical_bundle_op.get("operationId") != NONCANONICAL_OPERATION_ID:
            violations.append("noncanonical_operation_id_mismatch_in_bundled_contract")
        lock = noncanonical_bundle_op.get(B17_LOCK_KEY, {})
        if not isinstance(lock, dict) or lock.get("authority_status") != "invalid_noncanonical_blueprint":
            violations.append("noncanonical_bundle_missing_invalid_authority_status")

    scope = _read_yaml(contract_scope_file)
    mappings = scope.get("spec_mappings", {})
    if not isinstance(mappings, dict):
        violations.append("contract_scope_spec_mappings_invalid")
    elif mappings.get("/api/attribution") != "api-contracts/dist/openapi/v1/attribution.bundled.yaml":
        violations.append("contract_scope_attribution_mapping_mismatch")

    allowlist = scope.get("contract_only_allowlist", [])
    if not isinstance(allowlist, list):
        violations.append("contract_scope_contract_only_allowlist_invalid")
        allowlist = []
    canonical_key = f"{CANONICAL_METHOD} {CANONICAL_PATH}"
    if canonical_key in allowlist:
        violations.append("canonical_route_must_not_be_contract_only_allowlisted")
    if noncanonical_key in allowlist:
        violations.append("noncanonical_route_must_not_be_contract_only_allowlisted")

    semantics_skip = _read_yaml(semantics_skip_file).get("bundles", {})
    if not isinstance(semantics_skip, dict):
        violations.append("semantics_skip_allowlist_invalid")
        semantics_skip = {}
    if NONCANONICAL_BUNDLE in semantics_skip:
        violations.append("noncanonical_bundle_must_not_be_explicitly_allowlisted")
    if CANONICAL_BUNDLE in semantics_skip:
        violations.append("canonical_bundle_must_not_be_explicitly_allowlisted")

    coverage_manifest = _read_yaml(coverage_manifest_file)
    canonical_requirements = _manifest_requirements_for_operation(
        coverage_manifest, CANONICAL_OPERATION_ID
    )
    if not canonical_requirements:
        violations.append("coverage_manifest_missing_canonical_operation")
    else:
        for domain, requirement in canonical_requirements:
            if requirement.get("status") != "implemented":
                violations.append(
                    "coverage_manifest_canonical_status_must_be_implemented:"
                    f"{domain}:{requirement.get('requirement_id', 'UNKNOWN')}"
                )
    noncanonical_requirements = _manifest_requirements_for_operation(
        coverage_manifest, NONCANONICAL_OPERATION_ID
    )
    if noncanonical_requirements:
        violations.append("coverage_manifest_must_not_include_noncanonical_operation")

    try:
        runtime_routes = (
            _load_route_set_from_file(runtime_routes_file)
            if runtime_routes_file is not None
            else _load_runtime_routes(repo_root)
        )
    except Exception as exc:  # pragma: no cover
        violations.append(f"runtime_route_load_failed:{exc}")
        runtime_routes = set()

    if canonical_key not in runtime_routes:
        violations.append("canonical_route_not_mounted_runtime")
    if noncanonical_key in runtime_routes:
        violations.append("noncanonical_route_mounted_runtime")

    try:
        runtime_openapi = (
            _read_json_or_yaml(runtime_openapi_file)
            if runtime_openapi_file is not None
            else _load_runtime_openapi(repo_root)
        )
    except Exception as exc:  # pragma: no cover
        violations.append(f"runtime_openapi_load_failed:{exc}")
        runtime_openapi = {}

    runtime_paths = runtime_openapi.get("paths", {})
    if not isinstance(runtime_paths, dict):
        violations.append("runtime_openapi_paths_invalid")
        runtime_paths = {}
    canonical_runtime_path = runtime_paths.get(CANONICAL_PATH)
    if not isinstance(canonical_runtime_path, dict):
        violations.append("canonical_route_missing_from_runtime_openapi")
    else:
        runtime_operation = canonical_runtime_path.get("get")
        if not isinstance(runtime_operation, dict):
            violations.append("canonical_route_get_missing_from_runtime_openapi")
        else:
            if runtime_operation.get("operationId") != CANONICAL_OPERATION_ID:
                violations.append("canonical_runtime_openapi_operation_id_mismatch")
            runtime_responses = runtime_operation.get("responses", {})
            if not isinstance(runtime_responses, dict) or "503" not in runtime_responses:
                violations.append("canonical_runtime_openapi_missing_503_response")
            runtime_lock = runtime_operation.get(B17_LOCK_KEY, {})
            if not isinstance(runtime_lock, dict):
                violations.append("canonical_runtime_openapi_missing_b17_lock_extension")
            else:
                if runtime_lock.get("implementation_status") != "mounted_not_operational":
                    violations.append("canonical_runtime_openapi_lock_status_mismatch")
                runtime_contract_mode = runtime_lock.get("runtime_contract_mode", {})
                if not isinstance(runtime_contract_mode, dict) or runtime_contract_mode.get("status_code") != 503:
                    violations.append("canonical_runtime_openapi_lock_runtime_mode_mismatch")

    if NONCANONICAL_PATH in runtime_paths:
        violations.append("noncanonical_route_present_in_runtime_openapi")

    required_checks = _read_json(required_checks_contract_file)
    declarations = required_checks.get("future_required_context_declarations", [])
    if not isinstance(declarations, list):
        violations.append("required_checks_future_context_declarations_invalid")
        declarations = []
    matched_declaration = None
    for declaration in declarations:
        if isinstance(declaration, dict) and declaration.get("name") == "B1.7 Explanation Runtime Adjudication":
            matched_declaration = declaration
            break
    if matched_declaration is None:
        violations.append("required_checks_missing_b17_future_context_declaration")
    else:
        expected_source_contract = (
            "api-contracts/openapi/v1/attribution.yaml#/paths/"
            "~1api~1attribution~1explain~1{entity_type}~1{entity_id}/get/x-skeldir-b17-p0"
        )
        if matched_declaration.get("activation_phase") != "B1.7-P5":
            violations.append("required_checks_b17_future_context_phase_mismatch")
        if matched_declaration.get("source_contract") != expected_source_contract:
            violations.append("required_checks_b17_future_context_source_contract_mismatch")

    workflow_text = ci_workflow_file.read_text(encoding="utf-8", errors="ignore")
    if "enforce_b17_p0_explanation_surface_lock.py" not in workflow_text:
        violations.append("ci_missing_b17_p0_enforcer_step")
    if "test_b17_p0_explanation_surface_lock_enforcer.py" not in workflow_text:
        violations.append("ci_missing_b17_p0_negative_control_test_step")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.7-P0 explanation surface lock enforcer")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--attribution-source-file",
        default="api-contracts/openapi/v1/attribution.yaml",
    )
    parser.add_argument(
        "--attribution-bundle-file",
        default="api-contracts/dist/openapi/v1/attribution.bundled.yaml",
    )
    parser.add_argument(
        "--noncanonical-source-file",
        default="api-contracts/openapi/v1/llm-explanations.yaml",
    )
    parser.add_argument(
        "--noncanonical-bundle-file",
        default="api-contracts/dist/openapi/v1/llm-explanations.bundled.yaml",
    )
    parser.add_argument("--contract-scope-file", default="backend/app/config/contract_scope.yaml")
    parser.add_argument("--semantics-skip-file", default="tests/contract/semantics_skip_allowlist.yaml")
    parser.add_argument(
        "--coverage-manifest-file",
        default="api-contracts/governance/coverage-manifest.yaml",
    )
    parser.add_argument("--ci-workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--llm-model-file", default="backend/app/models/llm.py")
    parser.add_argument("--canonical-schema-file", default="db/schema/canonical_schema.sql")
    parser.add_argument("--runtime-routes-file")
    parser.add_argument("--runtime-openapi-file")
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
        attribution_source_file=_resolve(repo_root, args.attribution_source_file),
        attribution_bundle_file=_resolve(repo_root, args.attribution_bundle_file),
        noncanonical_source_file=_resolve(repo_root, args.noncanonical_source_file),
        noncanonical_bundle_file=_resolve(repo_root, args.noncanonical_bundle_file),
        contract_scope_file=_resolve(repo_root, args.contract_scope_file),
        semantics_skip_file=_resolve(repo_root, args.semantics_skip_file),
        coverage_manifest_file=_resolve(repo_root, args.coverage_manifest_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        required_checks_contract_file=_resolve(repo_root, args.required_checks_contract_file),
        llm_model_file=_resolve(repo_root, args.llm_model_file),
        canonical_schema_file=_resolve(repo_root, args.canonical_schema_file),
        runtime_routes_file=_resolve(repo_root, args.runtime_routes_file)
        if args.runtime_routes_file
        else None,
        runtime_openapi_file=_resolve(repo_root, args.runtime_openapi_file)
        if args.runtime_openapi_file
        else None,
    )

    lines = ["b17_p0_explanation_surface_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=canonical_openapi_authority_plus_runtime_route_and_openapi_convergence"
        )

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""B1.7-P1 canonical explanation authority lock enforcer."""

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
B17_LOCK_KEY = "x-skeldir-b17-p1"
LEGACY_NONCANONICAL_LOCK_KEY = "x-skeldir-b17-p0"


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (repo_root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_json_or_yaml(path: Path) -> dict[str, Any]:
    return _read_json(path) if path.suffix.lower() == ".json" else _read_yaml(path)


def _extract_operations(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for path, methods in (spec.get("paths") or {}).items():
        if not isinstance(path, str) or not isinstance(methods, dict):
            continue
        for method, payload in methods.items():
            method_upper = str(method).upper()
            if method_upper not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if isinstance(payload, dict):
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
    routes = payload.get("routes")
    if not isinstance(routes, list) or not all(isinstance(item, str) for item in routes):
        raise ValueError("runtime routes file must be JSON object with string list 'routes'")
    return set(routes)


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


def _schema_ref_for_200(operation: dict[str, Any]) -> str | None:
    responses = operation.get("responses", {})
    if not isinstance(responses, dict):
        return None
    response_200 = responses.get("200")
    if not isinstance(response_200, dict):
        return None
    return (
        response_200.get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref")
    )


def _schema_for_200(operation: dict[str, Any]) -> dict[str, Any] | None:
    responses = operation.get("responses", {})
    if not isinstance(responses, dict):
        return None
    response_200 = responses.get("200")
    if not isinstance(response_200, dict):
        return None
    schema = (
        response_200.get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    return schema if isinstance(schema, dict) else None


def _resolve_local_ref(spec: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    node: Any = spec
    for segment in ref[2:].split("/"):
        key = segment.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, dict) else None


def _has_separated_response_shape(spec: dict[str, Any], operation: dict[str, Any]) -> bool:
    schema = _schema_for_200(operation)
    if not isinstance(schema, dict):
        return False
    if "$ref" in schema and isinstance(schema["$ref"], str):
        resolved = _resolve_local_ref(spec, schema["$ref"])
        if isinstance(resolved, dict):
            schema = resolved
    required = set(schema.get("required", [])) if isinstance(schema.get("required"), list) else set()
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return False
    return {
        "authoritative_metric",
        "non_authoritative_explanation",
    }.issubset(required) and {
        "authoritative_metric",
        "non_authoritative_explanation",
    }.issubset(set(properties.keys()))


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

    canonical_key = f"{CANONICAL_METHOD} {CANONICAL_PATH}"
    source_operation = _extract_operations(attribution_source).get(canonical_key)
    bundle_operation = _extract_operations(attribution_bundle).get(canonical_key)
    if source_operation is None:
        violations.append("canonical_operation_missing_from_source_openapi")
        source_operation = {}
    if bundle_operation is None:
        violations.append("canonical_operation_missing_from_bundled_openapi")
        bundle_operation = {}

    if source_operation.get("operationId") != CANONICAL_OPERATION_ID:
        violations.append("source_operation_id_mismatch")
    if bundle_operation.get("operationId") != CANONICAL_OPERATION_ID:
        violations.append("bundle_operation_id_mismatch")

    source_lock = source_operation.get(B17_LOCK_KEY, {})
    bundle_lock = bundle_operation.get(B17_LOCK_KEY, {})
    if not isinstance(source_lock, dict):
        violations.append("source_missing_b17_p1_lock")
        source_lock = {}
    if not isinstance(bundle_lock, dict):
        violations.append("bundle_missing_b17_p1_lock")
        bundle_lock = {}
    if source_lock.get("implementation_status") != "mounted_operational_authority_read":
        violations.append("source_implementation_status_mismatch")
    if bundle_lock.get("implementation_status") != "mounted_operational_authority_read":
        violations.append("bundle_implementation_status_mismatch")

    if _schema_ref_for_200(source_operation) != "#/components/schemas/AttributionExplanationResponse":
        violations.append("source_missing_200_response_schema_ref")
    if not _has_separated_response_shape(attribution_bundle, bundle_operation):
        violations.append("bundle_missing_separated_200_response_schema")

    authority_surface = source_lock.get("authority_surface", {})
    if not isinstance(authority_surface, dict):
        violations.append("source_authority_surface_invalid")
        authority_surface = {}
    canonical_route = authority_surface.get("canonical_route", {})
    if canonical_route.get("method") != CANONICAL_METHOD:
        violations.append("source_canonical_method_mismatch")
    if canonical_route.get("path") != CANONICAL_PATH:
        violations.append("source_canonical_path_mismatch")
    if canonical_route.get("operation_id") != CANONICAL_OPERATION_ID:
        violations.append("source_canonical_operation_id_mismatch")
    if canonical_route.get("bundle") != CANONICAL_BUNDLE:
        violations.append("source_canonical_bundle_mismatch")

    noncanonical_route = authority_surface.get("noncanonical_route", {})
    if noncanonical_route.get("method") != NONCANONICAL_METHOD:
        violations.append("source_noncanonical_method_mismatch")
    if noncanonical_route.get("path") != NONCANONICAL_PATH:
        violations.append("source_noncanonical_path_mismatch")
    if noncanonical_route.get("operation_id") != NONCANONICAL_OPERATION_ID:
        violations.append("source_noncanonical_operation_id_mismatch")
    if noncanonical_route.get("bundle") != NONCANONICAL_BUNDLE:
        violations.append("source_noncanonical_bundle_mismatch")
    if noncanonical_route.get("authority_status") != "invalid_noncanonical_blueprint":
        violations.append("source_noncanonical_authority_status_mismatch")

    governed_skip_bundles = authority_surface.get("governed_runtime_skip_bundles", [])
    if not isinstance(governed_skip_bundles, list):
        violations.append("source_governed_runtime_skip_bundles_invalid")
    elif NONCANONICAL_BUNDLE not in governed_skip_bundles:
        violations.append("source_missing_noncanonical_runtime_skip_bundle")

    authority_model = source_lock.get("authority_model", {})
    if not isinstance(authority_model, dict):
        violations.append("source_authority_model_invalid")
        authority_model = {}
    if authority_model.get("deterministic_truth_domain") != "attribution_authority":
        violations.append("source_truth_domain_mismatch")
    truth_sources = authority_model.get("required_truth_sources", [])
    if not isinstance(truth_sources, list):
        violations.append("source_required_truth_sources_invalid")
        truth_sources = []
    for required_source in ("attribution_allocations", "revenue_cache_entries"):
        if required_source not in truth_sources:
            violations.append(f"missing_required_truth_source:{required_source}")
        if required_source not in canonical_schema_file.read_text(encoding="utf-8", errors="ignore"):
            violations.append(f"truth_source_missing_from_schema:{required_source}")

    separation = authority_model.get("required_response_separation", {})
    if not isinstance(separation, dict):
        violations.append("source_required_response_separation_invalid")
    else:
        if separation.get("authoritative_metric_payload_required") is not True:
            violations.append("authoritative_metric_payload_required_not_true")
        if separation.get("non_authoritative_explanation_payload_required") is not True:
            violations.append("non_authoritative_explanation_payload_required_not_true")
        if separation.get("merged_payload_forbidden") is not True:
            violations.append("merged_payload_forbidden_not_true")

    noncanonical_key = f"{NONCANONICAL_METHOD} {NONCANONICAL_PATH}"
    noncanonical_source_op = _extract_operations(noncanonical_source).get(noncanonical_key)
    noncanonical_bundle_op = _extract_operations(noncanonical_bundle).get(noncanonical_key)
    if noncanonical_source_op is None:
        violations.append("noncanonical_operation_missing_from_source_contract")
    else:
        lock = noncanonical_source_op.get(LEGACY_NONCANONICAL_LOCK_KEY, {})
        if not isinstance(lock, dict) or lock.get("authority_status") != "invalid_noncanonical_blueprint":
            violations.append("noncanonical_source_missing_invalid_authority_status")
    if noncanonical_bundle_op is None:
        violations.append("noncanonical_operation_missing_from_bundled_contract")
    else:
        lock = noncanonical_bundle_op.get(LEGACY_NONCANONICAL_LOCK_KEY, {})
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
    if canonical_key in allowlist:
        violations.append("canonical_route_must_not_be_contract_only_allowlisted")
    if noncanonical_key in allowlist:
        violations.append("noncanonical_route_must_not_be_contract_only_allowlisted")

    semantics_skip = _read_yaml(semantics_skip_file).get("bundles", {})
    if not isinstance(semantics_skip, dict):
        violations.append("semantics_skip_allowlist_invalid")
    elif NONCANONICAL_BUNDLE in semantics_skip:
        violations.append("noncanonical_bundle_must_not_be_explicitly_allowlisted")

    coverage_manifest = _read_yaml(coverage_manifest_file)
    canonical_requirements = _manifest_requirements_for_operation(coverage_manifest, CANONICAL_OPERATION_ID)
    if not canonical_requirements:
        violations.append("coverage_manifest_missing_canonical_operation")
    else:
        for domain, requirement in canonical_requirements:
            if requirement.get("status") != "implemented":
                violations.append(
                    "coverage_manifest_canonical_status_must_be_implemented:"
                    f"{domain}:{requirement.get('requirement_id', 'UNKNOWN')}"
                )

    try:
        runtime_routes = (
            _load_route_set_from_file(runtime_routes_file)
            if runtime_routes_file is not None
            else _load_runtime_routes(repo_root)
        )
    except Exception as exc:
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
    except Exception as exc:
        violations.append(f"runtime_openapi_load_failed:{exc}")
        runtime_openapi = {}

    runtime_operation = (
        (runtime_openapi.get("paths", {}) or {})
        .get(CANONICAL_PATH, {})
        .get("get", {})
    )
    if not isinstance(runtime_operation, dict):
        violations.append("canonical_route_missing_from_runtime_openapi")
    else:
        if runtime_operation.get("operationId") != CANONICAL_OPERATION_ID:
            violations.append("canonical_runtime_openapi_operation_id_mismatch")
        if not _has_separated_response_shape(runtime_openapi, runtime_operation):
            violations.append("canonical_runtime_openapi_missing_separated_200_response_schema")
        runtime_lock = runtime_operation.get(B17_LOCK_KEY, {})
        if not isinstance(runtime_lock, dict):
            violations.append("canonical_runtime_openapi_missing_b17_p1_lock")
        elif runtime_lock.get("implementation_status") != "mounted_operational_authority_read":
            violations.append("canonical_runtime_openapi_lock_status_mismatch")
        if NONCANONICAL_PATH in runtime_openapi.get("paths", {}):
            violations.append("noncanonical_route_present_in_runtime_openapi")

    required_checks = _read_json(required_checks_contract_file)
    required_contexts = required_checks.get("required_contexts", [])
    required_context_name = "B1.7 Explanation Runtime Adjudication"
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
        required_contexts = []
    if required_context_name not in required_contexts:
        violations.append("required_checks_missing_b17_required_context")

    declarations = required_checks.get("future_required_context_declarations", [])
    if isinstance(declarations, list):
        for declaration in declarations:
            if isinstance(declaration, dict) and declaration.get("name") == required_context_name:
                violations.append("required_checks_b17_context_must_not_remain_future_declared")
                break

    workflow_text = ci_workflow_file.read_text(encoding="utf-8", errors="ignore")
    if "enforce_b17_p0_explanation_surface_lock.py" not in workflow_text:
        violations.append("ci_missing_b17_enforcer_step")
    if "test_b17_p0_explanation_surface_lock_enforcer.py" not in workflow_text:
        violations.append("ci_missing_b17_negative_control_test_step")
    if "llm_semantic_cache" not in llm_model_file.read_text(encoding="utf-8", errors="ignore"):
        violations.append("llm_model_missing_llm_semantic_cache")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.7-P1 explanation authority lock enforcer")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--attribution-source-file", default="api-contracts/openapi/v1/attribution.yaml")
    parser.add_argument("--attribution-bundle-file", default="api-contracts/dist/openapi/v1/attribution.bundled.yaml")
    parser.add_argument("--noncanonical-source-file", default="api-contracts/openapi/v1/llm-explanations.yaml")
    parser.add_argument("--noncanonical-bundle-file", default="api-contracts/dist/openapi/v1/llm-explanations.bundled.yaml")
    parser.add_argument("--contract-scope-file", default="backend/app/config/contract_scope.yaml")
    parser.add_argument("--semantics-skip-file", default="tests/contract/semantics_skip_allowlist.yaml")
    parser.add_argument("--coverage-manifest-file", default="api-contracts/governance/coverage-manifest.yaml")
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
            "b17_p1_explanation_authority_lock_enforcer\n"
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

    lines = ["b17_p1_explanation_authority_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=canonical_authority_contract_runtime_convergence")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

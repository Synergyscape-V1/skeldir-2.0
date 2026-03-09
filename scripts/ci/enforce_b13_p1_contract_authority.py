#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

REQUIRED_LIFECYCLE_TAG = "Provider OAuth Lifecycle"
LIFECYCLE_PREFIX = "/api/attribution/platform-oauth/"
REQUIRED_SECURITY_SCHEMES = {"accessBearerAuth", "refreshBearerAuth", "tenantKeyAuth"}
REQUIRED_LIFECYCLE_OPERATIONS = {
    ("post", "/api/attribution/platform-oauth/{platform}/authorize"): {
        "scope": "manager",
        "success_status": "202",
    },
    ("get", "/api/attribution/platform-oauth/{platform}/callback"): {
        "scope": "manager",
        "success_status": "200",
    },
    ("get", "/api/attribution/platform-oauth/{platform}/status"): {
        "scope": "viewer",
        "success_status": "200",
    },
    ("post", "/api/attribution/platform-oauth/{platform}/disconnect"): {
        "scope": "manager",
        "success_status": "200",
    },
    ("get", "/api/attribution/platform-oauth/{platform}/refresh-state"): {
        "scope": "viewer",
        "success_status": "200",
    },
}
REQUIRED_PROVIDER_ERROR_CODES = {
    "provider_not_connected",
    "provider_expired",
    "provider_revoked",
    "provider_scope_insufficient",
    "provider_rate_limited",
    "provider_transport_failure",
}
REQUIRED_PROVIDER_ERROR_RESPONSES = {
    "ProviderNotConnectedError": "provider_not_connected",
    "ProviderExpiredError": "provider_expired",
    "ProviderRevokedError": "provider_revoked",
    "ProviderScopeInsufficientError": "provider_scope_insufficient",
    "ProviderRateLimitedError": "provider_rate_limited",
    "ProviderTransportFailureError": "provider_transport_failure",
}
CORRELATION_PARAMETER_REF = "./_common/base.yaml#/components/parameters/CorrelationId"
AUTHORIZATION_PARAMETER_REF = "./_common/base.yaml#/components/parameters/Authorization"
PROBLEM_DETAILS_REF = "./_common/base.yaml#/components/schemas/ProblemDetails"
PROVIDER_PROBLEM_DETAILS_REF = "#/components/schemas/ProviderLifecycleProblemDetails"
PROVIDER_ERROR_CODE_REF = "#/components/schemas/ProviderLifecycleErrorCode"


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"yaml root must be an object: {path}")
    return data


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P1 contract authority enforcement")
    parser.add_argument(
        "--attribution-contract",
        default="api-contracts/openapi/v1/attribution.yaml",
    )
    parser.add_argument(
        "--auth-contract",
        default="api-contracts/openapi/v1/auth.yaml",
    )
    parser.add_argument(
        "--base-contract",
        default="api-contracts/openapi/v1/_common/base.yaml",
    )
    parser.add_argument(
        "--webhook-contract-dir",
        default="api-contracts/openapi/v1/webhooks",
    )
    return parser.parse_args()


def _local_ref_name(ref: str) -> str | None:
    prefix = "#/components/responses/"
    if not ref.startswith(prefix):
        return None
    name = ref.removeprefix(prefix).strip()
    return name or None


def _operation_security_keys(operation: dict) -> set[str]:
    keys: set[str] = set()
    for entry in operation.get("security") or []:
        if not isinstance(entry, dict):
            continue
        for key in entry:
            keys.add(str(key))
    return keys


def _operation_scope(operation: dict, scheme: str) -> list[str] | None:
    for entry in operation.get("security") or []:
        if not isinstance(entry, dict):
            continue
        if scheme in entry and isinstance(entry[scheme], list):
            return [str(item) for item in entry[scheme]]
    return None


def _operation_parameters(operation: dict, path_item: dict) -> list[dict]:
    params: list[dict] = []
    path_params = path_item.get("parameters") or []
    op_params = operation.get("parameters") or []
    for group in (path_params, op_params):
        for entry in group:
            if isinstance(entry, dict):
                params.append(entry)
    return params


def _has_parameter_ref(parameters: list[dict], ref: str) -> bool:
    for entry in parameters:
        if entry.get("$ref") == ref:
            return True
    return False


def _has_platform_path_parameter(parameters: list[dict]) -> bool:
    for entry in parameters:
        if entry.get("name") == "platform" and entry.get("in") == "path" and bool(entry.get("required")):
            return True
    return False


def _resolve_response(response_obj: dict, component_responses: dict) -> dict | None:
    ref = response_obj.get("$ref")
    if not isinstance(ref, str):
        return response_obj
    name = _local_ref_name(ref)
    if name is None:
        return None
    resolved = component_responses.get(name)
    return resolved if isinstance(resolved, dict) else None


def _has_success_example(operation: dict, expected_status: str, component_responses: dict) -> bool:
    responses = operation.get("responses") or {}
    if not isinstance(responses, dict):
        return False
    response_obj = responses.get(expected_status)
    if not isinstance(response_obj, dict):
        return False
    resolved = _resolve_response(response_obj, component_responses)
    if not isinstance(resolved, dict):
        return False
    content = resolved.get("content") or {}
    if not isinstance(content, dict):
        return False
    application_json = content.get("application/json")
    if not isinstance(application_json, dict):
        return False
    if "example" in application_json:
        return True
    examples = application_json.get("examples")
    return isinstance(examples, dict) and len(examples) > 0


def _all_lifecycle_operations(attribution_doc: dict) -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []
    paths = attribution_doc.get("paths") or {}
    if not isinstance(paths, dict):
        return out
    for path, path_item in paths.items():
        if not isinstance(path, str) or not path.startswith(LIFECYCLE_PREFIX):
            continue
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if isinstance(operation, dict):
                out.append((method.lower(), path, operation))
    return out


def _validate_lifecycle_routes(attribution_doc: dict) -> list[str]:
    errors: list[str] = []
    component_responses = (
        attribution_doc.get("components", {}).get("responses", {})
        if isinstance(attribution_doc.get("components"), dict)
        else {}
    )
    paths = attribution_doc.get("paths")
    if not isinstance(paths, dict):
        return ["attribution contract missing paths object"]

    tags = attribution_doc.get("tags") or []
    if not any(
        isinstance(item, dict)
        and item.get("name") == REQUIRED_LIFECYCLE_TAG
        and isinstance(item.get("description"), str)
        and "distinct" in item.get("description", "").lower()
        for item in tags
    ):
        errors.append("missing Provider OAuth Lifecycle tag with explicit boundary description")

    for (method, path), requirement in REQUIRED_LIFECYCLE_OPERATIONS.items():
        path_item = paths.get(path)
        if not isinstance(path_item, dict):
            errors.append(f"missing lifecycle route: {method.upper()} {path}")
            continue
        operation = path_item.get(method)
        if not isinstance(operation, dict):
            errors.append(f"missing lifecycle operation method: {method.upper()} {path}")
            continue
        if not operation.get("operationId"):
            errors.append(f"missing operationId: {method.upper()} {path}")
        op_tags = operation.get("tags") or []
        if REQUIRED_LIFECYCLE_TAG not in op_tags:
            errors.append(f"lifecycle operation missing required tag: {method.upper()} {path}")

        if operation.get("x-auth-boundary") != "provider_oauth_lifecycle":
            errors.append(f"missing x-auth-boundary marker on {method.upper()} {path}")
        disallowed = operation.get("x-disallowed-security-schemes") or []
        disallowed_set = {str(item) for item in disallowed}
        if {"refreshBearerAuth", "tenantKeyAuth"} - disallowed_set:
            errors.append(f"x-disallowed-security-schemes incomplete on {method.upper()} {path}")

        security_keys = _operation_security_keys(operation)
        if security_keys != {"accessBearerAuth"}:
            errors.append(
                f"lifecycle operation security must be accessBearerAuth-only: "
                f"{method.upper()} {path} got={sorted(security_keys)}"
            )
        scopes = _operation_scope(operation, "accessBearerAuth")
        expected_scope = requirement["scope"]
        if scopes != [expected_scope]:
            errors.append(
                f"lifecycle operation scope mismatch on {method.upper()} {path}: "
                f"expected={[expected_scope]} got={scopes}"
            )

        params = _operation_parameters(operation, path_item)
        if not _has_parameter_ref(params, CORRELATION_PARAMETER_REF):
            errors.append(f"missing required X-Correlation-ID parameter on {method.upper()} {path}")
        if not _has_parameter_ref(params, AUTHORIZATION_PARAMETER_REF):
            errors.append(f"missing required Authorization parameter on {method.upper()} {path}")
        if not _has_platform_path_parameter(params):
            errors.append(f"missing required platform path parameter on {method.upper()} {path}")

        success_status = requirement["success_status"]
        if not _has_success_example(operation, success_status, component_responses):
            errors.append(f"missing success example for {success_status} response on {method.upper()} {path}")

    return errors


def _validate_problem_taxonomy(attribution_doc: dict) -> list[str]:
    errors: list[str] = []
    components = attribution_doc.get("components")
    if not isinstance(components, dict):
        return ["attribution contract missing components object"]
    schemas = components.get("schemas")
    responses = components.get("responses")
    if not isinstance(schemas, dict) or not isinstance(responses, dict):
        return ["attribution contract missing components.schemas or components.responses"]

    code_schema = schemas.get("ProviderLifecycleErrorCode")
    if not isinstance(code_schema, dict):
        errors.append("missing ProviderLifecycleErrorCode schema")
    else:
        enum_values = code_schema.get("enum")
        if not isinstance(enum_values, list):
            errors.append("ProviderLifecycleErrorCode.enum missing")
        else:
            enum_set = {str(item) for item in enum_values}
            if enum_set != REQUIRED_PROVIDER_ERROR_CODES:
                errors.append(
                    "ProviderLifecycleErrorCode.enum mismatch: "
                    f"expected={sorted(REQUIRED_PROVIDER_ERROR_CODES)} got={sorted(enum_set)}"
                )

    problem_schema = schemas.get("ProviderLifecycleProblemDetails")
    if not isinstance(problem_schema, dict):
        errors.append("missing ProviderLifecycleProblemDetails schema")
    else:
        all_of = problem_schema.get("allOf")
        if not isinstance(all_of, list):
            errors.append("ProviderLifecycleProblemDetails.allOf missing")
        else:
            has_base_ref = False
            has_code_ref = False
            for item in all_of:
                if not isinstance(item, dict):
                    continue
                if item.get("$ref") == PROBLEM_DETAILS_REF:
                    has_base_ref = True
                props = item.get("properties")
                if isinstance(props, dict):
                    code_prop = props.get("code")
                    if isinstance(code_prop, dict) and code_prop.get("$ref") == PROVIDER_ERROR_CODE_REF:
                        has_code_ref = True
            if not has_base_ref:
                errors.append("ProviderLifecycleProblemDetails must reference shared ProblemDetails base schema")
            if not has_code_ref:
                errors.append("ProviderLifecycleProblemDetails.code must reference ProviderLifecycleErrorCode")

    lifecycle_response_refs_used: set[str] = set()
    for method, path, operation in _all_lifecycle_operations(attribution_doc):
        responses_obj = operation.get("responses")
        if not isinstance(responses_obj, dict):
            errors.append(f"responses missing for lifecycle operation {method.upper()} {path}")
            continue
        has_specific_provider_response = False
        for status_code, response_obj in responses_obj.items():
            if not isinstance(response_obj, dict):
                continue
            ref_value = response_obj.get("$ref")
            if isinstance(ref_value, str):
                if ref_value.endswith("/ServerError") and str(status_code) == "503":
                    errors.append(
                        f"lifecycle 503 response must not collapse to generic ServerError on {method.upper()} {path}"
                    )
                ref_name = _local_ref_name(ref_value)
                if ref_name:
                    lifecycle_response_refs_used.add(ref_name)
                    if ref_name in REQUIRED_PROVIDER_ERROR_RESPONSES:
                        has_specific_provider_response = True
        if not has_specific_provider_response:
            errors.append(
                f"lifecycle operation missing provider-specific ProblemDetails responses: {method.upper()} {path}"
            )

    for response_name, expected_code in REQUIRED_PROVIDER_ERROR_RESPONSES.items():
        response_obj = responses.get(response_name)
        if not isinstance(response_obj, dict):
            errors.append(f"missing response component: {response_name}")
            continue
        content = response_obj.get("content")
        if not isinstance(content, dict):
            errors.append(f"{response_name} missing content object")
            continue
        problem_json = content.get("application/problem+json")
        if not isinstance(problem_json, dict):
            errors.append(f"{response_name} missing application/problem+json content")
            continue
        schema = problem_json.get("schema")
        if not isinstance(schema, dict) or schema.get("$ref") != PROVIDER_PROBLEM_DETAILS_REF:
            errors.append(f"{response_name} must reference ProviderLifecycleProblemDetails schema")
        example = problem_json.get("example")
        if not isinstance(example, dict):
            errors.append(f"{response_name} missing example payload")
            continue
        if example.get("code") != expected_code:
            errors.append(
                f"{response_name} example code mismatch: expected={expected_code} got={example.get('code')}"
            )

    missing_refs = set(REQUIRED_PROVIDER_ERROR_RESPONSES) - lifecycle_response_refs_used
    if missing_refs:
        errors.append(
            f"lifecycle operations do not reference all required provider taxonomy responses: {sorted(missing_refs)}"
        )

    return errors


def _validate_auth_boundaries(
    attribution_doc: dict,
    auth_doc: dict,
    base_doc: dict,
    webhook_docs: list[tuple[str, dict]],
) -> list[str]:
    errors: list[str] = []
    base_schemes = base_doc.get("components", {}).get("securitySchemes", {})
    if not isinstance(base_schemes, dict):
        return ["base contract missing components.securitySchemes"]

    base_scheme_set = {str(key) for key in base_schemes.keys()}
    if base_scheme_set & REQUIRED_SECURITY_SCHEMES != REQUIRED_SECURITY_SCHEMES:
        errors.append(
            "base security schemes missing one or more required auth boundaries: "
            f"required={sorted(REQUIRED_SECURITY_SCHEMES)} got={sorted(base_scheme_set)}"
        )

    attr_schemes = attribution_doc.get("components", {}).get("securitySchemes", {})
    if not isinstance(attr_schemes, dict):
        errors.append("attribution contract missing components.securitySchemes")
    else:
        if "tenantKeyAuth" in attr_schemes or "refreshBearerAuth" in attr_schemes:
            errors.append("attribution contract must not define webhook or refresh security schemes")

    auth_paths = auth_doc.get("paths", {})
    if isinstance(auth_paths, dict):
        collisions = [path for path in auth_paths if isinstance(path, str) and path.startswith(LIFECYCLE_PREFIX)]
        if collisions:
            errors.append(f"auth contract must not define provider lifecycle paths: {sorted(collisions)}")
    else:
        errors.append("auth contract missing paths object")

    for file_name, webhook_doc in webhook_docs:
        paths = webhook_doc.get("paths", {})
        if not isinstance(paths, dict):
            errors.append(f"webhook contract missing paths object: {file_name}")
            continue
        collisions = [path for path in paths if isinstance(path, str) and path.startswith(LIFECYCLE_PREFIX)]
        if collisions:
            errors.append(
                f"webhook contract must not define provider lifecycle paths ({file_name}): {sorted(collisions)}"
            )
        top_security = webhook_doc.get("security")
        has_tenant_key = False
        if isinstance(top_security, list):
            for entry in top_security:
                if isinstance(entry, dict) and "tenantKeyAuth" in entry:
                    has_tenant_key = True
        if not has_tenant_key:
            errors.append(f"webhook contract missing tenantKeyAuth boundary declaration: {file_name}")

    return errors


def _load_webhook_docs(directory: Path) -> list[tuple[str, dict]]:
    docs: list[tuple[str, dict]] = []
    for path in sorted(directory.glob("*.yaml")):
        docs.append((path.name, _load_yaml(path)))
    return docs


def main() -> int:
    args = _parse_args()
    attribution_path = Path(args.attribution_contract)
    auth_path = Path(args.auth_contract)
    base_path = Path(args.base_contract)
    webhook_dir = Path(args.webhook_contract_dir)

    try:
        attribution_doc = _load_yaml(attribution_path)
        auth_doc = _load_yaml(auth_path)
        base_doc = _load_yaml(base_path)
        webhook_docs = _load_webhook_docs(webhook_dir)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"B1.3-P1 contract authority gate failed: {exc}")
        return 1

    if not webhook_docs:
        print("B1.3-P1 contract authority gate failed: no webhook contracts found")
        return 1

    errors: list[str] = []
    errors.extend(_validate_lifecycle_routes(attribution_doc))
    errors.extend(_validate_problem_taxonomy(attribution_doc))
    errors.extend(_validate_auth_boundaries(attribution_doc, auth_doc, base_doc, webhook_docs))

    if errors:
        print("B1.3-P1 contract authority gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P1 contract authority gate passed.")
    print(f"  lifecycle_routes={len(REQUIRED_LIFECYCLE_OPERATIONS)}")
    print(f"  provider_problem_codes={sorted(REQUIRED_PROVIDER_ERROR_CODES)}")
    print("  auth_boundaries=jwt|webhook_hmac|provider_oauth_lifecycle (distinct)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

REQUIRED_CONTEXT = "B1.3 P8 Failure & Baseline Proofs"
REQUIRED_FAILURE_CODES = {
    "provider_expired",
    "provider_revoked",
    "provider_scope_insufficient",
    "provider_rate_limited",
    "provider_transport_failure",
}
REQUIRED_TEST_NAMES = (
    "test_b13_p8_gate_passes_repo_state",
    "test_b13_p8_failure_taxonomy_is_explicit_on_refresh_state_surface",
    "test_b13_p8_terminal_invalid_client_suppresses_refresh_churn",
    "test_b13_p8_reconnectable_degradation_is_explicit_when_connection_has_no_credentials",
    "test_b13_p8_supported_provider_tranche_baseline_is_explicit_and_callable",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P8 failure taxonomy and provider baseline enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--attribution-contract", default="api-contracts/openapi/v1/attribution.yaml")
    parser.add_argument("--oauth-api-file", default="backend/app/api/platform_oauth.py")
    parser.add_argument("--runtime-service-file", default="backend/app/services/provider_oauth_runtime.py")
    parser.add_argument("--refresh-service-file", default="backend/app/services/provider_token_refresh.py")
    parser.add_argument("--adapter-file", default="backend/app/services/provider_oauth_lifecycle.py")
    parser.add_argument("--credential-store-file", default="backend/app/services/platform_credentials.py")
    parser.add_argument(
        "--p0-capability-contract",
        default="contracts-internal/governance/b13_p0_provider_capability_matrix.main.json",
    )
    parser.add_argument(
        "--p5-capability-contract",
        default="contracts-internal/governance/b13_p5_oauth_adapter_capabilities.main.json",
    )
    parser.add_argument("--tests-file", default="backend/tests/test_b13_p8_failure_baseline.py")
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _check_required_context(workflow_text: str, required_checks: dict, errors: list[str]) -> None:
    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")
    contexts = required_checks.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required checks contract missing required_contexts list")
        return
    if REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")


def _check_contract_taxonomy(contract_doc: dict, errors: list[str]) -> None:
    paths = contract_doc.get("paths")
    if not isinstance(paths, dict):
        errors.append("attribution contract missing paths object")
        return
    refresh_state_operation = (paths.get("/api/attribution/platform-oauth/{platform}/refresh-state") or {}).get("get")
    if not isinstance(refresh_state_operation, dict):
        errors.append("attribution contract missing GET /platform-oauth/{platform}/refresh-state operation")

    schemas = (contract_doc.get("components") or {}).get("schemas") or {}
    failure_enum = ((schemas.get("ProviderLifecycleErrorCode") or {}).get("enum")) or []
    missing = REQUIRED_FAILURE_CODES - {str(item) for item in failure_enum}
    if missing:
        errors.append(f"ProviderLifecycleErrorCode missing required values: {sorted(missing)}")


def _check_api_surface(oauth_api_text: str, errors: list[str]) -> None:
    if "/platform-oauth/{platform}/refresh-state" not in oauth_api_text:
        errors.append("platform_oauth api missing /refresh-state route")
    if "operation_id=\"getProviderOAuthRefreshState\"" not in oauth_api_text:
        errors.append("platform_oauth api missing getProviderOAuthRefreshState operation id")
    if "ProviderOAuthRefreshStateResponse" not in oauth_api_text:
        errors.append("platform_oauth api missing refresh-state response model binding")
    if "Depends(require_lifecycle_read_access)" not in oauth_api_text:
        errors.append("platform_oauth api must enforce viewer scope for refresh-state route")


def _check_runtime_service(runtime_text: str, errors: list[str]) -> None:
    required_fragments = (
        "def provider_rate_limited(",
        "def _external_error_code_for_failure_class(",
        "async def get_refresh_state(",
        "provider_rate_limited(",
        "provider_scope_insufficient(",
        "provider_transport_failure(",
        "provider_revoked(",
    )
    for fragment in required_fragments:
        if fragment not in runtime_text:
            errors.append(f"runtime service missing required P8 failure handling fragment: {fragment}")
    if "_REFRESH_FAILURE_TO_EXTERNAL_CODE" not in runtime_text:
        errors.append("runtime service missing canonical refresh failure translation table")


def _check_refresh_orchestration(
    refresh_text: str,
    adapter_text: str,
    credential_store_text: str,
    errors: list[str],
) -> None:
    if "provider_invalid_client" not in adapter_text:
        errors.append("adapter layer missing provider_invalid_client failure classification")
    if "status=\"revoked_terminal\"" not in refresh_text:
        errors.append("refresh orchestration missing revoked_terminal execution status")
    if "mark_revoked(" not in refresh_text:
        errors.append("refresh orchestration missing mark_revoked call for terminal failures")
    if "lifecycle_status.in_((\"active\", \"degraded\"))" not in credential_store_text:
        errors.append("credential due-selection must exclude revoked credentials")
    if "next_refresh_due_at=None" not in credential_store_text:
        errors.append("revoked credential mutation must clear next_refresh_due_at")


def _check_supported_tranche(p0_contract: dict, p5_contract: dict, errors: list[str]) -> None:
    runtime_backed = {
        str(value).strip()
        for value in p0_contract.get("runtime_backed_providers", [])
        if str(value).strip()
    }
    if not runtime_backed:
        errors.append("p0 capability contract has empty runtime_backed_providers")

    adapter_capabilities = p5_contract.get("adapter_capabilities")
    if not isinstance(adapter_capabilities, list):
        errors.append("p5 capability contract missing adapter_capabilities list")
        return
    runtime_modes = {
        str(item.get("provider")).strip()
        for item in adapter_capabilities
        if isinstance(item, dict) and str(item.get("mode")).strip() == "runtime_backed"
    }
    if runtime_modes != runtime_backed:
        errors.append(
            "supported runtime-backed provider tranche mismatch between P0 and P5 contracts: "
            f"p0={sorted(runtime_backed)} p5={sorted(runtime_modes)}"
        )


def _check_tests_surface(test_text: str, errors: list[str]) -> None:
    for test_name in REQUIRED_TEST_NAMES:
        if test_name not in test_text:
            errors.append(f"P8 proof suite missing required test: {test_name}")


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "contract": Path(args.attribution_contract),
        "oauth_api": Path(args.oauth_api_file),
        "runtime_service": Path(args.runtime_service_file),
        "refresh_service": Path(args.refresh_service_file),
        "adapter": Path(args.adapter_file),
        "credential_store": Path(args.credential_store_file),
        "p0_capability": Path(args.p0_capability_contract),
        "p5_capability": Path(args.p5_capability_contract),
        "tests": Path(args.tests_file),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P8 failure & baseline gate failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    required_checks = _load_json(paths["required_checks"])
    contract_doc = _load_yaml(paths["contract"])
    oauth_api_text = _read_text(paths["oauth_api"])
    runtime_service_text = _read_text(paths["runtime_service"])
    refresh_service_text = _read_text(paths["refresh_service"])
    adapter_text = _read_text(paths["adapter"])
    credential_store_text = _read_text(paths["credential_store"])
    p0_capability = _load_json(paths["p0_capability"])
    p5_capability = _load_json(paths["p5_capability"])
    tests_text = _read_text(paths["tests"])

    errors: list[str] = []
    _check_required_context(workflow_text, required_checks, errors)
    _check_contract_taxonomy(contract_doc, errors)
    _check_api_surface(oauth_api_text, errors)
    _check_runtime_service(runtime_service_text, errors)
    _check_refresh_orchestration(refresh_service_text, adapter_text, credential_store_text, errors)
    _check_supported_tranche(p0_capability, p5_capability, errors)
    _check_tests_surface(tests_text, errors)

    if errors:
        print("B1.3-P8 failure & baseline gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P8 failure & baseline gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print(f"  required_failure_codes={sorted(REQUIRED_FAILURE_CODES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

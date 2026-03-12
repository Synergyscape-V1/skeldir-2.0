#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

REQUIRED_CONTEXT = "B1.3 P6 Runtime Lifecycle Proofs"
REQUIRED_ROUTES = (
    "/platform-oauth/{platform}/authorize",
    "/platform-oauth/{platform}/callback",
    "/platform-oauth/{platform}/status",
    "/platform-oauth/{platform}/disconnect",
)
REQUIRED_OPERATION_IDS = (
    "initiateProviderOAuthAuthorization",
    "completeProviderOAuthCallback",
    "getProviderOAuthStatus",
    "disconnectProviderOAuth",
)
PROVIDER_LITERAL_PATTERN = re.compile(
    r"\b(?:if|elif)\s+platform(?:_key)?\s*==\s*['\"](stripe|dummy|paypal|shopify|woocommerce|google_ads|meta_ads|tiktok_ads|linkedin_ads)['\"]"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P6 runtime lifecycle enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--main-file", default="backend/app/main.py")
    parser.add_argument("--oauth-api-file", default="backend/app/api/platform_oauth.py")
    parser.add_argument("--runtime-service-file", default="backend/app/services/provider_oauth_runtime.py")
    parser.add_argument("--dispatcher-file", default="backend/app/services/oauth_lifecycle_dispatcher.py")
    parser.add_argument("--attribution-contract", default="api-contracts/openapi/v1/attribution.yaml")
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


def _check_route_registration(main_text: str, errors: list[str]) -> None:
    if "platform_oauth.router" not in main_text:
        errors.append("main router composition missing platform_oauth.router registration")
    if 'prefix="/api/attribution"' not in main_text:
        errors.append("main router composition missing /api/attribution prefix for OAuth lifecycle routes")


def _check_api_router_structure(oauth_api_text: str, errors: list[str]) -> None:
    for route in REQUIRED_ROUTES:
        if route not in oauth_api_text:
            errors.append(f"platform_oauth api missing route declaration: {route}")
    for operation_id in REQUIRED_OPERATION_IDS:
        if operation_id not in oauth_api_text:
            errors.append(f"platform_oauth api missing operationId binding: {operation_id}")

    if oauth_api_text.count("Depends(require_lifecycle_mutation_access)") < 3:
        errors.append("platform_oauth api must enforce manager mutation scope on authorize/callback/disconnect")
    if "Depends(require_lifecycle_read_access)" not in oauth_api_text:
        errors.append("platform_oauth api must enforce viewer scope on status route")

    if PROVIDER_LITERAL_PATTERN.search(oauth_api_text):
        errors.append("provider-specific branching detected in platform_oauth api")

    if "provider_raw_body" in oauth_api_text or "access_token" in oauth_api_text:
        errors.append("platform_oauth api must not expose raw provider payloads or token material")


def _check_runtime_service_structure(runtime_text: str, errors: list[str]) -> None:
    required_dispatch_calls = (
        "self._dispatcher.build_authorize_url(",
        "self._dispatcher.validate_callback_state(",
        "self._dispatcher.exchange_auth_code(",
        "self._dispatcher.fetch_account_metadata(",
        "self._dispatcher.revoke_disconnect(",
    )
    for call in required_dispatch_calls:
        if call not in runtime_text:
            errors.append(f"runtime service missing dispatcher seam call: {call}")

    consume_index = runtime_text.find("OAuthHandshakeStateService.consume_session(")
    durable_upsert_index = runtime_text.find("PlatformCredentialStore.upsert_tokens(")
    if consume_index < 0:
        errors.append("runtime service missing callback consume_session usage")
    elif durable_upsert_index < 0:
        errors.append("runtime service missing durable credential upsert")
    elif consume_index > durable_upsert_index:
        errors.append("callback durable write occurs before transient consume validation")

    if "self._dispatcher.refresh_token(" in runtime_text:
        errors.append("P6 phase collapse: runtime service must not orchestrate refresh scheduling/token-refresh loops")
    if "app.tasks" in runtime_text or "beat_schedule" in runtime_text:
        errors.append("P6 phase collapse: runtime service must not bind worker scheduling")

    for handshake_error in (
        "OAuthHandshakeStateBindingError",
        "OAuthHandshakeStateNotFoundError",
        "OAuthHandshakeStateReplayError",
        "OAuthHandshakeStateExpiredError",
    ):
        if handshake_error not in runtime_text:
            errors.append(f"runtime service missing handshake failure handling: {handshake_error}")

    if PROVIDER_LITERAL_PATTERN.search(runtime_text):
        errors.append("provider-specific branching detected in runtime service")


def _check_contract_authority(contract_doc: dict, errors: list[str]) -> None:
    paths = contract_doc.get("paths")
    if not isinstance(paths, dict):
        errors.append("attribution contract missing paths object")
        return

    expected_contract_routes = {
        "/api/attribution/platform-oauth/{platform}/authorize": "post",
        "/api/attribution/platform-oauth/{platform}/callback": "get",
        "/api/attribution/platform-oauth/{platform}/status": "get",
        "/api/attribution/platform-oauth/{platform}/disconnect": "post",
    }
    for route, method in expected_contract_routes.items():
        operation = (paths.get(route) or {}).get(method)
        if not isinstance(operation, dict):
            errors.append(f"attribution contract missing lifecycle operation: {method.upper()} {route}")


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "main": Path(args.main_file),
        "oauth_api": Path(args.oauth_api_file),
        "runtime_service": Path(args.runtime_service_file),
        "dispatcher": Path(args.dispatcher_file),
        "attribution_contract": Path(args.attribution_contract),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P6 runtime lifecycle gate failed:")
        for path in missing:
            print(f"  - missing file: {path}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    required_checks = _load_json(paths["required_checks"])
    main_text = _read_text(paths["main"])
    oauth_api_text = _read_text(paths["oauth_api"])
    runtime_text = _read_text(paths["runtime_service"])
    dispatcher_text = _read_text(paths["dispatcher"])
    contract_doc = _load_yaml(paths["attribution_contract"])

    errors: list[str] = []
    _check_required_context(workflow_text, required_checks, errors)
    _check_route_registration(main_text, errors)
    _check_api_router_structure(oauth_api_text, errors)
    _check_runtime_service_structure(runtime_text, errors)
    _check_contract_authority(contract_doc, errors)

    if "class ProviderOAuthLifecycleDispatcher" not in dispatcher_text:
        errors.append("dispatcher seam file missing ProviderOAuthLifecycleDispatcher class")

    if errors:
        print("B1.3-P6 runtime lifecycle gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P6 runtime lifecycle gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print("  routes=authorize|callback|status|disconnect registered and contract-aligned")
    print("  callback_flow=consume_transient_then_durable_write")
    print("  dispatch=provider-neutral dispatcher seam")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

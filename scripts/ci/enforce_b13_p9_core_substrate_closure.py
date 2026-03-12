#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CONTEXT = "B1.3 P9 Core Substrate Closure Proofs"
REQUIRED_TEST_NAMES = (
    "test_b13_p9_gate_passes_repo_state",
    "test_b13_p9_composed_lifecycle_closure_with_deterministic_and_stripe_paths",
    "test_b13_p9_cross_tenant_and_tenantless_worker_fail_before_side_effects",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P9 core substrate closure enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--tests-file", default="backend/tests/integration/test_b13_p9_core_substrate_closure.py")
    parser.add_argument("--oauth-api-file", default="backend/app/api/platform_oauth.py")
    parser.add_argument("--runtime-service-file", default="backend/app/services/provider_oauth_runtime.py")
    parser.add_argument("--adapter-file", default="backend/app/services/provider_oauth_lifecycle.py")
    parser.add_argument("--refresh-service-file", default="backend/app/services/provider_token_refresh.py")
    parser.add_argument("--resolver-file", default="backend/app/services/provider_valid_token_resolution.py")
    parser.add_argument("--maintenance-task-file", default="backend/app/tasks/maintenance.py")
    parser.add_argument("--enqueue-file", default="backend/app/tasks/enqueue.py")
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_required_context(workflow_text: str, required_checks: dict, errors: list[str]) -> None:
    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")
    contexts = required_checks.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required checks contract missing required_contexts list")
        return
    if REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")


def _check_workflow_surface(workflow_text: str, errors: list[str]) -> None:
    required_fragments = (
        "name: B1.3 P9 Core Substrate Closure Proofs",
        "python scripts/ci/enforce_b13_p9_core_substrate_closure.py",
        "pytest backend/tests/integration/test_b13_p9_core_substrate_closure.py -q",
        "name: b13-p9-runtime-artifacts",
        "path: artifacts/b13_p9",
    )
    for fragment in required_fragments:
        if fragment not in workflow_text:
            errors.append(f"workflow missing P9 closure fragment: {fragment}")


def _check_runtime_surface(
    *,
    oauth_api_text: str,
    runtime_text: str,
    adapter_text: str,
    refresh_text: str,
    resolver_text: str,
    maintenance_text: str,
    enqueue_text: str,
    errors: list[str],
) -> None:
    api_fragments = (
        "/platform-oauth/{platform}/authorize",
        "/platform-oauth/{platform}/callback",
        "/platform-oauth/{platform}/status",
        "/platform-oauth/{platform}/refresh-state",
        "/platform-oauth/{platform}/disconnect",
    )
    for fragment in api_fragments:
        if fragment not in oauth_api_text:
            errors.append(f"platform_oauth api missing lifecycle route: {fragment}")

    runtime_fragments = (
        "async def initiate_authorization(",
        "async def complete_callback(",
        "async def get_status(",
        "async def get_refresh_state(",
        "async def disconnect(",
    )
    for fragment in runtime_fragments:
        if fragment not in runtime_text:
            errors.append(f"runtime lifecycle service missing fragment: {fragment}")

    adapter_fragments = (
        "class DeterministicOAuthLifecycleAdapter",
        "class StripeOAuthLifecycleAdapter",
    )
    for fragment in adapter_fragments:
        if fragment not in adapter_text:
            errors.append(f"adapter layer missing required provider surface: {fragment}")

    refresh_fragments = (
        "async def claim_due_credentials_for_tenant(",
        "async def refresh_credential_once(",
        "pg_try_advisory_xact_lock",
        "status=\"revoked_terminal\"",
    )
    for fragment in refresh_fragments:
        if fragment not in refresh_text:
            errors.append(f"refresh orchestration service missing fragment: {fragment}")

    resolver_fragments = (
        "class ProviderValidTokenResolver",
        "app.tasks.maintenance.refresh_provider_oauth_credential",
    )
    for fragment in resolver_fragments:
        if fragment not in resolver_text:
            errors.append(f"valid-token resolver missing fragment: {fragment}")

    maintenance_fragments = (
        "name=\"app.tasks.maintenance.refresh_provider_oauth_credential\"",
        "name=\"app.tasks.maintenance.schedule_provider_oauth_refresh_for_tenant\"",
    )
    for fragment in maintenance_fragments:
        if fragment not in maintenance_text:
            errors.append(f"maintenance task surface missing fragment: {fragment}")

    if "app.tasks.maintenance.refresh_provider_oauth_credential" not in enqueue_text:
        errors.append("tenant enqueue registry missing refresh_provider_oauth_credential")


def _check_tests_surface(test_text: str, errors: list[str]) -> None:
    for test_name in REQUIRED_TEST_NAMES:
        if test_name not in test_text:
            errors.append(f"P9 proof suite missing required test: {test_name}")

    required_fragments = (
        'platform="dummy"',
        "platform=Platform.stripe",
        "_run_scheduled_refresh_for_credential(",
        "ProviderValidTokenResolver",
        "disconnect_provider_oauth(",
        "authority_envelope header is required",
        "refresh_provider_oauth_credential.apply(",
        "SystemAuthorityEnvelope",
        "_write_artifact(",
    )
    for fragment in required_fragments:
        if fragment not in test_text:
            errors.append(f"P9 proof suite missing closure fragment: {fragment}")


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "tests": Path(args.tests_file),
        "oauth_api": Path(args.oauth_api_file),
        "runtime_service": Path(args.runtime_service_file),
        "adapter": Path(args.adapter_file),
        "refresh_service": Path(args.refresh_service_file),
        "resolver": Path(args.resolver_file),
        "maintenance": Path(args.maintenance_task_file),
        "enqueue": Path(args.enqueue_file),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P9 core substrate closure gate failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    required_checks = _load_json(paths["required_checks"])
    tests_text = _read_text(paths["tests"])
    oauth_api_text = _read_text(paths["oauth_api"])
    runtime_text = _read_text(paths["runtime_service"])
    adapter_text = _read_text(paths["adapter"])
    refresh_text = _read_text(paths["refresh_service"])
    resolver_text = _read_text(paths["resolver"])
    maintenance_text = _read_text(paths["maintenance"])
    enqueue_text = _read_text(paths["enqueue"])

    errors: list[str] = []
    _check_required_context(workflow_text, required_checks, errors)
    _check_workflow_surface(workflow_text, errors)
    _check_runtime_surface(
        oauth_api_text=oauth_api_text,
        runtime_text=runtime_text,
        adapter_text=adapter_text,
        refresh_text=refresh_text,
        resolver_text=resolver_text,
        maintenance_text=maintenance_text,
        enqueue_text=enqueue_text,
        errors=errors,
    )
    _check_tests_surface(tests_text, errors)

    if errors:
        print("B1.3-P9 core substrate closure gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P9 core substrate closure gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print("  composed_chain=authorize->callback->encrypted_store->refresh->use->revoke/fail")
    print("  negatives=cross_tenant + tenantless_worker + non_leak")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

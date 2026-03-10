#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

REQUIRED_CONTEXT = "B1.3 P4 Boundary Hardening Proofs"
FORBIDDEN_RUNTIME_LIFECYCLE_MARKERS = (
    "/platform-oauth/",
    "initiateProviderOAuthAuthorization",
    "disconnectProviderOAuth",
    "/callback",
)
ALLOWED_SECRET_PATHS = {
    "backend/app/core/secrets.py",
    "backend/app/core/config.py",
    "backend/app/core/managed_settings_contract.py",
}
DIRECT_SECRET_ACCESS_PATTERNS = (
    re.compile(r"settings\.PLATFORM_TOKEN_ENCRYPTION_KEY"),
    re.compile(r"os\.getenv\(\s*[\"']PLATFORM_TOKEN_ENCRYPTION_KEY[\"']\s*\)"),
    re.compile(r"os\.environ\[\s*[\"']PLATFORM_TOKEN_ENCRYPTION_KEY[\"']\s*\]"),
    re.compile(r"settings\.[A-Z0-9_]*CLIENT_SECRET"),
    re.compile(r"os\.getenv\(\s*[\"'][A-Z0-9_]*CLIENT_SECRET[\"']\s*\)"),
    re.compile(r"os\.environ\[\s*[\"'][A-Z0-9_]*CLIENT_SECRET[\"']\s*\]"),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P4 boundary hardening enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--platforms-api-file", default="backend/app/api/platforms.py")
    parser.add_argument("--secret-core-file", default="backend/app/core/secrets.py")
    parser.add_argument("--platform-credentials-file", default="backend/app/services/platform_credentials.py")
    parser.add_argument("--oauth-handshake-file", default="backend/app/services/oauth_handshake_state.py")
    parser.add_argument("--webhook-secret-file", default="backend/app/services/tenant_webhook_secrets.py")
    parser.add_argument("--enqueue-file", default="backend/app/tasks/enqueue.py")
    parser.add_argument("--logging-file", default="backend/app/observability/logging_config.py")
    parser.add_argument("--problem-details-file", default="backend/app/api/problem_details.py")
    parser.add_argument("--boundary-module-file", default="backend/app/security/secret_boundary.py")
    parser.add_argument("--lifecycle-auth-file", default="backend/app/security/lifecycle_authorization.py")
    parser.add_argument("--attribution-contract", default="api-contracts/openapi/v1/attribution.yaml")
    parser.add_argument("--app-root", default="backend/app")
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_function_block(source: str, function_name: str) -> str:
    marker = f"def {function_name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_router = source.find("\n\n@router", start + len(marker))
    next_def = source.find("\ndef ", start + len(marker))
    endings = [candidate for candidate in (next_router, next_def) if candidate >= 0]
    end = min(endings) if endings else len(source)
    return source[start:end]


def _check_required_context(workflow_text: str, required_checks: dict, errors: list[str]) -> None:
    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")

    contexts = required_checks.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required status checks contract missing required_contexts list")
        return
    if REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")


def _assert_contract_scope(
    contract_doc: dict,
    *,
    path: str,
    method: str,
    expected_scope: str,
    errors: list[str],
) -> None:
    paths = contract_doc.get("paths")
    if not isinstance(paths, dict):
        errors.append("attribution contract missing paths object")
        return
    path_item = paths.get(path)
    if not isinstance(path_item, dict):
        errors.append(f"attribution contract missing path: {path}")
        return
    operation = path_item.get(method)
    if not isinstance(operation, dict):
        errors.append(f"attribution contract missing method {method.upper()} {path}")
        return
    security = operation.get("security")
    if not isinstance(security, list):
        errors.append(f"attribution contract missing security for {method.upper()} {path}")
        return
    found = False
    for item in security:
        if not isinstance(item, dict):
            continue
        scopes = item.get("accessBearerAuth")
        if isinstance(scopes, list):
            if scopes == [expected_scope]:
                found = True
            break
    if not found:
        errors.append(
            f"attribution contract scope mismatch on {method.upper()} {path}: expected {[expected_scope]}"
        )


def _check_platform_rbac(platforms_text: str, errors: list[str]) -> None:
    connection_block = _extract_function_block(platforms_text, "upsert_platform_connection")
    credentials_block = _extract_function_block(platforms_text, "upsert_platform_credentials")
    read_block = _extract_function_block(platforms_text, "get_platform_connection")

    if not connection_block:
        errors.append("platforms api missing upsert_platform_connection")
    elif "Depends(require_lifecycle_mutation_access)" not in connection_block:
        errors.append("upsert_platform_connection must require lifecycle mutation access")

    if not credentials_block:
        errors.append("platforms api missing upsert_platform_credentials")
    elif "Depends(require_lifecycle_mutation_access)" not in credentials_block:
        errors.append("upsert_platform_credentials must require lifecycle mutation access")

    if not read_block:
        errors.append("platforms api missing get_platform_connection")
    elif "Depends(require_lifecycle_read_access)" not in read_block:
        errors.append("get_platform_connection must require lifecycle read access")

    for marker in FORBIDDEN_RUNTIME_LIFECYCLE_MARKERS:
        if marker in platforms_text:
            errors.append(f"phase-collapse marker found in runtime platforms api: {marker}")


def _check_secret_path_exclusivity(
    *,
    repo_root: Path,
    app_root: Path,
    platform_credentials_text: str,
    oauth_handshake_text: str,
    webhook_secret_text: str,
    errors: list[str],
) -> None:
    if "resolve_platform_encryption_key_by_id" not in platform_credentials_text:
        errors.append("platform_credentials must resolve key material through app/core/secrets.py")
    if "get_platform_encryption_material_for_write" not in oauth_handshake_text:
        errors.append("oauth_handshake_state must fetch write key through app/core/secrets.py")
    if "resolve_platform_encryption_key_by_id" not in oauth_handshake_text:
        errors.append("oauth_handshake_state must resolve key-id through app/core/secrets.py")
    if "resolve_platform_encryption_key_by_id" not in webhook_secret_text:
        errors.append("tenant_webhook_secrets must resolve key-id through app/core/secrets.py")
    if 'row.get(f"{provider}_webhook_secret")' in webhook_secret_text:
        errors.append("legacy plaintext webhook secret fallback must be removed")

    for path in sorted(app_root.rglob("*.py")):
        rel = path.resolve().relative_to(repo_root).as_posix()
        if rel in ALLOWED_SECRET_PATHS:
            continue
        text = _read_text(path)
        for pattern in DIRECT_SECRET_ACCESS_PATTERNS:
            if pattern.search(text):
                errors.append(f"direct secret/client-secret access found outside choke point: {rel} ({pattern.pattern})")


def _check_structural_non_leak(
    *,
    logging_text: str,
    enqueue_text: str,
    problem_details_text: str,
    boundary_module_text: str,
    errors: list[str],
) -> None:
    if "def assert_no_sensitive_material" not in boundary_module_text:
        errors.append("secret boundary module missing assert_no_sensitive_material")
    if "FORBIDDEN_LIFECYCLE_KEYS" not in boundary_module_text:
        errors.append("secret boundary module missing lifecycle forbidden key set")
    if "FORBIDDEN_RAW_PROVIDER_BODY_KEYS" not in boundary_module_text:
        errors.append("secret boundary module missing raw provider body forbidden key set")

    if "sanitize_for_transport" not in logging_text:
        errors.append("logging config must structurally sanitize payloads before serialization")
    if "assert_no_sensitive_material(task_kwargs" not in enqueue_text:
        errors.append("enqueue must reject sensitive task payload kwargs structurally")
    if "sanitize_problem_detail" not in problem_details_text:
        errors.append("problem details output must sanitize sensitive detail material")
    if "sanitize_for_transport(errors)" not in problem_details_text:
        errors.append("problem details output must sanitize structured error payloads")


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "platforms": Path(args.platforms_api_file),
        "secret_core": Path(args.secret_core_file),
        "platform_credentials": Path(args.platform_credentials_file),
        "oauth_handshake": Path(args.oauth_handshake_file),
        "webhook_secret": Path(args.webhook_secret_file),
        "enqueue": Path(args.enqueue_file),
        "logging": Path(args.logging_file),
        "problem_details": Path(args.problem_details_file),
        "boundary_module": Path(args.boundary_module_file),
        "lifecycle_auth": Path(args.lifecycle_auth_file),
        "attribution_contract": Path(args.attribution_contract),
        "app_root": Path(args.app_root),
    }

    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P4 boundary hardening gate failed:")
        for path in missing:
            print(f"  - missing file: {path}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    platforms_text = _read_text(paths["platforms"])
    platform_credentials_text = _read_text(paths["platform_credentials"])
    oauth_handshake_text = _read_text(paths["oauth_handshake"])
    webhook_secret_text = _read_text(paths["webhook_secret"])
    enqueue_text = _read_text(paths["enqueue"])
    logging_text = _read_text(paths["logging"])
    problem_details_text = _read_text(paths["problem_details"])
    boundary_module_text = _read_text(paths["boundary_module"])
    required_checks = json.loads(paths["required_checks"].read_text(encoding="utf-8"))
    attribution_doc = yaml.safe_load(paths["attribution_contract"].read_text(encoding="utf-8"))

    errors: list[str] = []

    _check_required_context(workflow_text, required_checks, errors)
    _check_platform_rbac(platforms_text, errors)
    _check_secret_path_exclusivity(
        repo_root=Path.cwd().resolve(),
        app_root=paths["app_root"],
        platform_credentials_text=platform_credentials_text,
        oauth_handshake_text=oauth_handshake_text,
        webhook_secret_text=webhook_secret_text,
        errors=errors,
    )
    _check_structural_non_leak(
        logging_text=logging_text,
        enqueue_text=enqueue_text,
        problem_details_text=problem_details_text,
        boundary_module_text=boundary_module_text,
        errors=errors,
    )
    _assert_contract_scope(
        attribution_doc,
        path="/api/attribution/platform-connections",
        method="post",
        expected_scope="manager",
        errors=errors,
    )
    _assert_contract_scope(
        attribution_doc,
        path="/api/attribution/platform-credentials",
        method="post",
        expected_scope="manager",
        errors=errors,
    )
    _assert_contract_scope(
        attribution_doc,
        path="/api/attribution/platform-connections/{platform}",
        method="get",
        expected_scope="viewer",
        errors=errors,
    )

    if "require_lifecycle_mutation_access" not in _read_text(paths["lifecycle_auth"]):
        errors.append("lifecycle authorization primitive missing mutation dependency")
    if "require_lifecycle_read_access" not in _read_text(paths["lifecycle_auth"]):
        errors.append("lifecycle authorization primitive missing read dependency")

    if errors:
        print("B1.3-P4 boundary hardening gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P4 boundary hardening gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print("  rbac=mutation(manager)|read(viewer)")
    print("  secret_path=core.secrets exclusive for lifecycle key resolution")
    print("  non_leak=logging|problem_details|task_enqueue structural guards active")
    print("  phase_collapse_guard=P6 runtime handlers remain absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

REQUIRED_CONTEXT = "B1.3 P5 Adapter Layer Proofs"
REQUIRED_METHODS = (
    "build_authorize_url",
    "validate_callback_state",
    "exchange_auth_code",
    "refresh_token",
    "revoke_disconnect",
    "fetch_account_metadata",
)
FORBIDDEN_HTTP_MODULES = ("httpx", "requests", "aiohttp", "urllib3")
PROVIDER_LITERAL_PATTERN = re.compile(
    r"['\"](stripe|dummy|shopify|paypal|woocommerce|google_ads|meta_ads|tiktok_ads|linkedin_ads)['\"]"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P5 adapter-layer structural enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--p0-capability-contract",
        default="contracts-internal/governance/b13_p0_provider_capability_matrix.main.json",
    )
    parser.add_argument(
        "--p5-capability-contract",
        default="contracts-internal/governance/b13_p5_oauth_adapter_capabilities.main.json",
    )
    parser.add_argument("--adapter-file", default="backend/app/services/provider_oauth_lifecycle.py")
    parser.add_argument("--dispatcher-file", default="backend/app/services/oauth_lifecycle_dispatcher.py")
    parser.add_argument("--api-root", default="backend/app/api")
    parser.add_argument(
        "--api-files",
        nargs="*",
        default=None,
        help="Optional explicit API files for provider-branching checks.",
    )
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _class_methods(tree: ast.Module, class_name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name != "__init__"
            }
    return set()


def _class_exists(tree: ast.Module, class_name: str) -> bool:
    return any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body)


def _extract_literal_assignment(tree: ast.Module, name: str) -> object | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        try:
            return ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != name:
            continue
        if node.value is None:
            return None
        try:
            return ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            return None
    return None


def _extract_registry_adapter_constructors(tree: ast.Module) -> list[str]:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "DEFAULT_OAUTH_LIFECYCLE_REGISTRY" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call):
            return []
        adapters: list[str] = []
        for keyword in node.value.keywords:
            if keyword.arg != "adapters" or not isinstance(keyword.value, ast.List):
                continue
            for item in keyword.value.elts:
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
                    adapters.append(item.func.id)
            return adapters
    return []


def _extract_method_block(source: str, method_name: str) -> str:
    marker = f"async def {method_name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_marker = source.find("\n    async def ", start + len(marker))
    if next_marker < 0:
        next_marker = len(source)
    return source[start:next_marker]


def _scan_provider_branching(path: Path, errors: list[str]) -> None:
    for lineno, line in enumerate(_read_text(path).splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.search(r"\bif\s+platform\s*==\s*['\"]", stripped):
            errors.append(f"provider-specific platform branch in API file: {path}:{lineno}")
        if re.search(r"\bmatch\s+platform\b", stripped):
            errors.append(f"match-platform branch in API file: {path}:{lineno}")
        if re.search(r"\bcase\s+['\"]", stripped) and PROVIDER_LITERAL_PATTERN.search(stripped):
            errors.append(f"provider-specific match-case branch in API file: {path}:{lineno}")


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".", 1)[0])
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".", 1)[0])
    return modules


def _check_required_context(workflow_text: str, required_checks: dict, errors: list[str]) -> None:
    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")
    contexts = required_checks.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required status checks contract missing required_contexts list")
        return
    if REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")


def _normalize_contract_capabilities(data: list[dict]) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    for item in data:
        provider = str(item.get("provider") or "").strip()
        if not provider:
            continue
        normalized[provider] = {
            "mode": str(item.get("mode") or "").strip(),
            "adapter_kind": str(item.get("adapter_kind") or "").strip(),
            "supports_authorize_url": bool(item.get("supports_authorize_url")),
            "supports_callback_state_validation": bool(item.get("supports_callback_state_validation")),
            "supports_code_exchange": bool(item.get("supports_code_exchange")),
            "supports_token_refresh": bool(item.get("supports_token_refresh")),
            "supports_revoke_disconnect": bool(item.get("supports_revoke_disconnect")),
            "supports_account_metadata": bool(item.get("supports_account_metadata")),
        }
    return normalized


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "p0_contract": Path(args.p0_capability_contract),
        "p5_contract": Path(args.p5_capability_contract),
        "adapter": Path(args.adapter_file),
        "dispatcher": Path(args.dispatcher_file),
        "api_root": Path(args.api_root),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P5 adapter-layer gate failed:")
        for path in missing:
            print(f"  - missing file: {path}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    required_checks = _load_json(paths["required_checks"])
    p0_contract = _load_json(paths["p0_contract"])
    p5_contract = _load_json(paths["p5_contract"])
    adapter_text = _read_text(paths["adapter"])
    dispatcher_text = _read_text(paths["dispatcher"])

    adapter_tree = ast.parse(adapter_text, filename=str(paths["adapter"]))
    dispatcher_tree = ast.parse(dispatcher_text, filename=str(paths["dispatcher"]))

    errors: list[str] = []
    _check_required_context(workflow_text, required_checks, errors)

    adapter_interface_methods = _class_methods(adapter_tree, "OAuthLifecycleAdapter")
    if set(REQUIRED_METHODS) != adapter_interface_methods:
        errors.append(
            "OAuthLifecycleAdapter method set mismatch: "
            f"expected={sorted(REQUIRED_METHODS)} actual={sorted(adapter_interface_methods)}"
        )

    if not _class_exists(adapter_tree, "OAuthLifecycleRegistry"):
        errors.append("missing OAuthLifecycleRegistry class")
    if not _class_exists(adapter_tree, "DeterministicOAuthLifecycleAdapter"):
        errors.append("missing DeterministicOAuthLifecycleAdapter class")
    if not _class_exists(adapter_tree, "StripeOAuthLifecycleAdapter"):
        errors.append("missing StripeOAuthLifecycleAdapter class")

    imported_modules = _imported_modules(adapter_tree)
    forbidden_imports = sorted(
        module for module in imported_modules if module in FORBIDDEN_HTTP_MODULES
    )
    if forbidden_imports:
        errors.append(
            "P5 adapter outbound HTTP firewall violated: forbidden HTTP client imports "
            f"in adapter file {paths['adapter']}: {forbidden_imports}"
        )

    declarations = _extract_literal_assignment(adapter_tree, "OAUTH_LIFECYCLE_CAPABILITY_DECLARATIONS")
    if not isinstance(declarations, dict):
        errors.append("unable to parse OAUTH_LIFECYCLE_CAPABILITY_DECLARATIONS as dict literal")
        declarations = {}

    declaration_map: dict[str, dict[str, object]] = {}
    for key, value in declarations.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        declaration_map[key] = {
            "mode": str(value.get("mode") or "").strip(),
            "adapter_kind": str(value.get("adapter_kind") or "").strip(),
            "supports_authorize_url": bool(value.get("supports_authorize_url")),
            "supports_callback_state_validation": bool(value.get("supports_callback_state_validation")),
            "supports_code_exchange": bool(value.get("supports_code_exchange")),
            "supports_token_refresh": bool(value.get("supports_token_refresh")),
            "supports_revoke_disconnect": bool(value.get("supports_revoke_disconnect")),
            "supports_account_metadata": bool(value.get("supports_account_metadata")),
        }

    contract_capabilities = p5_contract.get("adapter_capabilities")
    if not isinstance(contract_capabilities, list):
        errors.append("P5 capability contract missing adapter_capabilities list")
        contract_capabilities = []
    normalized_contract_map = _normalize_contract_capabilities(contract_capabilities)
    if declaration_map != normalized_contract_map:
        errors.append(
            "adapter code capability declarations differ from P5 capability contract: "
            f"code={sorted(declaration_map)} contract={sorted(normalized_contract_map)}"
        )

    contract_methods = p5_contract.get("canonical_lifecycle_methods")
    if not isinstance(contract_methods, list):
        errors.append("P5 capability contract missing canonical_lifecycle_methods list")
        contract_methods = []
    if list(contract_methods) != list(REQUIRED_METHODS):
        errors.append(
            "canonical_lifecycle_methods mismatch in P5 capability contract: "
            f"expected={list(REQUIRED_METHODS)} actual={list(contract_methods)}"
        )

    runtime_backed = {
        str(value).strip() for value in p0_contract.get("runtime_backed_providers", []) if str(value).strip()
    }
    internal_only = {
        str(value).strip()
        for value in p0_contract.get("runtime_internal_only_providers", [])
        if str(value).strip()
    }
    provider_modes = p0_contract.get("provider_modes")
    if not isinstance(provider_modes, dict):
        errors.append("P0 capability matrix missing provider_modes object")
        provider_modes = {}

    expected_providers = runtime_backed | internal_only
    declared_providers = set(declaration_map)
    contract_declared_providers = set(normalized_contract_map)
    if declared_providers != expected_providers:
        errors.append(
            "P5 adapter providers must match P0 runtime-backed + internal providers: "
            f"expected={sorted(expected_providers)} actual={sorted(declared_providers)}"
        )
    if contract_declared_providers != expected_providers:
        errors.append(
            "P5 capability contract providers must match P0 runtime-backed + internal providers: "
            f"expected={sorted(expected_providers)} actual={sorted(contract_declared_providers)}"
        )

    for provider in sorted(declaration_map):
        mode = declaration_map[provider].get("mode")
        expected_mode = provider_modes.get(provider)
        if mode != expected_mode:
            errors.append(
                f"provider mode mismatch for {provider}: expected={expected_mode} actual={mode}"
            )
        for key in (
            "supports_authorize_url",
            "supports_callback_state_validation",
            "supports_code_exchange",
            "supports_token_refresh",
            "supports_revoke_disconnect",
            "supports_account_metadata",
        ):
            if declaration_map[provider].get(key) is not True:
                errors.append(f"provider capability '{provider}.{key}' must be true")

    deterministic_providers = [
        provider
        for provider, payload in declaration_map.items()
        if payload.get("adapter_kind") == "deterministic_reference"
    ]
    if len(deterministic_providers) != 1:
        errors.append(
            "expected exactly one deterministic_reference adapter capability declaration"
        )
    elif deterministic_providers[0] not in internal_only:
        errors.append("deterministic_reference adapter must map to an internal_runtime_only provider")

    adapter_constructors = _extract_registry_adapter_constructors(adapter_tree)
    if "DeterministicOAuthLifecycleAdapter" not in adapter_constructors:
        errors.append("DEFAULT_OAUTH_LIFECYCLE_REGISTRY missing DeterministicOAuthLifecycleAdapter registration")

    dispatcher_methods = _class_methods(dispatcher_tree, "ProviderOAuthLifecycleDispatcher")
    if set(REQUIRED_METHODS) != dispatcher_methods:
        errors.append(
            "ProviderOAuthLifecycleDispatcher method set mismatch: "
            f"expected={sorted(REQUIRED_METHODS)} actual={sorted(dispatcher_methods)}"
        )
    for method_name in REQUIRED_METHODS:
        block = _extract_method_block(dispatcher_text, method_name)
        if not block:
            errors.append(f"unable to isolate dispatcher method block: {method_name}")
            continue
        if "self._registry.get_adapter(platform)" not in block:
            errors.append(f"dispatcher method '{method_name}' must resolve adapter via registry.get_adapter(platform)")
        if re.search(r"\bif\s+platform\s*==\s*['\"]", block) or re.search(r"\bmatch\s+platform\b", block):
            errors.append(f"dispatcher method '{method_name}' contains provider-specific branching")

    if args.api_files:
        api_files = [Path(entry) for entry in args.api_files]
    else:
        api_files = sorted(Path(args.api_root).glob("*.py"))
    for api_file in api_files:
        if not api_file.exists():
            errors.append(f"api file for branching scan not found: {api_file}")
            continue
        _scan_provider_branching(api_file, errors)

    if errors:
        print("B1.3-P5 adapter-layer gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P5 adapter-layer gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print(f"  adapter_interface_methods={list(REQUIRED_METHODS)}")
    print(f"  providers={sorted(declaration_map)}")
    print(f"  deterministic_reference={deterministic_providers[0] if deterministic_providers else 'missing'}")
    print("  outbound_http=forbidden_in_p5_adapter")
    print("  dispatch=registry-backed and provider-branch free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

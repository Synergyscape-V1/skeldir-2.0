#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path, PurePosixPath

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


class ScopeTruthError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ScopeTruthError(f"YAML root must be an object: {path}")
    return data


def _parse_openapi_platform_enum(path: Path) -> set[str]:
    doc = _load_yaml(path)
    enum_values = (
        doc.get("components", {})
        .get("schemas", {})
        .get("Platform", {})
        .get("enum", [])
    )
    if not isinstance(enum_values, list) or not enum_values:
        raise ScopeTruthError(f"Unable to read Platform enum from {path}")
    values = {str(item).strip() for item in enum_values if str(item).strip()}
    if not values:
        raise ScopeTruthError(f"Platform enum empty in {path}")
    return values


def _parse_openapi_security_schemes(path: Path) -> set[str]:
    doc = _load_yaml(path)
    schemes = doc.get("components", {}).get("securitySchemes", {})
    if not isinstance(schemes, dict):
        raise ScopeTruthError(f"securitySchemes is not an object in {path}")
    return {str(key).strip() for key in schemes.keys() if str(key).strip()}


def _const_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _parse_settings_supported_platforms(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "Settings":
            continue
        for item in node.body:
            if not isinstance(item, ast.AnnAssign):
                continue
            if not isinstance(item.target, ast.Name) or item.target.id != "PLATFORM_SUPPORTED_PLATFORMS":
                continue
            value = item.value
            if not isinstance(value, ast.Call):
                break
            raw: str | None = None
            if value.args:
                raw = _const_string(value.args[0])
            if raw is None:
                for keyword in value.keywords:
                    if keyword.arg == "default":
                        raw = _const_string(keyword.value)
                        break
            if raw is None:
                break
            parsed = {entry.strip() for entry in raw.split(",") if entry.strip()}
            if not parsed:
                raise ScopeTruthError("PLATFORM_SUPPORTED_PLATFORMS default parsed empty")
            return parsed

    raise ScopeTruthError(f"Could not parse PLATFORM_SUPPORTED_PLATFORMS default from {path}")


def _parse_registry_provider_keys(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    class_to_key: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "provider_key":
                    value = _const_string(item.value)
                    if value:
                        class_to_key[node.name] = value

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "DEFAULT_PROVIDER_REGISTRY" for t in node.targets):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "ProviderRegistry":
            raise ScopeTruthError("DEFAULT_PROVIDER_REGISTRY is not ProviderRegistry(...) call")

        provider_nodes: list[ast.AST] = []
        for keyword in value.keywords:
            if keyword.arg == "providers" and isinstance(keyword.value, ast.List):
                provider_nodes = list(keyword.value.elts)
                break
        if not provider_nodes:
            raise ScopeTruthError("DEFAULT_PROVIDER_REGISTRY providers list not found")

        keys: set[str] = set()
        for provider_node in provider_nodes:
            if not isinstance(provider_node, ast.Call) or not isinstance(provider_node.func, ast.Name):
                raise ScopeTruthError("ProviderRegistry providers must be constructor calls")
            cls_name = provider_node.func.id
            if cls_name not in class_to_key:
                raise ScopeTruthError(f"Missing provider_key for class {cls_name}")
            keys.add(class_to_key[cls_name])
        return keys

    raise ScopeTruthError(f"DEFAULT_PROVIDER_REGISTRY assignment not found in {path}")


def _parse_webhook_verifiers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "WEBHOOK_VERIFIERS":
            continue
        if not isinstance(node.value, ast.Dict):
            raise ScopeTruthError("WEBHOOK_VERIFIERS must be a dict literal")
        keys: set[str] = set()
        for key_node in node.value.keys:
            key = _const_string(key_node) if key_node is not None else None
            if key:
                keys.add(key)
        if not keys:
            raise ScopeTruthError("WEBHOOK_VERIFIERS has no provider keys")
        return keys

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "WEBHOOK_VERIFIERS" for t in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            raise ScopeTruthError("WEBHOOK_VERIFIERS must be a dict literal")
        keys: set[str] = set()
        for key_node in node.value.keys:
            key = _const_string(key_node) if key_node is not None else None
            if key:
                keys.add(key)
        if not keys:
            raise ScopeTruthError("WEBHOOK_VERIFIERS has no provider keys")
        return keys

    raise ScopeTruthError(f"WEBHOOK_VERIFIERS not found in {path}")


def _parse_webhook_contract_provider_keys(path: Path) -> set[str]:
    if not path.exists() or not path.is_dir():
        raise ScopeTruthError(f"Webhook contract directory not found: {path}")
    keys = {item.stem for item in path.glob("*.yaml") if item.is_file()}
    if not keys:
        raise ScopeTruthError(f"No webhook contracts found in {path}")
    return keys


def _as_set(data: dict, key: str, *, required: bool = True) -> set[str]:
    value = data.get(key)
    if value is None:
        if required:
            raise ScopeTruthError(f"Missing key in capability contract: {key}")
        return set()
    if not isinstance(value, list):
        raise ScopeTruthError(f"Contract key must be a list: {key}")
    parsed = {str(item).strip() for item in value if str(item).strip()}
    if required and not parsed:
        raise ScopeTruthError(f"Contract list is empty: {key}")
    return parsed


def _validate_provider_modes(contract: dict, connection: set[str], internal_only: set[str]) -> list[str]:
    errors: list[str] = []
    modes = contract.get("provider_modes")
    if not isinstance(modes, dict):
        return ["provider_modes missing or not an object"]

    expected_keys = connection | internal_only
    actual_keys = {str(key) for key in modes.keys()}
    if actual_keys != expected_keys:
        errors.append(
            "provider_modes keys mismatch: "
            f"expected={sorted(expected_keys)} actual={sorted(actual_keys)}"
        )

    for provider, mode in modes.items():
        provider_str = str(provider)
        mode_str = str(mode)
        if provider_str in connection and mode_str not in {"runtime_backed", "future_rollout"}:
            errors.append(f"provider_modes[{provider_str}] must be runtime_backed|future_rollout")
        if provider_str in internal_only and mode_str != "internal_runtime_only":
            errors.append(f"provider_modes[{provider_str}] must be internal_runtime_only")

    return errors


def _check_contract_sorting(data: dict, keys: list[str]) -> list[str]:
    errors: list[str] = []
    for key in keys:
        value = data.get(key)
        if not isinstance(value, list):
            continue
        raw = [str(item) for item in value]
        if raw != sorted(raw):
            errors.append(f"{key} must be sorted for deterministic diffs")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="B1.3-P0 scope-truth structural enforcement")
    parser.add_argument(
        "--capability-contract",
        default="contracts-internal/governance/b13_p0_provider_capability_matrix.main.json",
    )
    parser.add_argument(
        "--attribution-contract",
        default="api-contracts/openapi/v1/attribution.yaml",
    )
    parser.add_argument(
        "--base-contract",
        default="api-contracts/openapi/v1/_common/base.yaml",
    )
    parser.add_argument(
        "--settings-file",
        default="backend/app/core/config.py",
    )
    parser.add_argument(
        "--registry-file",
        default="backend/app/services/realtime_revenue_providers.py",
    )
    parser.add_argument(
        "--webhooks-file",
        default="backend/app/api/webhooks.py",
    )
    parser.add_argument(
        "--webhook-contract-dir",
        default="api-contracts/openapi/v1/webhooks",
    )
    args = parser.parse_args()

    contract_path = (REPO_ROOT / args.capability_contract).resolve()
    attribution_contract_path = (REPO_ROOT / args.attribution_contract).resolve()
    base_contract_path = (REPO_ROOT / args.base_contract).resolve()
    settings_path = (REPO_ROOT / args.settings_file).resolve()
    registry_path = (REPO_ROOT / args.registry_file).resolve()
    webhooks_path = (REPO_ROOT / args.webhooks_file).resolve()
    webhook_contract_dir = (REPO_ROOT / args.webhook_contract_dir).resolve()

    try:
        capability_contract = _load_json(contract_path)
        openapi_platforms = _parse_openapi_platform_enum(attribution_contract_path)
        settings_platforms = _parse_settings_supported_platforms(settings_path)
        registry_providers = _parse_registry_provider_keys(registry_path)
        webhook_py_providers = _parse_webhook_verifiers(webhooks_path)
        webhook_contract_providers = _parse_webhook_contract_provider_keys(webhook_contract_dir)
        security_schemes = _parse_openapi_security_schemes(base_contract_path)
    except (ScopeTruthError, FileNotFoundError, json.JSONDecodeError, yaml.YAMLError, SyntaxError) as exc:
        print(f"B1.3-P0 scope truth gate failed: {exc}")
        return 1

    errors: list[str] = []

    try:
        runtime_backed = _as_set(capability_contract, "runtime_backed_providers")
        internal_only = _as_set(capability_contract, "runtime_internal_only_providers")
        connection_substrate = _as_set(capability_contract, "connection_substrate_providers")
        future_rollout = _as_set(capability_contract, "future_rollout_targets")
        webhook_hmac = _as_set(capability_contract, "webhook_hmac_providers")
    except ScopeTruthError as exc:
        print(f"B1.3-P0 scope truth gate failed: {exc}")
        return 1

    errors.extend(
        _check_contract_sorting(
            capability_contract,
            [
                "runtime_backed_providers",
                "runtime_internal_only_providers",
                "connection_substrate_providers",
                "future_rollout_targets",
                "webhook_hmac_providers",
            ],
        )
    )

    if connection_substrate != openapi_platforms:
        errors.append(
            "connection_substrate_providers mismatch with OpenAPI Platform enum: "
            f"contract={sorted(connection_substrate)} openapi={sorted(openapi_platforms)}"
        )

    if connection_substrate != settings_platforms:
        errors.append(
            "connection_substrate_providers mismatch with PLATFORM_SUPPORTED_PLATFORMS default: "
            f"contract={sorted(connection_substrate)} settings={sorted(settings_platforms)}"
        )

    if not internal_only.issubset(registry_providers):
        errors.append(
            "runtime_internal_only_providers must be a subset of DEFAULT_PROVIDER_REGISTRY: "
            f"internal_only={sorted(internal_only)} registry={sorted(registry_providers)}"
        )

    if connection_substrate & internal_only:
        errors.append(
            "runtime_internal_only_providers must not overlap connection_substrate_providers: "
            f"overlap={sorted(connection_substrate & internal_only)}"
        )

    expected_runtime_backed = registry_providers - internal_only
    if runtime_backed != expected_runtime_backed:
        errors.append(
            "runtime_backed_providers mismatch with runtime registry truth: "
            f"contract={sorted(runtime_backed)} runtime={sorted(expected_runtime_backed)}"
        )

    expected_future = connection_substrate - runtime_backed
    if future_rollout != expected_future:
        errors.append(
            "future_rollout_targets must equal connection_substrate minus runtime_backed: "
            f"contract={sorted(future_rollout)} expected={sorted(expected_future)}"
        )

    if webhook_hmac != webhook_py_providers:
        errors.append(
            "webhook_hmac_providers mismatch with backend WEBHOOK_VERIFIERS: "
            f"contract={sorted(webhook_hmac)} backend={sorted(webhook_py_providers)}"
        )

    if webhook_hmac != webhook_contract_providers:
        errors.append(
            "webhook_hmac_providers mismatch with webhook OpenAPI contracts: "
            f"contract={sorted(webhook_hmac)} contracts={sorted(webhook_contract_providers)}"
        )

    excluded = capability_contract.get(
        "first_party_identity_oauth_surfaces_excluded_from_b13_provider_lifecycle",
        {},
    )
    if not isinstance(excluded, dict):
        errors.append(
            "first_party_identity_oauth_surfaces_excluded_from_b13_provider_lifecycle must be an object"
        )
    else:
        excluded_schemes = {
            str(item).strip() for item in excluded.get("security_schemes", []) if str(item).strip()
        }
        if "accessBearerAuth" not in excluded_schemes:
            errors.append(
                "Excluded first-party OAuth surfaces must include accessBearerAuth"
            )
        if not excluded_schemes.issubset(security_schemes):
            errors.append(
                "Excluded security schemes must exist in OpenAPI base securitySchemes: "
                f"excluded={sorted(excluded_schemes)} available={sorted(security_schemes)}"
            )
        docs_routes = {
            str(item).strip() for item in excluded.get("docs_routes", []) if str(item).strip()
        }
        if "/docs/oauth2-redirect" not in docs_routes:
            errors.append(
                "Excluded first-party OAuth docs routes must include /docs/oauth2-redirect"
            )

    errors.extend(_validate_provider_modes(capability_contract, connection_substrate, internal_only))

    if errors:
        print("B1.3-P0 scope truth gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P0 scope truth gate passed.")
    print(f"  connection_substrate_providers={sorted(connection_substrate)}")
    print(f"  runtime_backed_providers={sorted(runtime_backed)}")
    print(f"  runtime_internal_only_providers={sorted(internal_only)}")
    print(f"  webhook_hmac_providers={sorted(webhook_hmac)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

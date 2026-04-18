#!/usr/bin/env python3
"""B2.2-P0 webhook surface authority convergence enforcer."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DECLARED_SURFACE_CONTRACT = (
    "contracts-internal/governance/b22_p0_declared_webhook_surface.main.json"
)
SEMANTICS_SKIP_ALLOWLIST = "tests/contract/semantics_skip_allowlist.yaml"
CI_WORKFLOW = ".github/workflows/ci.yml"
ROUTE_FIDELITY_TEST = "tests/contract/test_route_fidelity.py"
TYPEGEN_SCRIPT = "scripts/contracts/generate_frontend_types.sh"
BUNDLE_SCRIPT = "scripts/contracts/bundle.sh"

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(path)) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML payload must be an object: {path}")
    return payload


def _extract_openapi_webhook_ops(payload: dict[str, Any]) -> set[str]:
    operations: set[str] = set()
    for path, methods in (payload.get("paths") or {}).items():
        if not str(path).startswith("/api/webhooks/"):
            continue
        if not isinstance(methods, dict):
            continue
        for method in methods:
            lowered = str(method).lower()
            if lowered in HTTP_METHODS:
                operations.add(f"{lowered.upper()} {path}")
    return operations


def _extract_typegen_webhook_ops(path: Path) -> set[str]:
    pattern = re.compile(r'^\s*"(/api/webhooks/[^\"]+)":\s*\{')
    operations: set[str] = set()
    for line in _read_text(path).splitlines():
        match = pattern.search(line)
        if match:
            operations.add(f"POST {match.group(1)}")
    return operations


def _extract_runtime_webhook_ops(repo_root: Path) -> tuple[set[str], set[str]]:
    backend_root = repo_root / "backend"
    sys.path.insert(0, str(backend_root.resolve()))
    from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

    os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
    os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
    os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
    os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
    os.environ.setdefault(
        "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
    )
    os.environ.setdefault(
        "MIGRATION_DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
    )
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("CONTRACT_TESTING", "1")

    from app.main import app

    runtime_routes: set[str] = set()
    for route in app.routes:
        if not hasattr(route, "path") or not hasattr(route, "methods"):
            continue
        if not str(route.path).startswith("/api/webhooks/"):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            runtime_routes.add(f"{method} {route.path}")

    runtime_openapi_doc = app.openapi() or {}
    runtime_openapi = _extract_openapi_webhook_ops(runtime_openapi_doc)
    return runtime_routes, runtime_openapi


def _compare_set(
    *,
    name: str,
    observed: set[str],
    declared: set[str],
    violations: list[str],
) -> None:
    missing = sorted(declared - observed)
    extra = sorted(observed - declared)
    if missing:
        violations.append(f"{name}_missing_declared:{'|'.join(missing)}")
    if extra:
        violations.append(f"{name}_contains_undeclared:{'|'.join(extra)}")


def run_enforcement(
    *,
    repo_root: Path,
    declared_surface_contract: Path,
    semantics_skip_allowlist: Path,
    ci_workflow: Path,
    route_fidelity_test: Path,
    typegen_script: Path,
    bundle_script: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_paths = (
        declared_surface_contract,
        semantics_skip_allowlist,
        ci_workflow,
        route_fidelity_test,
        typegen_script,
        bundle_script,
    )
    for path in required_paths:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")

    if violations:
        return 1, violations

    contract = _read_json(declared_surface_contract)
    declared_operations_raw = contract.get("operations")
    if not isinstance(declared_operations_raw, list) or not declared_operations_raw:
        violations.append("declared_surface_contract_missing_operations")
        return 1, violations

    declared_surface: set[str] = set()
    source_contract_paths: set[Path] = set()
    bundle_paths: set[Path] = set()
    generated_type_paths: set[Path] = set()

    for operation in declared_operations_raw:
        if not isinstance(operation, dict):
            violations.append("declared_surface_operation_not_object")
            continue
        method = str(operation.get("method", "")).upper().strip()
        path = str(operation.get("path", "")).strip()
        if method not in {m.upper() for m in HTTP_METHODS}:
            violations.append(f"invalid_declared_method:{method}")
            continue
        if not path.startswith("/api/webhooks/"):
            violations.append(f"invalid_declared_path:{path}")
            continue

        declared_surface.add(f"{method} {path}")
        source_contract_paths.add(_resolve(repo_root, str(operation.get("source_contract", ""))))
        bundle_paths.add(_resolve(repo_root, str(operation.get("bundle", ""))))
        generated_type_paths.add(_resolve(repo_root, str(operation.get("generated_type", ""))))

    if len(declared_surface) != len(declared_operations_raw):
        violations.append("declared_surface_contains_duplicates")

    for source_path in source_contract_paths:
        if not source_path.exists():
            violations.append(f"missing_declared_source_contract:{source_path}")
    for bundle_path in bundle_paths:
        if not bundle_path.exists():
            violations.append(f"missing_declared_bundle:{bundle_path}")
    for type_path in generated_type_paths:
        if not type_path.exists():
            violations.append(f"missing_declared_generated_type:{type_path}")

    if violations:
        return 1, violations

    runtime_routes, runtime_openapi = _extract_runtime_webhook_ops(repo_root)
    _compare_set(
        name="runtime_routes",
        observed=runtime_routes,
        declared=declared_surface,
        violations=violations,
    )
    _compare_set(
        name="runtime_openapi",
        observed=runtime_openapi,
        declared=declared_surface,
        violations=violations,
    )

    source_surface: set[str] = set()
    for source_path in source_contract_paths:
        payload = _read_yaml(source_path)
        source_surface.update(_extract_openapi_webhook_ops(payload))
    _compare_set(
        name="source_contracts",
        observed=source_surface,
        declared=declared_surface,
        violations=violations,
    )

    bundle_surface: set[str] = set()
    for bundle_path in bundle_paths:
        payload = _read_yaml(bundle_path)
        bundle_surface.update(_extract_openapi_webhook_ops(payload))
    _compare_set(
        name="bundled_contracts",
        observed=bundle_surface,
        declared=declared_surface,
        violations=violations,
    )

    typegen_surface: set[str] = set()
    for type_path in generated_type_paths:
        typegen_surface.update(_extract_typegen_webhook_ops(type_path))
    _compare_set(
        name="generated_types",
        observed=typegen_surface,
        declared=declared_surface,
        violations=violations,
    )

    allowlist_doc = _read_yaml(semantics_skip_allowlist)
    bundles = allowlist_doc.get("bundles") or {}
    if not isinstance(bundles, dict):
        violations.append("semantics_skip_allowlist_bundles_must_be_mapping")
    else:
        webhook_bundles = sorted(
            key for key in bundles.keys() if str(key).startswith("webhooks.")
        )
        if webhook_bundles:
            violations.append(
                "semantics_skip_allowlist_contains_webhook_bundles:"
                + "|".join(webhook_bundles)
            )

    ci_text = _read_text(ci_workflow)
    required_ci_tokens = (
        "python scripts/ci/enforce_b22_p0_webhook_surface_lock.py",
        "pytest backend/tests/test_b22_p0_webhook_surface_lock_enforcer.py -q",
    )
    for token in required_ci_tokens:
        if token not in ci_text:
            violations.append(f"ci_missing_webhook_surface_lock_token:{token}")

    route_fidelity_text = _read_text(route_fidelity_test)
    if "webhook_contract_drift_is_merge_blocking" not in route_fidelity_text:
        violations.append("route_fidelity_missing_webhook_drift_guard")

    typegen_text = _read_text(typegen_script)
    required_typegen_tokens = (
        'generate "webhooks.shopify.bundled.yaml" "webhooks-shopify.ts"',
        'generate "webhooks.stripe.bundled.yaml" "webhooks-stripe.ts"',
        'generate "webhooks.woocommerce.bundled.yaml" "webhooks-woocommerce.ts"',
        'generate "webhooks.paypal.bundled.yaml" "webhooks-paypal.ts"',
    )
    for token in required_typegen_tokens:
        if token not in typegen_text:
            violations.append(f"typegen_missing_webhook_token:{token}")

    bundle_text = _read_text(bundle_script)
    required_bundle_tokens = (
        "shopify_webhook",
        "woocommerce_webhook",
        "stripe_webhook",
        "paypal_webhook",
    )
    for token in required_bundle_tokens:
        if token not in bundle_text:
            violations.append(f"bundle_script_missing_webhook_token:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.2-P0 webhook authority convergence and declared surface lock."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument(
        "--declared-surface-contract", default=DECLARED_SURFACE_CONTRACT
    )
    parser.add_argument("--semantics-skip-allowlist", default=SEMANTICS_SKIP_ALLOWLIST)
    parser.add_argument("--ci-workflow", default=CI_WORKFLOW)
    parser.add_argument("--route-fidelity-test", default=ROUTE_FIDELITY_TEST)
    parser.add_argument("--typegen-script", default=TYPEGEN_SCRIPT)
    parser.add_argument("--bundle-script", default=BUNDLE_SCRIPT)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b22_p0_webhook_surface_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        declared_surface_contract=_resolve(repo_root, args.declared_surface_contract),
        semantics_skip_allowlist=_resolve(repo_root, args.semantics_skip_allowlist),
        ci_workflow=_resolve(repo_root, args.ci_workflow),
        route_fidelity_test=_resolve(repo_root, args.route_fidelity_test),
        typegen_script=_resolve(repo_root, args.typegen_script),
        bundle_script=_resolve(repo_root, args.bundle_script),
    )
    lines = ["b22_p0_webhook_surface_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=declared_runtime_contract_bundle_typegen_webhook_surface_converged")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

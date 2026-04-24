#!/usr/bin/env python3
"""B2.3-P0 typed-boundary source alignment enforcement.

Verifies that OpenAPI source paths/methods for investigations + budget are mounted
in FastAPI runtime and represented in generated frontend contract artifacts.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi.routing import APIRoute


REPO_ROOT = Path(__file__).resolve().parents[2]
INVESTIGATIONS_SPEC_FILE = "api-contracts/openapi/v1/llm-investigations.yaml"
BUDGET_SPEC_FILE = "api-contracts/openapi/v1/llm-budget.yaml"
GENERATED_INVESTIGATIONS_TYPES_FILE = "frontend/src/types/api/llm-investigations.ts"
GENERATED_BUDGET_TYPES_FILE = "frontend/src/types/api/llm-budget.ts"
CONTRACT_GATE_FILE = "frontend/src/contract-consumption-gate.ts"
REQUIRED_CONTRACT_GATE_OPERATION_IDS = (
    "createInvestigation",
    "getInvestigationStatus",
    "getInvestigationResult",
    "createBudgetOptimization",
    "getBudgetRecommendationStatus",
    "getBudgetRecommendation",
)


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}


def _extract_spec_operations(payload: dict[str, Any]) -> set[tuple[str, str, str]]:
    operations: set[tuple[str, str, str]] = set()
    paths = payload.get("paths") or {}
    if not isinstance(paths, dict):
        return operations
    for path, methods in paths.items():
        if not isinstance(path, str) or not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if not isinstance(method, str) or method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                continue
            operation_id = ""
            if isinstance(operation, dict):
                operation_id = str(operation.get("operationId") or "").strip()
            operations.add((method.upper(), path, operation_id))
    return operations


def _load_fastapi_runtime_route_pairs() -> set[tuple[str, str]]:
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres"
    )
    os.environ.setdefault(
        "MIGRATION_DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
    )
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("CONTRACT_TESTING", "1")
    os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
    backend_root = REPO_ROOT / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from app.main import app  # Imported late so env defaults are in place.

    route_pairs: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                route_pairs.add((method, route.path))
    return route_pairs


def run_enforcement(
    *,
    investigations_spec_file: Path,
    budget_spec_file: Path,
    generated_investigations_types_file: Path,
    generated_budget_types_file: Path,
    contract_gate_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        investigations_spec_file,
        budget_spec_file,
        generated_investigations_types_file,
        generated_budget_types_file,
        contract_gate_file,
    )
    missing = [path for path in required_files if not path.exists()]
    if missing:
        return 1, [f"missing_file:{path}" for path in missing]

    investigations_spec = _read_yaml(investigations_spec_file)
    budget_spec = _read_yaml(budget_spec_file)
    spec_ops = _extract_spec_operations(investigations_spec) | _extract_spec_operations(budget_spec)
    if not spec_ops:
        violations.append("spec_operations_empty")
        return 1, violations

    runtime_route_pairs = _load_fastapi_runtime_route_pairs()
    for method, path, operation_id in sorted(spec_ops):
        if (method, path) not in runtime_route_pairs:
            violations.append(f"missing_runtime_route:{method}:{path}:{operation_id}")
        if not operation_id:
            violations.append(f"missing_operation_id:{method}:{path}")

    investigations_types = generated_investigations_types_file.read_text(encoding="utf-8")
    budget_types = generated_budget_types_file.read_text(encoding="utf-8")
    contract_gate = contract_gate_file.read_text(encoding="utf-8")
    spec_operation_ids = {operation_id for _, _, operation_id in spec_ops if operation_id}
    for _, path, operation_id in sorted(spec_ops):
        if not operation_id:
            continue
        if path.startswith("/api/investigations"):
            if operation_id not in investigations_types:
                violations.append(f"missing_generated_operation:{operation_id}")
        if path.startswith("/api/budget"):
            if operation_id not in budget_types:
                violations.append(f"missing_generated_operation:{operation_id}")
    for operation_id in REQUIRED_CONTRACT_GATE_OPERATION_IDS:
        if operation_id not in spec_operation_ids:
            violations.append(f"required_contract_gate_operation_not_in_spec:{operation_id}")
        if operation_id not in contract_gate:
            violations.append(f"missing_contract_gate_operation:{operation_id}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.3-P0 typed-boundary source alignment."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--investigations-spec-file", default=INVESTIGATIONS_SPEC_FILE)
    parser.add_argument("--budget-spec-file", default=BUDGET_SPEC_FILE)
    parser.add_argument(
        "--generated-investigations-types-file",
        default=GENERATED_INVESTIGATIONS_TYPES_FILE,
    )
    parser.add_argument(
        "--generated-budget-types-file",
        default=GENERATED_BUDGET_TYPES_FILE,
    )
    parser.add_argument("--contract-gate-file", default=CONTRACT_GATE_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b23_p0_typed_boundary_source_alignment_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        investigations_spec_file=_resolve(repo_root, args.investigations_spec_file),
        budget_spec_file=_resolve(repo_root, args.budget_spec_file),
        generated_investigations_types_file=_resolve(
            repo_root, args.generated_investigations_types_file
        ),
        generated_budget_types_file=_resolve(repo_root, args.generated_budget_types_file),
        contract_gate_file=_resolve(repo_root, args.contract_gate_file),
    )

    lines = ["b23_p0_typed_boundary_source_alignment_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=source_openapi_runtime_routes_generated_contracts_aligned")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

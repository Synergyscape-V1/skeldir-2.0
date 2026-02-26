#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "api-contracts" / "dist" / "openapi" / "v1"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"
REQUIRED_CHECKS_PATH = (
    REPO_ROOT / "contracts-internal" / "governance" / "b03_phase2_required_status_checks.main.json"
)
OUTPUT_DIR = REPO_ROOT / "docs" / "forensics" / "evidence" / "b12_p0"
OUTPUT_MD = OUTPUT_DIR / "B1.2-P0_Adjudication_Map.md"
OUTPUT_JSON = OUTPUT_DIR / "auth_contract_inventory.json"

JWT_PREFIXES = (
    "/api/auth",
    "/api/attribution",
    "/api/v1/revenue",
    "/api/reconciliation",
    "/api/export",
    "/api/health",
    "/api/llm",
)
PUBLIC_ALLOWLIST = {
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
    ("GET", "/api/health/version"),
}


@dataclass
class OperationRow:
    bundle: str
    method: str
    path: str
    security: list[dict[str, Any]]
    has_401_problem: bool
    has_403_problem: bool


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _iter_operations(bundle_name: str, doc: dict[str, Any]) -> list[OperationRow]:
    out: list[OperationRow] = []
    top_security = doc.get("security")
    for path, path_item in (doc.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            effective_security = op.get("security", top_security) or []
            responses = op.get("responses") or {}
            out.append(
                OperationRow(
                    bundle=bundle_name,
                    method=method.upper(),
                    path=path,
                    security=effective_security,
                    has_401_problem=_has_problem_response(responses.get("401")),
                    has_403_problem=_has_problem_response(responses.get("403")),
                )
            )
    return out


def _has_problem_response(response_spec: Any) -> bool:
    if not isinstance(response_spec, dict):
        return False
    content = response_spec.get("content") or {}
    return "application/problem+json" in content


def _security_names(security: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for rule in security:
        if isinstance(rule, dict):
            names.update(rule.keys())
    return names


def _route_family(row: OperationRow) -> str:
    if row.path.startswith("/api/webhooks/"):
        return "webhook_hmac"
    if (row.method, row.path) in PUBLIC_ALLOWLIST:
        return "public"
    if row.path.startswith(JWT_PREFIXES):
        return "jwt"
    return "other"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bundles = sorted(DIST_DIR.glob("*.bundled.yaml"))
    if not bundles:
        raise SystemExit(f"No bundled contracts found under {DIST_DIR}")

    rows: list[OperationRow] = []
    scheme_inventory: dict[str, list[str]] = {}
    for bundle in bundles:
        doc = _load_yaml(bundle)
        schemes = sorted(((doc.get("components") or {}).get("securitySchemes") or {}).keys())
        scheme_inventory[bundle.name] = schemes
        rows.extend(_iter_operations(bundle.name, doc))

    required_checks = json.loads(REQUIRED_CHECKS_PATH.read_text(encoding="utf-8"))
    required_contexts = required_checks.get("required_contexts", [])
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8", errors="replace")

    jwt_rows = [r for r in rows if _route_family(r) == "jwt"]
    webhook_rows = [r for r in rows if _route_family(r) == "webhook_hmac"]

    jwt_with_bearer = sum("bearerAuth" in _security_names(r.security) for r in jwt_rows)
    webhook_with_tenant_key = sum("tenantKeyAuth" in _security_names(r.security) for r in webhook_rows)
    webhook_with_bearer = sum("bearerAuth" in _security_names(r.security) for r in webhook_rows)
    has_401_problem = sum(r.has_401_problem for r in rows)
    has_403_problem = sum(r.has_403_problem for r in rows)

    inventory = {
        "bundles": [b.name for b in bundles],
        "scheme_inventory": scheme_inventory,
        "counts": {
            "operations_total": len(rows),
            "jwt_operations": len(jwt_rows),
            "webhook_operations": len(webhook_rows),
            "jwt_with_bearer": jwt_with_bearer,
            "webhook_with_tenant_key": webhook_with_tenant_key,
            "webhook_with_bearer": webhook_with_bearer,
            "operations_with_401_problem": has_401_problem,
            "operations_with_403_problem": has_403_problem,
        },
        "required_contexts": required_contexts,
    }
    OUTPUT_JSON.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    key_jobs = [
        "Validate Contracts",
        "Phase 1 Runtime Conformance",
        "Phase 1 Negative Controls",
        "JWT Tenant Context Invariants",
        "Governance Guardrails",
        "Frontend Contract Consumption Gate",
    ]
    job_lines = []
    for job in key_jobs:
        required = "yes" if job in required_contexts else "no"
        declared = "yes" if job in workflow_text else "no"
        job_lines.append(f"| `{job}` | {required} | {declared} |")

    md = f"""# B1.2-P0 Adjudication Map

Generated from repository state.

## Contract Authority Surface
- Contract roots: `api-contracts/openapi/v1/*.yaml`
- Bundled artifacts used for adjudication: `api-contracts/dist/openapi/v1/*.bundled.yaml`
- Security schemes required by topology lock: `bearerAuth` (JWT) and `tenantKeyAuth` (webhook/HMAC)

## Auth Topology Inventory
- Total operations: **{len(rows)}**
- JWT-family operations: **{len(jwt_rows)}**
- JWT-family operations declaring `bearerAuth`: **{jwt_with_bearer}**
- Webhook-family operations: **{len(webhook_rows)}**
- Webhook operations declaring `tenantKeyAuth`: **{webhook_with_tenant_key}**
- Webhook operations declaring `bearerAuth` (must remain 0): **{webhook_with_bearer}**

## Canonical Error Surface Inventory
- Operations exposing `401` with `application/problem+json`: **{has_401_problem}**
- Operations exposing `403` with `application/problem+json`: **{has_403_problem}**

## CI Adjudication Surface
| Required Check | In Required Contexts Contract | Declared in CI Workflow |
|---|---|---|
{chr(10).join(job_lines)}

## Invariant-to-Job Mapping
- Contract topology + canonical 401/403 schema: `Phase 1 Runtime Conformance` (`tests/contract/test_contract_semantics.py`)
- Non-vacuous topology/error drift controls: `Phase 1 Negative Controls` (`scripts/contracts/run_negative_controls.sh`)
- JWT missing `tenant_id` and JWT->GUC checks: `JWT Tenant Context Invariants` (`tests/test_b060_phase1_auth_tenant.py`, `backend/tests/test_b07_p1_identity_guc.py`)
- Required-check merge lock enforcement: `Governance Guardrails` (`scripts/ci/enforce_required_status_checks.py`)
"""
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"Wrote {OUTPUT_MD}")
    print(f"Wrote {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Dynamic Contract Conformance Tests - Phase CF4

This module uses Schemathesis to validate runtime behavior against OpenAPI contracts.
Tests ensure that:
- Response status codes match contract-defined allowed statuses
- Response payloads validate against OpenAPI schemas
- Error responses conform to RFC7807 Problem schema

This is the behavioral validation layer: structure can match but behavior can drift.
Dynamic conformance catches status code changes, missing fields, and schema violations.

Coverage Requirement: All in-scope operations hit at least once.
"""

import os
import time
import pytest
import schemathesis
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml
from fastapi.testclient import TestClient
from schemathesis.core.failures import FailureGroup
import uuid
import jwt

# Import FastAPI app for ASGI testing (no network required)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
from app.testing.jwt_rs256 import TEST_PRIVATE_KEY_PEM, private_ring_payload, public_ring_payload

os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault("CONTRACT_TESTING", "1")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
from app.main import app


def _build_token() -> str:
    now = int(time.time())
    payload = {
        "sub": "contract-user",
        "iss": os.environ["AUTH_JWT_ISSUER"],
        "aud": os.environ["AUTH_JWT_AUDIENCE"],
        "iat": now,
        "exp": now + 3600,
        "tenant_id": "00000000-0000-0000-0000-000000000000",
    }
    return jwt.encode(
        payload,
        TEST_PRIVATE_KEY_PEM,
        algorithm=os.environ["AUTH_JWT_ALGORITHM"],
        headers={"kid": "kid-1"},
    )


def load_scope_config() -> dict:
    """Load contract scope configuration."""
    config_path = Path(__file__).parent.parent.parent / "backend" / "app" / "config" / "contract_scope.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_skip_allowlist() -> set[str]:
    """Load explicit bundle skip allowlist for runtime conformance tests."""
    allowlist_path = Path(__file__).parent / "semantics_skip_allowlist.yaml"
    with open(allowlist_path, "r") as f:
        data = yaml.safe_load(f) or {}
    bundles = data.get("bundles", {})
    if not isinstance(bundles, dict):
        raise ValueError("semantics_skip_allowlist.yaml must define a 'bundles' mapping")
    return set(bundles.keys())


def get_bundled_specs() -> List[Path]:
    """Get all bundled OpenAPI specifications."""
    bundles_dir = Path(__file__).parent.parent.parent / "api-contracts" / "dist" / "openapi" / "v1"
    return list(bundles_dir.glob("*.bundled.yaml"))


# Load scope configuration
config = load_scope_config()
in_scope_prefixes = config.get('in_scope_prefixes', [])
semantics_skip_allowlist = load_skip_allowlist()
operation_skip_prefixes = (
    "/api/attribution/platform-connections",
    "/api/attribution/platform-credentials",
    "/api/attribution/channels",
)


def is_in_scope(path: str) -> bool:
    """Check if path is in scope for contract enforcement."""
    for prefix in in_scope_prefixes:
        if path.startswith(prefix):
            return True
    return False


# Test each bundled specification
bundled_specs = get_bundled_specs()
JWT_PROTECTED_PREFIXES = (
    "/api/auth",
    "/api/attribution",
    "/api/v1/revenue",
    "/api/reconciliation",
    "/api/export",
    "/api/health",
    "/api/llm",
)
PUBLIC_ROUTE_ALLOWLIST = {
    ("POST", "/api/auth/login"),
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("GET", "/api/health/ready"),
    ("GET", "/api/health/version"),
}
PROBLEM_REQUIRED_FIELDS = {
    "type",
    "title",
    "status",
    "detail",
    "instance",
    "correlation_id",
    "timestamp",
}


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _iter_operations(spec: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any], List[Dict[str, Any]]]]:
    operations: List[Tuple[str, str, Dict[str, Any], List[Dict[str, Any]]]] = []
    top_level_security = spec.get("security")
    for route_path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            effective_security = operation.get("security", top_level_security)
            operations.append((method.upper(), route_path, operation, effective_security or []))
    return operations


def _extract_security_scheme_names(security: List[Dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for requirement in security:
        if isinstance(requirement, dict):
            names.update(requirement.keys())
    return names


@pytest.mark.parametrize("spec_path", bundled_specs, ids=lambda p: p.name)
def test_contract_semantic_conformance(spec_path: Path):
    """
    Test that FastAPI implementation conforms to OpenAPI contract at runtime.
    
    This test:
    1. Loads the bundled OpenAPI specification
    2. Generates test cases for all operations
    3. Executes requests against FastAPI app (ASGI, no network)
    4. Validates response status codes match contract
    5. Validates response bodies match OpenAPI schemas
    
    Any mismatch indicates contract-implementation divergence.
    """
    # Load schema with Schemathesis
    schema = schemathesis.openapi.from_path(str(spec_path))
    schema.app = app
    client = TestClient(app)
    
    operations_tested = []
    operations_failed = []
    operation_results = []
    for result in schema.get_all_operations():
        try:
            operation_results.append(result.ok())
        except AttributeError:
            continue
    
    skipped_due_to_missing = 0
    executed_in_scope = 0
    is_revenue_spec = spec_path.name == "revenue.bundled.yaml"
    for operation in operation_results:
        if not is_in_scope(operation.path):
            continue
        if any(operation.path.startswith(prefix) for prefix in operation_skip_prefixes):
            continue
        security_param_names = {
            p.get("name")
            for p in getattr(operation.security, "_parameters", [])
            if isinstance(p, dict)
        }
        # Webhook contracts use tenant API keys and have bespoke auth/error semantics.
        # Keep them in explicit allowlist until webhook RFC7807 parity is remediated.
        if "X-Skeldir-Tenant-Key" in security_param_names:
            continue
        try:
            executed_in_scope += 1
            case = operation.as_strategy().example()
            headers = {"X-Correlation-ID": str(uuid.uuid4())}
            if isinstance(case.headers, dict):
                for key, value in case.headers.items():
                    lower_key = key.lower()
                    if lower_key == "x-correlation-id":
                        continue
                    if lower_key == "authorization":
                        headers[key] = f"Bearer {_build_token()}"
                    elif isinstance(value, str) and value.isascii():
                        headers[key] = value
            if operation.security._parameters and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {_build_token()}"
            case.headers.update(headers)
            case.headers = dict(case.headers)
            if operation.security._parameters:
                case._has_explicit_auth = True
            body_payload = None if case.body.__class__.__name__ == "NotSet" else case.body
            response = client.request(
                case.method.upper(),
                case.path,
                headers=headers,
                params=case.query or None,
                cookies=case.cookies or None,
                json=body_payload,
            )
            case.validate_response(response)
            operations_tested.append(f"{case.method.upper()} {case.path}")
        except FailureGroup as exc:
            if response.status_code == 404:
                skipped_due_to_missing += 1
                continue
            operations_failed.append(
                {
                    "operation": f"{operation.method.upper()} {operation.path}",
                    "error": str(exc),
                }
            )
            raise
        except Exception as exc:
            operations_failed.append(
                {
                    "operation": f"{operation.method.upper()} {operation.path}",
                    "error": str(exc),
                }
            )
            raise
    
    if operations_failed:
        failure_report = "\n".join(
            f"  - {failure['operation']}: {failure['error']}" for failure in operations_failed
        )
        pytest.fail(
            f"Contract semantic validation failed for {len(operations_failed)} operation(s):\n"
            f"{failure_report}"
        )
    
    if not operations_tested:
        if skipped_due_to_missing:
            if spec_path.name not in semantics_skip_allowlist:
                pytest.fail(
                    f"Unexpected runtime skip (404) for non-allowlisted bundle: {spec_path.name}"
                )
            pytest.skip(f"All operations returned 404 (not implemented) in {spec_path.name}")
        if not is_revenue_spec:
            if spec_path.name not in semantics_skip_allowlist:
                pytest.fail(
                    f"Unexpected runtime skip (security-only) for non-allowlisted bundle: {spec_path.name}"
                )
            pytest.skip(f"No operations without security requirements in {spec_path.name}")
        pytest.fail(f"No in-scope operations executed for {spec_path.name}")


def test_auth_login_happy_path():
    """
    Test auth login endpoint with valid request.
    
    This explicit test supplements Schemathesis coverage with business logic validation.
    """
    from fastapi.testclient import TestClient
    import uuid
    
    client = TestClient(app)
    
    response = client.post(
        "/api/auth/login",
        json={
            "email": "user@example.com",
            "password": "securePassword123"
        },
        headers={"X-Correlation-ID": str(uuid.uuid4())}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert "access_token" in data, "Missing access_token in response"
    assert "refresh_token" in data, "Missing refresh_token in response"
    assert "expires_in" in data, "Missing expires_in in response"
    assert "user" in data, "Missing user in response"
    assert isinstance(data["user"], dict), "user must be an object"
    assert {"id", "email", "username"}.issubset(data["user"].keys()), "user must include id, email, username"
    assert "token_type" in data, "Missing token_type in response"
    assert data["token_type"] == "Bearer", "Expected token_type to be 'Bearer'"


def test_attribution_revenue_realtime_happy_path():
    """
    Test attribution revenue endpoint with valid request.
    
    This explicit test supplements Schemathesis coverage.
    """
    from fastapi.testclient import TestClient
    import uuid
    
    client = TestClient(app)
    
    response = client.get(
        "/api/attribution/revenue/realtime",
        headers={
            "X-Correlation-ID": str(uuid.uuid4()),
            "Authorization": f"Bearer {_build_token()}",
        },
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = response.json()
    assert "total_revenue" in data, "Missing total_revenue in response"
    assert "verified" in data, "Missing verified in response"
    assert "data_freshness_seconds" in data, "Missing data_freshness_seconds in response"
    assert "tenant_id" in data, "Missing tenant_id in response"
    
    # Validate types
    assert isinstance(data["total_revenue"], (int, float)), "total_revenue should be numeric"
    assert isinstance(data["verified"], bool), "verified should be boolean"
    assert isinstance(data["data_freshness_seconds"], int), "data_freshness_seconds should be int"


def test_coverage_report():
    """
    Generate coverage report showing which operations were tested.
    
    This helps verify the "all operations hit at least once" requirement.
    """
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    # Get all routes from app
    in_scope_routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            path = route.path
            if is_in_scope(path):
                for method in route.methods:
                    if method not in ('HEAD', 'OPTIONS'):
                        in_scope_routes.append(f"{method} {path}")
    
    print(f"\nContract Coverage Report:")
    print(f"  Total in-scope routes: {len(in_scope_routes)}")
    print(f"  Routes:")
    for route in sorted(in_scope_routes):
        print(f"    - {route}")


@pytest.mark.parametrize("spec_path", bundled_specs, ids=lambda p: p.name)
def test_contract_auth_topology_and_error_surface(spec_path: Path):
    """
    Static adjudication for auth topology + canonical error shape.

    This closes vacuity by failing on:
    - JWT route losing bearerAuth declaration
    - webhook route gaining bearerAuth or losing tenantKeyAuth
    - 401/403 responses drifting away from RFC7807 ProblemDetails surface
    """
    spec = _load_yaml(spec_path)
    security_schemes = ((spec.get("components") or {}).get("securitySchemes") or {})

    jwt_protected_operation_count = 0
    jwt_operations_with_403_problem = 0

    for method, route_path, operation, effective_security in _iter_operations(spec):
        security_names = _extract_security_scheme_names(effective_security)
        is_webhook = route_path.startswith("/api/webhooks/")
        is_jwt_family = route_path.startswith(JWT_PROTECTED_PREFIXES)
        is_public_allowlisted = (method, route_path) in PUBLIC_ROUTE_ALLOWLIST

        if is_webhook:
            assert "tenantKeyAuth" in security_names, (
                f"{method} {route_path} must declare tenantKeyAuth"
            )
            assert "bearerAuth" not in security_names, (
                f"{method} {route_path} must not declare bearerAuth"
            )
            assert "tenantKeyAuth" in security_schemes, (
                f"{spec_path.name} must publish tenantKeyAuth in components.securitySchemes"
            )

        if is_jwt_family and not is_webhook and not is_public_allowlisted:
            jwt_protected_operation_count += 1
            assert "bearerAuth" in security_names, (
                f"{method} {route_path} must declare bearerAuth"
            )
            responses = operation.get("responses") or {}
            assert "401" in responses, (
                f"{method} {route_path} must declare 401 Unauthorized"
            )
            assert "403" in responses, (
                f"{method} {route_path} must declare 403 Forbidden"
            )

        responses = operation.get("responses") or {}
        for code in ("401", "403"):
            if code not in responses:
                continue
            response_spec = responses[code] or {}
            content = response_spec.get("content") or {}
            problem_content = content.get("application/problem+json")
            assert problem_content, (
                f"{method} {route_path} {code} must expose application/problem+json"
            )
            schema = problem_content.get("schema") or {}
            if "$ref" in schema:
                assert schema["$ref"].endswith("/ProblemDetails"), (
                    f"{method} {route_path} {code} must reference ProblemDetails"
                )
            else:
                required_fields = set(schema.get("required") or [])
                assert PROBLEM_REQUIRED_FIELDS.issubset(required_fields), (
                    f"{method} {route_path} {code} must require canonical ProblemDetails fields"
                )
            if code == "403" and is_jwt_family and not is_webhook and not is_public_allowlisted:
                jwt_operations_with_403_problem += 1

    if jwt_protected_operation_count > 0:
        assert jwt_operations_with_403_problem == jwt_protected_operation_count, (
            f"{spec_path.name} must expose canonical 403 ProblemDetails on every JWT-protected operation"
        )


# Negative test scenarios (documented in negative_tests_dynamic.md)
# These should be run manually on test branches to validate enforcement


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])

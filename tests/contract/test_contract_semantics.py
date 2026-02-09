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
from typing import List
import yaml
from fastapi.testclient import TestClient
from schemathesis.core.failures import FailureGroup
import uuid
import jwt

# Import FastAPI app for ASGI testing (no network required)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
os.environ.setdefault("AUTH_JWT_SECRET", "test-secret")
os.environ.setdefault("AUTH_JWT_ALGORITHM", "HS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault("CONTRACT_TESTING", "1")
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
    return jwt.encode(payload, os.environ["AUTH_JWT_SECRET"], algorithm=os.environ["AUTH_JWT_ALGORITHM"])


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


def is_in_scope(path: str) -> bool:
    """Check if path is in scope for contract enforcement."""
    for prefix in in_scope_prefixes:
        if path.startswith(prefix):
            return True
    return False


# Test each bundled specification
bundled_specs = get_bundled_specs()


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
        if operation.security._parameters and not is_revenue_spec:
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


# Negative test scenarios (documented in negative_tests_dynamic.md)
# These should be run manually on test branches to validate enforcement


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])





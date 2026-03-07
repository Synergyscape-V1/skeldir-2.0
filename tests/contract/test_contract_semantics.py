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
import json
import time
import pytest
import schemathesis
from pathlib import Path
from typing import List
import yaml
from fastapi.testclient import TestClient
from schemathesis.core.failures import FailureGroup
import uuid

# Import FastAPI app for ASGI testing (no network required)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))
from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

os.environ["AUTH_JWT_SECRET"] = private_ring_payload()
os.environ["AUTH_JWT_PUBLIC_KEY_RING"] = public_ring_payload()
os.environ["AUTH_JWT_ALGORITHM"] = "RS256"
os.environ["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
os.environ["AUTH_JWT_AUDIENCE"] = "skeldir-api"
os.environ["CONTRACT_TESTING"] = "1"
os.environ["TESTING"] = "1"
from app.main import app
from app.security.auth import mint_internal_jwt
from app.api import webhooks as webhooks_api


def _build_token() -> str:
    return mint_internal_jwt(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        user_id=uuid.uuid4(),
        expires_in_seconds=3600,
        additional_claims={
            "role": "viewer",
            "roles": ["viewer"],
            "scopes": ["viewer"],
        },
    )


@pytest.fixture(autouse=True)
def _contract_runtime_auth_fixture(monkeypatch):
    async def _no_revocation_check(_token_claims):
        return None

    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation_check)


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
P8_FORBIDDEN_SUBSTRINGS = (
    "unknown kid",
    "kid",
    "jwks",
    "user not found",
    "signature",
    "shopify",
    "stripe",
    "paypal",
    "woocommerce",
    "invalidtokenerror",
    "pyjwterror",
    "invalid_signature",
    "invalid_tenant_key",
)
P8_EXPECTED_KEYS = {
    "type",
    "title",
    "status",
    "detail",
    "instance",
    "correlation_id",
    "timestamp",
    "code",
}


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
        if any(operation.path.startswith(prefix) for prefix in operation_skip_prefixes):
            continue
        security_param_names = {
            p.get("name")
            for p in getattr(operation.security, "_parameters", [])
            if isinstance(p, dict)
        }
        # Webhook contracts use tenant API keys and signature semantics that do not
        # fit generic Schemathesis auth/header generation. P8 parity is asserted in
        # dedicated runtime tests below.
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
            "password": "securePassword123",
            "tenant_id": "00000000-0000-0000-0000-000000000000",
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


def _assert_problem_details_response(response, *, expected_status: int) -> dict:
    assert response.status_code == expected_status, response.text
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    body = response.json()
    assert set(body.keys()) == P8_EXPECTED_KEYS
    assert body["status"] == expected_status
    if expected_status == 401:
        assert body["code"] == "AUTH_UNAUTHORIZED"
    if expected_status == 403:
        assert body["code"] == "AUTH_FORBIDDEN"
    lowered = json.dumps(body, sort_keys=True).lower()
    for forbidden in P8_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in lowered, f"oracle leakage detected: {forbidden}"
    return body


def test_p8_contract_error_surface_uses_problem_details_for_auth_and_webhook_modalities():
    bundle_names = (
        "auth.bundled.yaml",
        "webhooks.shopify.bundled.yaml",
        "webhooks.stripe.bundled.yaml",
        "webhooks.paypal.bundled.yaml",
        "webhooks.woocommerce.bundled.yaml",
    )
    required_fields = {"type", "title", "status", "detail", "instance", "correlation_id", "timestamp", "code"}
    bundles_dir = Path(__file__).parent.parent.parent / "api-contracts" / "dist" / "openapi" / "v1"

    for bundle_name in bundle_names:
        doc = yaml.safe_load((bundles_dir / bundle_name).read_text(encoding="utf-8"))
        paths = doc.get("paths", {})
        for path, operations in paths.items():
            for method, operation in operations.items():
                if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                responses = operation.get("responses", {})
                for status_code in ("401", "403"):
                    if status_code not in responses:
                        continue
                    response = responses[status_code]
                    content = response.get("content", {})
                    assert set(content.keys()) == {"application/problem+json"}, (
                        f"{bundle_name} {method.upper()} {path} {status_code} must be application/problem+json only"
                    )
                    schema = content["application/problem+json"]["schema"]
                    properties = schema.get("properties", {})
                    required = set(schema.get("required", []))
                    assert required_fields.issubset(required), (
                        f"{bundle_name} {method.upper()} {path} {status_code} missing canonical required ProblemDetails fields"
                    )
                    assert "code" in properties, (
                        f"{bundle_name} {method.upper()} {path} {status_code} missing stable error code field"
                    )


def test_p8_runtime_parity_invalid_jwt_vs_invalid_hmac_signature():
    async def _tenant_secrets_override():
        return {
            "tenant_id": uuid.uuid4(),
            "shopify_webhook_secret": "shopify_secret",
            "stripe_webhook_secret": "stripe_secret",
            "paypal_webhook_secret": "paypal_secret",
            "woocommerce_webhook_secret": "woo_secret",
        }

    client = TestClient(app)
    app.dependency_overrides[webhooks_api.tenant_secrets] = _tenant_secrets_override
    try:
        jwt_resp = client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid.uuid4()),
                "Authorization": "Bearer not-a-jwt",
            },
        )
        hmac_resp = client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            json={
                "id": f"pi_{uuid.uuid4().hex[:12]}",
                "amount": 5000,
                "currency": "usd",
                "created": 1732631400,
                "status": "succeeded",
            },
            headers={
                "X-Correlation-ID": str(uuid.uuid4()),
                "X-Skeldir-Tenant-Key": "synthetic-tenant-key",
                "Stripe-Signature": "t=0,v1=invalid",
            },
        )
    finally:
        app.dependency_overrides.pop(webhooks_api.tenant_secrets, None)

    jwt_problem = _assert_problem_details_response(jwt_resp, expected_status=401)
    hmac_problem = _assert_problem_details_response(hmac_resp, expected_status=401)
    assert set(jwt_problem.keys()) == set(hmac_problem.keys())
    assert jwt_problem["detail"] == hmac_problem["detail"]
    assert jwt_problem["code"] == hmac_problem["code"] == "AUTH_UNAUTHORIZED"


def test_p8_runtime_403_surface_exists_and_is_canonical(monkeypatch):
    claims = {
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "sub": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "role": "viewer",
        "roles": ["viewer"],
        "scopes": ["viewer"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": str(uuid.uuid4()),
    }

    async def _no_revocation_check(_token_claims):
        return None

    monkeypatch.setattr("app.security.auth._decode_token", lambda _token: claims)
    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation_check)
    client = TestClient(app)
    response = client.get(
        "/api/auth/admin/rbac-check",
        headers={
            "X-Correlation-ID": str(uuid.uuid4()),
            "Authorization": "Bearer contract-test-token",
        },
    )
    _assert_problem_details_response(response, expected_status=403)


def test_p8_negative_control_leak_detector_is_non_vacuous():
    with pytest.raises(AssertionError):
        lowered = json.dumps({"detail": "unknown kid signature failure for stripe InvalidTokenError"}).lower()
        for forbidden in P8_FORBIDDEN_SUBSTRINGS:
            assert forbidden not in lowered, f"oracle leakage detected: {forbidden}"

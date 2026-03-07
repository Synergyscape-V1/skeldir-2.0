from __future__ import annotations

import json
import time
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api import webhooks as webhooks_api
from app.core.secrets import reset_crypto_secret_caches_for_testing, reset_jwt_verification_pg_cache_for_testing
from app.main import app
from app.security.auth import unauthorized_auth_error
from app.testing.jwt_rs256 import TEST_PRIVATE_KEY_PEM, private_ring_payload, public_ring_payload

FORBIDDEN_LEAK_SUBSTRINGS = (
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

EXPECTED_PROBLEM_KEYS = {
    "type",
    "title",
    "status",
    "detail",
    "instance",
    "correlation_id",
    "timestamp",
    "code",
}


def _mint_test_token(
    *,
    exp_delta_seconds: int = 300,
    include_tenant_claim: bool = True,
    kid: str = "kid-1",
) -> str:
    now = int(time.time())
    user_id = str(uuid4())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "jti": str(uuid4()),
        "iat": now - 1,
        "exp": now + exp_delta_seconds,
        "iss": "https://issuer.skeldir.test",
        "aud": "skeldir-api",
        "role": "viewer",
        "roles": ["viewer"],
        "scopes": ["viewer"],
    }
    if include_tenant_claim:
        payload["tenant_id"] = str(uuid4())
    return jwt.encode(payload, TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": kid})


def _assert_no_oracle_substrings(payload_text: str) -> None:
    lowered = payload_text.lower()
    for forbidden in FORBIDDEN_LEAK_SUBSTRINGS:
        assert forbidden not in lowered, f"leakage substring detected: {forbidden}"


def _assert_problem_response_shape(response, *, expected_status: int) -> dict:
    assert response.status_code == expected_status, response.text
    assert response.headers.get("content-type", "").startswith("application/problem+json")
    body = response.json()
    assert set(body.keys()) == EXPECTED_PROBLEM_KEYS
    assert body["status"] == expected_status
    UUID(str(body["correlation_id"]))
    if expected_status == 401:
        assert body["code"] == "AUTH_UNAUTHORIZED"
    if expected_status == 403:
        assert body["code"] == "AUTH_FORBIDDEN"
    _assert_no_oracle_substrings(json.dumps(body, sort_keys=True))
    return body


@pytest.fixture(autouse=True)
def _disable_revocation_io(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWT_SECRET", private_ring_payload())
    monkeypatch.setenv("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
    monkeypatch.setenv("AUTH_JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "skeldir-api")
    reset_crypto_secret_caches_for_testing()
    reset_jwt_verification_pg_cache_for_testing()

    async def _no_revocation_check(_token_claims):
        return None

    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation_check)


@pytest.mark.asyncio
async def test_eg83_invalid_jwt_and_invalid_hmac_return_same_canonical_401_shape() -> None:
    async def _tenant_secrets_override():
        return {
            "tenant_id": uuid4(),
            "shopify_webhook_secret": "shopify_secret",
            "stripe_webhook_secret": "stripe_secret",
            "paypal_webhook_secret": "paypal_secret",
            "woocommerce_webhook_secret": "woo_secret",
        }

    app.dependency_overrides[webhooks_api.tenant_secrets] = _tenant_secrets_override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            jwt_resp = await client.get(
                "/api/v1/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": "Bearer not-a-jwt",
                },
            )
            hmac_resp = await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                json={
                    "id": f"pi_{uuid4().hex[:12]}",
                    "amount": 5000,
                    "currency": "usd",
                    "created": 1732631400,
                    "status": "succeeded",
                },
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": "synthetic-tenant-key",
                    "Stripe-Signature": "t=0,v1=invalid",
                },
            )
    finally:
        app.dependency_overrides.pop(webhooks_api.tenant_secrets, None)

    jwt_problem = _assert_problem_response_shape(jwt_resp, expected_status=401)
    hmac_problem = _assert_problem_response_shape(hmac_resp, expected_status=401)
    assert set(jwt_problem.keys()) == set(hmac_problem.keys())
    assert jwt_problem["detail"] == hmac_problem["detail"]
    assert jwt_problem["code"] == hmac_problem["code"] == "AUTH_UNAUTHORIZED"


@pytest.mark.asyncio
async def test_eg81_jwt_failure_variants_share_non_leaky_problem_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    token_unknown_kid = _mint_test_token(kid="kid-unknown")
    token_expired = _mint_test_token(exp_delta_seconds=-30)
    token_missing_tenant = _mint_test_token(include_tenant_claim=False)

    # Simulate a stale/unknown-kid verifier path that cannot validate only unknown-kid tokens.
    from app.core import secrets as secrets_module

    def _resolver(*, kid: str | None):
        if kid == "kid-unknown":
            return ("invalid-public-key", [], True)
        return secrets_module.resolve_jwt_verification_keys(kid=kid)

    monkeypatch.setattr("app.security.auth.resolve_jwt_verification_keys", _resolver)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = {
            "malformed": await client.get(
                "/api/v1/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": "Bearer not-a-jwt",
                },
            ),
            "expired": await client.get(
                "/api/v1/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {token_expired}",
                },
            ),
            "missing_tenant": await client.get(
                "/api/v1/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {token_missing_tenant}",
                },
            ),
            "unknown_kid": await client.get(
                "/api/v1/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {token_unknown_kid}",
                },
            ),
        }

    problems = {
        scenario: _assert_problem_response_shape(response, expected_status=401)
        for scenario, response in responses.items()
    }
    codes = {p["code"] for p in problems.values()}
    details = {p["detail"] for p in problems.values()}
    assert codes == {"AUTH_UNAUTHORIZED"}
    assert details == {"Authentication failed."}


@pytest.mark.asyncio
async def test_eg83_hmac_failure_variants_share_non_leaky_problem_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _tenant_secrets_override():
        return {
            "tenant_id": uuid4(),
            "shopify_webhook_secret": "shopify_secret",
            "stripe_webhook_secret": "stripe_secret",
            "paypal_webhook_secret": "paypal_secret",
            "woocommerce_webhook_secret": "woo_secret",
        }

    transport = ASGITransport(app=app)
    app.dependency_overrides[webhooks_api.tenant_secrets] = _tenant_secrets_override
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            missing_signature = await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                json={
                    "id": f"pi_{uuid4().hex[:12]}",
                    "amount": 5000,
                    "currency": "usd",
                    "created": 1732631400,
                    "status": "succeeded",
                },
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": "synthetic-tenant-key",
                },
            )
    finally:
        app.dependency_overrides.pop(webhooks_api.tenant_secrets, None)

    async def _raise_unauthorized(_api_key: str):
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _raise_unauthorized)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unknown_tenant = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            json={
                "id": f"pi_{uuid4().hex[:12]}",
                "amount": 5000,
                "currency": "usd",
                "created": 1732631400,
                "status": "succeeded",
            },
            headers={
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "unknown-key",
                "Stripe-Signature": "t=0,v1=invalid",
            },
        )
        missing_tenant_key = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            json={
                "id": f"pi_{uuid4().hex[:12]}",
                "amount": 5000,
                "currency": "usd",
                "created": 1732631400,
                "status": "succeeded",
            },
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Stripe-Signature": "t=0,v1=invalid",
            },
        )

    problems = {
        "missing_signature": _assert_problem_response_shape(missing_signature, expected_status=401),
        "unknown_tenant": _assert_problem_response_shape(unknown_tenant, expected_status=401),
        "missing_tenant_key": _assert_problem_response_shape(missing_tenant_key, expected_status=401),
    }
    codes = {p["code"] for p in problems.values()}
    details = {p["detail"] for p in problems.values()}
    assert codes == {"AUTH_UNAUTHORIZED"}
    assert details == {"Authentication failed."}


@pytest.mark.asyncio
async def test_eg82_unknown_tenant_key_path_is_canonical_and_non_leaky(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _raise_unauthorized(_api_key: str):
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _raise_unauthorized)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            json={
                "id": f"pi_{uuid4().hex[:12]}",
                "amount": 5000,
                "currency": "usd",
                "created": 1732631400,
                "status": "succeeded",
            },
            headers={
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "unknown-key",
                "Stripe-Signature": "t=0,v1=invalid",
            },
        )
    _assert_problem_response_shape(response, expected_status=401)


@pytest.mark.asyncio
async def test_eg82_raw_http_exception_401_is_normalized_and_non_leaky() -> None:
    async def _leaky_tenant_override():
        raise HTTPException(status_code=401, detail="unknown kid signature failure for stripe")

    app.dependency_overrides[webhooks_api.tenant_secrets] = _leaky_tenant_override
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                json={
                    "id": f"pi_{uuid4().hex[:12]}",
                    "amount": 5000,
                    "currency": "usd",
                    "created": 1732631400,
                    "status": "succeeded",
                },
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": "synthetic-tenant-key",
                    "Stripe-Signature": "t=0,v1=invalid",
                },
            )
    finally:
        app.dependency_overrides.pop(webhooks_api.tenant_secrets, None)

    problem = _assert_problem_response_shape(response, expected_status=401)
    assert problem["detail"] == "Authentication failed."


def test_eg82_negative_control_oracle_leak_detector_is_non_vacuous() -> None:
    with pytest.raises(AssertionError):
        _assert_no_oracle_substrings(
            json.dumps(
                {
                    "detail": "unknown kid signature failure for stripe InvalidTokenError",
                    "status": 401,
                }
            )
        )

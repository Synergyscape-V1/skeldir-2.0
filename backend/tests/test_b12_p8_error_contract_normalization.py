from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import webhooks as webhooks_api
from app.core.secrets import reset_crypto_secret_caches_for_testing, reset_jwt_verification_pg_cache_for_testing
import app.middleware.pii_stripping as pii_stripping_middleware
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


def _assert_www_authenticate_is_safe(response, *, allow_absent: bool) -> None:
    value = response.headers.get("www-authenticate")
    if value is None:
        assert allow_absent
        return
    lowered = value.lower()
    assert lowered == "bearer"
    assert "error=" not in lowered
    assert "error_description=" not in lowered
    assert "scope=" not in lowered


def _stripe_signature(raw_body: bytes, secret: str, *, valid: bool) -> str:
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not valid:
        digest = "0" * len(digest)
    return f"t={timestamp},v1={digest}"


def _shopify_signature(raw_body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()).decode("utf-8")


def _assert_constant_work_compute_called_once(calls: int) -> None:
    assert calls == 1, "expected exactly one signature compute invocation"


def _tenant_info() -> dict:
    return {
        "tenant_id": uuid4(),
        "shopify_webhook_secret": "shopify_secret",
        "stripe_webhook_secret": "stripe_secret",
        "paypal_webhook_secret": "paypal_secret",
        "woocommerce_webhook_secret": "woo_secret",
    }


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
async def test_eg83_invalid_jwt_and_invalid_hmac_return_same_canonical_401_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _known_tenant_lookup(api_key: str):
        if api_key == "known-key":
            return _tenant_info()
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _known_tenant_lookup)

    payload = {
        "id": f"pi_{uuid4().hex[:12]}",
        "amount": 5000,
        "currency": "usd",
        "created": 1732631400,
        "status": "succeeded",
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad_signature = _stripe_signature(raw_body, "stripe_secret", valid=False)

    transport = ASGITransport(app=app)
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
            content=raw_body,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "known-key",
                "Stripe-Signature": bad_signature,
            },
        )

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
    async def _tenant_lookup(api_key: str):
        if api_key == "known-key":
            return _tenant_info()
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _tenant_lookup)
    payload = {
        "id": f"pi_{uuid4().hex[:12]}",
        "amount": 5000,
        "currency": "usd",
        "created": 1732631400,
        "status": "succeeded",
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad_signature = _stripe_signature(raw_body, "stripe_secret", valid=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        missing_signature = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=raw_body,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "known-key",
            },
        )
        unknown_tenant = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=raw_body,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "unknown-key",
                "Stripe-Signature": bad_signature,
            },
        )
        missing_tenant_key = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=raw_body,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
                "Stripe-Signature": bad_signature,
            },
        )

    problems = {
        "missing_signature": _assert_problem_response_shape(missing_signature, expected_status=401),
        "unknown_tenant": _assert_problem_response_shape(unknown_tenant, expected_status=401),
        "missing_tenant_key": _assert_problem_response_shape(missing_tenant_key, expected_status=401),
    }
    assert {p["code"] for p in problems.values()} == {"AUTH_UNAUTHORIZED"}
    assert {p["detail"] for p in problems.values()} == {"Authentication failed."}


@pytest.mark.asyncio
async def test_eg8cf_constant_work_unknown_key_and_known_bad_signature_both_invoke_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _tenant_lookup(api_key: str):
        if api_key == "known-key":
            return _tenant_info()
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _tenant_lookup)

    original_secret_field, original_verifier = webhooks_api.WEBHOOK_VERIFIERS["stripe"]
    call_count = {"value": 0}

    def _spy_verifier(raw_body: bytes, secret: str | None, header: str | None) -> bool:
        call_count["value"] += 1
        return original_verifier(raw_body, secret, header)

    webhooks_api.WEBHOOK_VERIFIERS["stripe"] = (original_secret_field, _spy_verifier)

    payload = {
        "id": f"pi_{uuid4().hex[:12]}",
        "amount": 5000,
        "currency": "usd",
        "created": 1732631400,
        "status": "succeeded",
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad_signature = _stripe_signature(raw_body, "stripe_secret", valid=False)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            call_count["value"] = 0
            unknown_key_response = await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                content=raw_body,
                headers={
                    "content-type": "application/json",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": "unknown-key",
                    "Stripe-Signature": bad_signature,
                },
            )
            unknown_calls = call_count["value"]

            call_count["value"] = 0
            known_key_bad_sig_response = await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                content=raw_body,
                headers={
                    "content-type": "application/json",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": "known-key",
                    "Stripe-Signature": bad_signature,
                },
            )
            known_calls = call_count["value"]
    finally:
        webhooks_api.WEBHOOK_VERIFIERS["stripe"] = (original_secret_field, original_verifier)

    _assert_problem_response_shape(unknown_key_response, expected_status=401)
    _assert_problem_response_shape(known_key_bad_sig_response, expected_status=401)
    _assert_constant_work_compute_called_once(unknown_calls)
    _assert_constant_work_compute_called_once(known_calls)


@pytest.mark.asyncio
async def test_eg8size_oversized_payload_is_rejected_pre_crypto_with_constant_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _tenant_lookup(api_key: str):
        if api_key == "known-key":
            return _tenant_info()
        if api_key == "unknown-key":
            raise unauthorized_auth_error()
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _tenant_lookup)
    monkeypatch.setattr(webhooks_api.settings, "WEBHOOK_AUTH_MAX_BODY_BYTES", 64, raising=False)
    monkeypatch.setattr(pii_stripping_middleware, "WEBHOOK_AUTH_MAX_BODY_BYTES", 64, raising=False)

    original_secret_field, original_verifier = webhooks_api.WEBHOOK_VERIFIERS["stripe"]
    call_count = {"value": 0}

    def _spy_verifier(raw_body: bytes, secret: str | None, header: str | None) -> bool:
        call_count["value"] += 1
        return original_verifier(raw_body, secret, header)

    webhooks_api.WEBHOOK_VERIFIERS["stripe"] = (original_secret_field, _spy_verifier)

    large_payload = json.dumps({"pad": "x" * 4096}, separators=(",", ":")).encode("utf-8")

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            call_count["value"] = 0
            known_response = await client.post(
                "/api/webhooks/stripe/payment_intent/succeeded",
                content=large_payload,
                headers={
                    "content-type": "application/json",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": "known-key",
                    "Stripe-Signature": "t=0,v1=invalid",
                },
            )
            known_calls = call_count["value"]

            call_count["value"] = 0
            unknown_response = await client.post(
                "/api/webhooks/stripe/payment_intent/succeeded",
                content=large_payload,
                headers={
                    "content-type": "application/json",
                    "X-Correlation-ID": str(uuid4()),
                    "X-Skeldir-Tenant-Key": "unknown-key",
                    "Stripe-Signature": "t=0,v1=invalid",
                },
            )
            unknown_calls = call_count["value"]
    finally:
        webhooks_api.WEBHOOK_VERIFIERS["stripe"] = (original_secret_field, original_verifier)

    assert known_response.status_code == 413, known_response.text
    assert unknown_response.status_code == 413, unknown_response.text
    assert known_response.json() == unknown_response.json() == {"detail": "Request payload too large."}
    assert known_calls == 0
    assert unknown_calls == 0


@pytest.mark.asyncio
async def test_eg8hdr_www_authenticate_behavior_is_non_leaky(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _tenant_lookup(api_key: str):
        if api_key == "known-key":
            return _tenant_info()
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _tenant_lookup)

    payload = {
        "id": f"pi_{uuid4().hex[:12]}",
        "amount": 5000,
        "currency": "usd",
        "created": 1732631400,
        "status": "succeeded",
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    bad_signature = _stripe_signature(raw_body, "stripe_secret", valid=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        jwt_response = await client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": "Bearer not-a-jwt",
            },
        )
        webhook_response = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=raw_body,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "known-key",
                "Stripe-Signature": bad_signature,
            },
        )

    _assert_problem_response_shape(jwt_response, expected_status=401)
    _assert_problem_response_shape(webhook_response, expected_status=401)
    _assert_www_authenticate_is_safe(jwt_response, allow_absent=True)
    assert webhook_response.headers.get("www-authenticate") is None


@pytest.mark.asyncio
async def test_eg8422_auth_header_failures_do_not_emit_422_pointer_payloads() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=b"[]",
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
            },
        )

    body = _assert_problem_response_shape(response, expected_status=401)
    serialized = json.dumps(body, sort_keys=True).lower()
    assert "loc" not in serialized
    assert "input" not in serialized


@pytest.mark.asyncio
async def test_eg8422_business_validation_after_valid_auth_is_problem_details_and_non_leaky(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _tenant_lookup(api_key: str):
        if api_key == "known-key":
            return _tenant_info()
        raise unauthorized_auth_error()

    monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", _tenant_lookup)

    invalid_body = b"[]"
    signature = _shopify_signature(invalid_body, "shopify_secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=invalid_body,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "known-key",
                "X-Shopify-Hmac-Sha256": signature,
            },
        )

    problem = _assert_problem_response_shape(response, expected_status=422)
    assert problem["code"] == "REQUEST_VALIDATION_FAILED"
    serialized = json.dumps(problem, sort_keys=True).lower()
    assert "loc" not in serialized
    assert "input" not in serialized
    assert "validationerror" not in serialized


@pytest.mark.asyncio
async def test_eg82_raw_http_exception_401_is_normalized_and_non_leaky(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _leaky_auth_dependency(*, request, provider, signature_header, api_key):
        raise webhooks_api.HTTPException(status_code=401, detail="unknown kid signature failure for stripe")

    monkeypatch.setattr(webhooks_api, "_authorize_webhook_request", _leaky_auth_dependency)

    payload = {
        "id": f"pi_{uuid4().hex[:12]}",
        "amount": 5000,
        "currency": "usd",
        "created": 1732631400,
        "status": "succeeded",
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=raw_body,
            headers={
                "content-type": "application/json",
                "X-Correlation-ID": str(uuid4()),
                "X-Skeldir-Tenant-Key": "known-key",
                "Stripe-Signature": "t=0,v1=invalid",
            },
        )

    problem = _assert_problem_response_shape(response, expected_status=401)
    assert problem["detail"] == "Authentication failed."


def test_eg8proof_negative_control_constant_work_detector_is_non_vacuous() -> None:
    with pytest.raises(AssertionError):
        _assert_constant_work_compute_called_once(0)


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

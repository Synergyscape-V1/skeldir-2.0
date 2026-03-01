from __future__ import annotations

import json
import time
from uuid import uuid4

import jwt
import pytest
from jwt import InvalidTokenError
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.secrets import reset_crypto_secret_caches_for_testing, reset_jwt_verification_pg_cache_for_testing
from app.main import app
from app.security.auth import _decode_token, decode_and_verify_jwt
from app.tasks.context import decode_worker_auth_token
from app.testing.jwt_rs256 import TEST_PRIVATE_KEY_PEM, TEST_PUBLIC_KEY_PEM


def _ring_payload(*, current_kid: str, key_material: str) -> str:
    return json.dumps({"current_kid": current_kid, "keys": {current_kid: key_material}})


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", "RS256")
    monkeypatch.setattr(settings, "AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setattr(settings, "AUTH_JWT_AUDIENCE", "skeldir-api")
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        _ring_payload(current_kid="kid-1", key_material=TEST_PRIVATE_KEY_PEM),
    )
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_PUBLIC_KEY_RING",
        _ring_payload(current_kid="kid-1", key_material=TEST_PUBLIC_KEY_PEM),
    )
    monkeypatch.setenv("SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS", "300")
    reset_crypto_secret_caches_for_testing()
    reset_jwt_verification_pg_cache_for_testing()
    yield
    reset_crypto_secret_caches_for_testing()
    reset_jwt_verification_pg_cache_for_testing()


def _payload() -> dict[str, object]:
    now = int(time.time())
    return {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "user_id": str(uuid4()),
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
        "iat": now,
        "exp": now + 120,
    }


def test_rs256_token_is_accepted():
    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-1"})
    decoded = _decode_token(token)
    assert decoded["tenant_id"]


def test_hs256_token_is_rejected():
    token = jwt.encode(_payload(), "hs-secret", algorithm="HS256", headers={"kid": "kid-1"})
    with pytest.raises(InvalidTokenError):
        _decode_token(token)


def test_alg_none_token_is_rejected():
    payload = _payload()
    token = jwt.encode(payload, key="", algorithm="none")
    with pytest.raises(InvalidTokenError):
        _decode_token(token)


def test_verification_steady_state_does_not_read_secret_source(monkeypatch):
    from app.core import secrets as secrets_module

    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-1"})
    _decode_token(token)  # warm verification cache

    calls = {"count": 0}

    def _counting_fetch(_key: str) -> str | None:
        calls["count"] += 1
        return None

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _counting_fetch)
    for _ in range(10):
        _decode_token(token)
    assert calls["count"] == 0


def test_worker_plane_uses_same_verifier_and_no_fetch(monkeypatch):
    from app.core import secrets as secrets_module

    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-1"})
    decode_and_verify_jwt(token)  # warm verification cache

    calls = {"count": 0}

    def _counting_fetch(_key: str) -> str | None:
        calls["count"] += 1
        return None

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _counting_fetch)
    decoded = decode_worker_auth_token(token)
    assert decoded["tenant_id"]
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_http_plane_steady_state_does_not_read_secret_source(monkeypatch):
    from app.core import secrets as secrets_module

    token = jwt.encode(_payload(), TEST_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "kid-1"})
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        warm = await client.get(
            "/api/auth/verify",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Correlation-ID": str(uuid4()),
            },
        )
        assert warm.status_code == 200

        calls = {"count": 0}

        def _counting_fetch(_key: str) -> str | None:
            calls["count"] += 1
            return None

        monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _counting_fetch)
        for _ in range(5):
            resp = await client.get(
                "/api/auth/verify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Correlation-ID": str(uuid4()),
                },
            )
            assert resp.status_code == 200

    assert calls["count"] == 0

from __future__ import annotations

import json
import os
import time
from uuid import uuid4

import jwt
import pytest
from jwt import InvalidTokenError

from app.core.config import settings
from app.core.secrets import reset_crypto_secret_caches_for_testing
from app.security.auth import _decode_token, mint_internal_jwt
from app.testing.jwt_rs256 import TEST_PRIVATE_KEY_PEM, TEST_PUBLIC_KEY_PEM


def _jwt_ring_payload(
    *,
    current_kid: str,
    key_material: str,
    previous_kids: list[str] | None = None,
    all_kids: list[str] | None = None,
) -> str:
    kids = all_kids or [current_kid]
    payload = {
        "current_kid": current_kid,
        "keys": {kid: key_material for kid in kids},
    }
    if previous_kids is not None:
        payload["previous_kids"] = previous_kids
    return json.dumps(payload)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS", "1")
    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_REFRESH_DEBOUNCE_SECONDS", "1")
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", "RS256")
    monkeypatch.setattr(settings, "AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setattr(settings, "AUTH_JWT_AUDIENCE", "skeldir-api")
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        _jwt_ring_payload(current_kid="kid-1", key_material=TEST_PRIVATE_KEY_PEM),
    )
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_PUBLIC_KEY_RING",
        _jwt_ring_payload(current_kid="kid-1", key_material=TEST_PUBLIC_KEY_PEM),
    )
    reset_crypto_secret_caches_for_testing()
    yield
    reset_crypto_secret_caches_for_testing()


def test_jwt_overlap_rotation_switches_kid_within_bound(monkeypatch):
    tenant_id = uuid4()
    user_id = uuid4()
    old_private_ring = _jwt_ring_payload(current_kid="kid-old", key_material=TEST_PRIVATE_KEY_PEM)
    old_public_ring = _jwt_ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM)
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", old_private_ring)
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY_RING", old_public_ring)

    old_token = mint_internal_jwt(tenant_id=tenant_id, user_id=user_id, expires_in_seconds=180)
    old_header = jwt.get_unverified_header(old_token)
    assert old_header["kid"] == "kid-old"

    rotated_private_ring = _jwt_ring_payload(
        current_kid="kid-new",
        key_material=TEST_PRIVATE_KEY_PEM,
        previous_kids=["kid-old"],
        all_kids=["kid-old", "kid-new"],
    )
    rotated_public_ring = _jwt_ring_payload(
        current_kid="kid-new",
        key_material=TEST_PUBLIC_KEY_PEM,
        previous_kids=["kid-old"],
        all_kids=["kid-old", "kid-new"],
    )
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", rotated_private_ring)
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY_RING", rotated_public_ring)
    time.sleep(1.1)

    new_token = mint_internal_jwt(tenant_id=tenant_id, user_id=user_id, expires_in_seconds=180)
    new_header = jwt.get_unverified_header(new_token)
    assert new_header["kid"] == "kid-new"

    old_claims = _decode_token(old_token)
    assert old_claims["tenant_id"] == str(tenant_id)


def test_missing_kid_fails_when_ring_requires_kid():
    payload = {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "exp": int(time.time()) + 120,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
    }
    token_without_kid = jwt.encode(payload, TEST_PRIVATE_KEY_PEM, algorithm=settings.AUTH_JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError):
        _decode_token(token_without_kid)


def test_keyring_refresh_failure_fails_closed_for_mint(monkeypatch):
    _ = mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=60)
    time.sleep(1.1)

    from app.core import secrets as secrets_module

    def _boom(_: str) -> str | None:
        raise RuntimeError("simulated source-of-truth fetch failure")

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _boom)
    with pytest.raises(RuntimeError, match="simulated source-of-truth fetch failure"):
        mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=60)


def test_unbounded_keyring_is_rejected(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        _jwt_ring_payload(
            current_kid="k1",
            key_material=TEST_PRIVATE_KEY_PEM,
            previous_kids=["k2", "k3", "k4"],
            all_kids=["k1", "k2", "k3", "k4"],
        ),
    )
    with pytest.raises(RuntimeError, match="exceeds max accepted keys"):
        mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=60)


def test_unknown_kid_forces_debounced_refresh_and_recovers(monkeypatch):
    from app.core import secrets as secrets_module

    old_public_ring = _jwt_ring_payload(current_kid="kid-old", key_material=TEST_PUBLIC_KEY_PEM)
    rotated_public_ring = _jwt_ring_payload(
        current_kid="kid-new",
        key_material=TEST_PUBLIC_KEY_PEM,
        previous_kids=["kid-old"],
        all_kids=["kid-old", "kid-new"],
    )
    monkeypatch.setattr(settings, "AUTH_JWT_PUBLIC_KEY_RING", old_public_ring)
    reset_crypto_secret_caches_for_testing()
    _ = mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=180)

    calls = {"count": 0}

    def _refreshing_fetch(key: str) -> str | None:
        if key == "AUTH_JWT_PUBLIC_KEY_RING":
            calls["count"] += 1
            return rotated_public_ring
        return getattr(settings, key, None)

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _refreshing_fetch)
    payload = {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "exp": int(time.time()) + 120,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
    }
    token = jwt.encode(payload, TEST_PRIVATE_KEY_PEM, algorithm=settings.AUTH_JWT_ALGORITHM, headers={"kid": "kid-new"})
    decoded = _decode_token(token)
    assert decoded["tenant_id"] == payload["tenant_id"]
    assert calls["count"] == 1


def test_unknown_kid_refresh_failure_degrades_to_bounded_fallback(monkeypatch):
    from app.core import secrets as secrets_module

    monkeypatch.setattr(
        settings,
        "AUTH_JWT_PUBLIC_KEY_RING",
        _jwt_ring_payload(
            current_kid="kid-current",
            key_material=TEST_PUBLIC_KEY_PEM,
            previous_kids=["kid-prev"],
            all_kids=["kid-current", "kid-prev"],
        ),
    )
    reset_crypto_secret_caches_for_testing()
    _ = mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=180)
    warm_payload = {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "exp": int(time.time()) + 120,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
    }
    warm_token = jwt.encode(
        warm_payload,
        TEST_PRIVATE_KEY_PEM,
        algorithm=settings.AUTH_JWT_ALGORITHM,
        headers={"kid": "kid-current"},
    )
    _decode_token(warm_token)

    def _boom(_: str) -> str | None:
        raise RuntimeError("simulated refresh failure")

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _boom)
    payload = {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "exp": int(time.time()) + 120,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
    }
    token = jwt.encode(payload, TEST_PRIVATE_KEY_PEM, algorithm=settings.AUTH_JWT_ALGORITHM, headers={"kid": "kid-unknown"})
    decoded = _decode_token(token)
    assert decoded["tenant_id"] == payload["tenant_id"]


def test_unknown_kid_refresh_is_debounced_under_flood(monkeypatch):
    from app.core import secrets as secrets_module

    monkeypatch.setenv("SKELDIR_JWT_UNKNOWN_KID_REFRESH_DEBOUNCE_SECONDS", "30")
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_PUBLIC_KEY_RING",
        _jwt_ring_payload(current_kid="kid-current", key_material=TEST_PUBLIC_KEY_PEM),
    )
    reset_crypto_secret_caches_for_testing()

    refresh_calls = {"count": 0}

    def _counting_fetch(key: str) -> str | None:
        if key == "AUTH_JWT_PUBLIC_KEY_RING":
            refresh_calls["count"] += 1
        return getattr(settings, key, None)

    monkeypatch.setattr(secrets_module, "_read_secret_source_of_truth_value", _counting_fetch)
    payload = {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "exp": int(time.time()) + 120,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
    }
    token = jwt.encode(payload, TEST_PRIVATE_KEY_PEM, algorithm=settings.AUTH_JWT_ALGORITHM, headers={"kid": "kid-unknown"})

    for _ in range(25):
        _decode_token(token)

    assert refresh_calls["count"] <= 2

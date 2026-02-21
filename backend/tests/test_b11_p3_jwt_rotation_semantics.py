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


def _jwt_ring_payload(*, current_kid: str, keys: dict[str, str], previous_kids: list[str] | None = None) -> str:
    payload = {
        "current_kid": current_kid,
        "keys": keys,
    }
    if previous_kids is not None:
        payload["previous_kids"] = previous_kids
    return json.dumps(payload)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS", "1")
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setattr(settings, "AUTH_JWT_AUDIENCE", "skeldir-api")
    reset_crypto_secret_caches_for_testing()
    yield
    reset_crypto_secret_caches_for_testing()


def test_jwt_overlap_rotation_switches_kid_within_bound(monkeypatch):
    tenant_id = uuid4()
    user_id = uuid4()
    old_ring = _jwt_ring_payload(current_kid="kid-old", keys={"kid-old": "secret-old"})
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", old_ring)

    old_token = mint_internal_jwt(tenant_id=tenant_id, user_id=user_id, expires_in_seconds=180)
    old_header = jwt.get_unverified_header(old_token)
    assert old_header["kid"] == "kid-old"

    rotated_ring = _jwt_ring_payload(
        current_kid="kid-new",
        keys={"kid-old": "secret-old", "kid-new": "secret-new"},
        previous_kids=["kid-old"],
    )
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", rotated_ring)
    time.sleep(1.1)

    new_token = mint_internal_jwt(tenant_id=tenant_id, user_id=user_id, expires_in_seconds=180)
    new_header = jwt.get_unverified_header(new_token)
    assert new_header["kid"] == "kid-new"

    old_claims = _decode_token(old_token)
    assert old_claims["tenant_id"] == str(tenant_id)


def test_missing_kid_fails_when_ring_requires_kid(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        _jwt_ring_payload(current_kid="kid-1", keys={"kid-1": "secret-1"}),
    )
    payload = {
        "tenant_id": str(uuid4()),
        "sub": str(uuid4()),
        "exp": int(time.time()) + 120,
        "iss": settings.AUTH_JWT_ISSUER,
        "aud": settings.AUTH_JWT_AUDIENCE,
    }
    token_without_kid = jwt.encode(payload, "secret-1", algorithm=settings.AUTH_JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError):
        _decode_token(token_without_kid)


def test_keyring_refresh_failure_fails_closed_for_mint(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AUTH_JWT_SECRET",
        _jwt_ring_payload(current_kid="kid-1", keys={"kid-1": "secret-1"}),
    )
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
            keys={"k1": "s1", "k2": "s2", "k3": "s3", "k4": "s4"},
            previous_kids=["k2", "k3", "k4"],
        ),
    )
    with pytest.raises(RuntimeError, match="exceeds max accepted keys"):
        mint_internal_jwt(tenant_id=uuid4(), user_id=uuid4(), expires_in_seconds=60)

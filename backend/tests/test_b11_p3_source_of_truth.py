from __future__ import annotations

import json

from app.core.config import settings
from app.core.secrets import (
    reset_crypto_secret_caches_for_testing,
    validate_runtime_secret_contract,
)


def _ring_payload(current: str, key_name: str, value: str) -> str:
    return json.dumps({key_name: current, "keys": {current: value}})


def test_stage_requires_control_plane_for_crypto_secrets(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir")
    monkeypatch.setattr(settings, "ENVIRONMENT", "stage")
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", "stage-local-fallback")
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setattr(settings, "AUTH_JWT_AUDIENCE", "skeldir-api")
    monkeypatch.setattr(settings, "PLATFORM_TOKEN_ENCRYPTION_KEY", "stage-platform-fallback")
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "0")
    reset_crypto_secret_caches_for_testing()

    result = validate_runtime_secret_contract("readiness")
    assert not result.ok
    assert "SKELDIR_CONTROL_PLANE_ENABLED" in result.missing


def test_stage_accepts_control_plane_sourced_crypto_secrets(monkeypatch):
    from app.core import secrets as secrets_module

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://app_user:app_user@127.0.0.1:5432/skeldir")
    monkeypatch.setattr(settings, "ENVIRONMENT", "stage")
    monkeypatch.setattr(settings, "AUTH_JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
    monkeypatch.setattr(settings, "AUTH_JWT_AUDIENCE", "skeldir-api")
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", None)
    monkeypatch.setattr(settings, "PLATFORM_TOKEN_ENCRYPTION_KEY", None)
    monkeypatch.setenv("SKELDIR_CONTROL_PLANE_ENABLED", "1")
    reset_crypto_secret_caches_for_testing()

    def _fake_cp_fetch(contract, _path):
        if contract.key == "AUTH_JWT_SECRET":
            return _ring_payload("kid-1", "current_kid", "jwt-secret")
        if contract.key == "PLATFORM_TOKEN_ENCRYPTION_KEY":
            return _ring_payload("platform-1", "current_key_id", "platform-secret")
        if contract.key == "DATABASE_URL":
            return "postgresql://app_user:app_user@127.0.0.1:5432/skeldir"
        return "dummy"

    monkeypatch.setattr(secrets_module, "_fetch_value_from_aws", _fake_cp_fetch)

    result = validate_runtime_secret_contract("readiness")
    assert result.ok, result.missing

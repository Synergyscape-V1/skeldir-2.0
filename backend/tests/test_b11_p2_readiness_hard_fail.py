from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.config import settings
from app.core.secrets import assert_runtime_secret_contract


@pytest_asyncio.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_readiness_fails_closed_when_jwt_secret_missing(monkeypatch, api_client):
    monkeypatch.setenv("SKELDIR_REQUIRE_AUTH_SECRETS", "1")
    monkeypatch.setattr(settings, "AUTH_JWT_SECRET", None)
    monkeypatch.setattr(settings, "AUTH_JWT_JWKS_URL", None)

    ready = await api_client.get("/health/ready")
    health = await api_client.get("/api/health")
    api_ready = await api_client.get("/api/health/ready")

    assert ready.status_code == 503
    assert health.status_code == 503
    assert api_ready.status_code == 503
    assert "AUTH_JWT_SECRET|AUTH_JWT_JWKS_URL" in ready.json()["missing_required_secrets"]


@pytest.mark.asyncio
async def test_readiness_fails_closed_when_platform_envelope_key_missing(monkeypatch, api_client):
    monkeypatch.setattr(settings, "PLATFORM_TOKEN_ENCRYPTION_KEY", None)

    ready = await api_client.get("/health/ready")
    assert ready.status_code == 503
    assert "PLATFORM_TOKEN_ENCRYPTION_KEY" in ready.json()["missing_required_secrets"]


def test_worker_boot_contract_fails_without_database_secret(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    with pytest.raises(RuntimeError, match="runtime secret contract failed"):
        assert_runtime_secret_contract("worker")

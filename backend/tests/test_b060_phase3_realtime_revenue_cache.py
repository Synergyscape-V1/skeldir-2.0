"""
B0.6 Phase 3: realtime revenue cache + stampede prevention tests.
"""

from __future__ import annotations

import asyncio
import os
import time
from uuid import UUID, uuid4

from app.testing.jwt_rs256 import TEST_PRIVATE_KEY_PEM, private_ring_payload, public_ring_payload

os.environ["AUTH_JWT_SECRET"] = private_ring_payload()
os.environ["AUTH_JWT_PUBLIC_KEY_RING"] = public_ring_payload()
os.environ["AUTH_JWT_ALGORITHM"] = "RS256"
os.environ["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
os.environ["AUTH_JWT_AUDIENCE"] = "skeldir-api"
os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"] = "test-platform-key"
os.environ["PLATFORM_TOKEN_KEY_ID"] = "test-key"

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.secrets import (
    reset_crypto_secret_caches_for_testing,
    reset_jwt_verification_pg_cache_for_testing,
    seed_jwt_verification_pg_cache_for_testing,
)
from app.main import app
from app.services import realtime_revenue_providers as providers
from tests.builders.core_builders import (
    build_platform_connection,
    build_platform_credentials,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _reset_jwt_verifier_state() -> None:
    reset_crypto_secret_caches_for_testing()
    reset_jwt_verification_pg_cache_for_testing()
    try:
        seed_jwt_verification_pg_cache_for_testing(raw_ring=os.environ["AUTH_JWT_PUBLIC_KEY_RING"])
    except Exception:
        pass
    yield
    reset_crypto_secret_caches_for_testing()
    reset_jwt_verification_pg_cache_for_testing()


def _build_token(tenant_id: UUID) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-1",
        "iss": os.environ["AUTH_JWT_ISSUER"],
        "aud": os.environ["AUTH_JWT_AUDIENCE"],
        "iat": now,
        "exp": now + 3600,
        "tenant_id": str(tenant_id),
    }
    return jwt.encode(
        payload,
        TEST_PRIVATE_KEY_PEM,
        algorithm=os.environ["AUTH_JWT_ALGORITHM"],
        headers={"kid": "kid-1"},
    )


async def _make_client_request(path: str, token: str, correlation_id: str) -> tuple[int, dict, dict]:
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            path,
            headers={
                "X-Correlation-ID": correlation_id,
                "Authorization": f"Bearer {token}",
            },
        )
    return resp.status_code, resp.json() if resp.content else {}, dict(resp.headers)


async def test_cache_hit_avoids_upstream_call(test_tenant, monkeypatch):
    counter = {"count": 0}

    class CountingDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            counter["count"] += 1
            await asyncio.sleep(0.05)
            return await super().fetch_realtime(ctx)

    connection = await build_platform_connection(
        tenant_id=test_tenant,
        platform="dummy",
        platform_account_id="dummy",
    )
    await build_platform_credentials(
        tenant_id=test_tenant,
        platform="dummy",
        platform_connection_id=connection["id"],
        access_token="dummy-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )

    registry = providers.ProviderRegistry(
        providers=[CountingDummy(raw_revenue_micros=1_234_500, event_count=7)]
    )
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    status1, body1, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    status2, body2, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )

    assert status1 == 200
    assert status2 == 200
    assert counter["count"] == 1
    assert body1["total_revenue"] == body2["total_revenue"]
    assert body1["last_updated"] == body2["last_updated"]


async def test_stampede_prevention_singleflight(test_tenant, monkeypatch):
    counter = {"count": 0}

    class CountingDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            counter["count"] += 1
            await asyncio.sleep(0.2)
            return await super().fetch_realtime(ctx)

    connection = await build_platform_connection(
        tenant_id=test_tenant,
        platform="dummy",
        platform_account_id="dummy",
    )
    await build_platform_credentials(
        tenant_id=test_tenant,
        platform="dummy",
        platform_connection_id=connection["id"],
        access_token="dummy-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )

    registry = providers.ProviderRegistry(
        providers=[CountingDummy(raw_revenue_micros=5_555_500, event_count=1)]
    )
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    tasks = [
        _make_client_request("/api/attribution/revenue/realtime", token, str(uuid4()))
        for _ in range(10)
    ]
    results = await asyncio.gather(*tasks)

    assert counter["count"] == 1
    statuses = [status for status, _, _ in results]
    assert all(status == 200 for status in statuses)

    last_updated_values = {body["last_updated"] for _, body, _ in results}
    assert len(last_updated_values) == 1


async def test_cross_tenant_isolation(test_tenant_pair, monkeypatch):
    tenant_a, tenant_b = test_tenant_pair
    counter = {"count": 0}

    class CountingDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            counter["count"] += 1
            await asyncio.sleep(0.1)
            return await super().fetch_realtime(ctx)

    for tenant_id in (tenant_a, tenant_b):
        connection = await build_platform_connection(
            tenant_id=tenant_id,
            platform="dummy",
            platform_account_id="dummy",
        )
        await build_platform_credentials(
            tenant_id=tenant_id,
            platform="dummy",
            platform_connection_id=connection["id"],
            access_token="dummy-token",
            encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
        )

    registry = providers.ProviderRegistry(
        providers=[CountingDummy(raw_revenue_micros=8_888_800, event_count=2)]
    )
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token_a = _build_token(tenant_a)
    token_b = _build_token(tenant_b)

    tasks = [
        _make_client_request("/api/v1/revenue/realtime", token_a, str(uuid4())),
        _make_client_request("/api/v1/revenue/realtime", token_b, str(uuid4())),
    ]
    results = await asyncio.gather(*tasks)

    assert counter["count"] == 2
    assert all(status == 200 for status, _, _ in results)


async def test_failure_stampede_cooldown(test_tenant, monkeypatch):
    counter = {"count": 0}
    monkeypatch.setenv("REALTIME_REVENUE_ERROR_COOLDOWN_SECONDS", "5")
    monkeypatch.setenv("REALTIME_REVENUE_SINGLEFLIGHT_WAIT_SECONDS", "2")

    class FailingDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            counter["count"] += 1
            await asyncio.sleep(0.1)
            raise providers.ProviderFetchError(
                "upstream down",
                error_type="upstream",
                retry_after_seconds=5,
                provider_key="dummy",
            )

    connection = await build_platform_connection(
        tenant_id=test_tenant,
        platform="dummy",
        platform_account_id="dummy",
    )
    await build_platform_credentials(
        tenant_id=test_tenant,
        platform="dummy",
        platform_connection_id=connection["id"],
        access_token="dummy-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )

    registry = providers.ProviderRegistry(providers=[FailingDummy()])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    tasks = [
        _make_client_request("/api/attribution/revenue/realtime", token, str(uuid4()))
        for _ in range(10)
    ]
    results = await asyncio.gather(*tasks)

    assert counter["count"] == 1
    assert all(status == 503 for status, _, _ in results)
    assert all("retry-after" in {k.lower() for k in headers} for _, _, headers in results)

    status, _, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 503
    assert counter["count"] == 1

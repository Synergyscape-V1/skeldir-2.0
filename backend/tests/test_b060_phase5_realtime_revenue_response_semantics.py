"""
B0.6 Phase 5: realtime revenue response semantics (fetch-time freshness, verified=false).
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
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
from sqlalchemy import text

from app.core import clock as clock_module
from app.core.secrets import (
    reset_crypto_secret_caches_for_testing,
    reset_jwt_verification_pg_cache_for_testing,
    seed_jwt_verification_pg_cache_for_testing,
)
from app.db.session import AsyncSessionLocal, set_tenant_guc_async
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


class FrozenClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def set(self, now: datetime) -> None:
        self._now = now

    def utcnow(self) -> datetime:
        return self._now


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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


async def _seed_dummy_connection(tenant_id: UUID) -> None:
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


async def test_verified_is_explicit_false_across_paths(test_tenant, monkeypatch):
    frozen = FrozenClock(datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(clock_module, "utcnow", frozen.utcnow)
    monkeypatch.setenv("REALTIME_REVENUE_CACHE_TTL_SECONDS", "30")
    monkeypatch.setenv("REALTIME_REVENUE_SINGLEFLIGHT_WAIT_SECONDS", "2")

    class SlowDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            await asyncio.sleep(0.2)
            return await super().fetch_realtime(ctx)

    await _seed_dummy_connection(test_tenant)
    registry = providers.ProviderRegistry(providers=[SlowDummy(raw_revenue_micros=1_234_500, event_count=7)])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    tasks = [
        _make_client_request("/api/attribution/revenue/realtime", token, str(uuid4()))
        for _ in range(3)
    ]
    results = await asyncio.gather(*tasks)

    assert all(status == 200 for status, _, _ in results)
    assert all(body["verified"] is False for _, body, _ in results)

    frozen.set(datetime(2026, 2, 2, 12, 0, 10, tzinfo=timezone.utc))
    status, body, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 200
    assert body["verified"] is False


async def test_last_updated_equals_fetch_time_not_request_time(test_tenant, monkeypatch):
    t0 = datetime(2026, 2, 2, 13, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=12)
    frozen = FrozenClock(t0)
    monkeypatch.setattr(clock_module, "utcnow", frozen.utcnow)
    monkeypatch.setenv("REALTIME_REVENUE_CACHE_TTL_SECONDS", "60")

    await _seed_dummy_connection(test_tenant)
    registry = providers.ProviderRegistry(providers=[providers.DummyRevenueProvider(raw_revenue_micros=2_000_000)])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    status, body, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 200
    assert _parse_iso_datetime(body["last_updated"]) == t0

    frozen.set(t1)
    status, body, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 200
    assert _parse_iso_datetime(body["last_updated"]) == t0
    assert body["data_freshness_seconds"] == int((t1 - t0).total_seconds())


async def test_follower_reports_leader_fetch_time(test_tenant, monkeypatch):
    t0 = datetime(2026, 2, 2, 14, 0, 0, tzinfo=timezone.utc)
    frozen = FrozenClock(t0)
    monkeypatch.setattr(clock_module, "utcnow", frozen.utcnow)
    monkeypatch.setenv("REALTIME_REVENUE_CACHE_TTL_SECONDS", "30")
    monkeypatch.setenv("REALTIME_REVENUE_SINGLEFLIGHT_WAIT_SECONDS", "2")

    class SlowDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            await asyncio.sleep(0.2)
            return await super().fetch_realtime(ctx)

    await _seed_dummy_connection(test_tenant)
    registry = providers.ProviderRegistry(providers=[SlowDummy(raw_revenue_micros=5_000_000, event_count=1)])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    tasks = [
        _make_client_request("/api/attribution/revenue/realtime", token, str(uuid4()))
        for _ in range(5)
    ]
    results = await asyncio.gather(*tasks)
    last_updated_values = {_parse_iso_datetime(body["last_updated"]) for _, body, _ in results}

    assert all(status == 200 for status, _, _ in results)
    assert last_updated_values == {t0}


async def test_failure_does_not_mutate_fetch_time(test_tenant, monkeypatch):
    t0 = datetime(2026, 2, 2, 15, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=61)
    frozen = FrozenClock(t0)
    monkeypatch.setattr(clock_module, "utcnow", frozen.utcnow)
    monkeypatch.setenv("REALTIME_REVENUE_CACHE_TTL_SECONDS", "60")
    monkeypatch.setenv("REALTIME_REVENUE_ERROR_COOLDOWN_SECONDS", "5")

    await _seed_dummy_connection(test_tenant)
    registry = providers.ProviderRegistry(providers=[providers.DummyRevenueProvider(raw_revenue_micros=9_000_000)])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    status, body, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 200
    assert _parse_iso_datetime(body["last_updated"]) == t0

    class FailingDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            raise providers.ProviderFetchError(
                "upstream down",
                error_type="upstream",
                retry_after_seconds=5,
                provider_key="dummy",
            )

    frozen.set(t1)
    registry = providers.ProviderRegistry(providers=[FailingDummy()])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    status, _, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 503

    async with AsyncSessionLocal() as session:
        await set_tenant_guc_async(session, test_tenant, local=False)
        result = await session.execute(
            text(
                """
                SELECT data_as_of
                FROM revenue_cache_entries
                WHERE tenant_id = :tenant_id AND cache_key = :cache_key
                """
            ),
            {"tenant_id": str(test_tenant), "cache_key": "realtime_revenue:shared:v1"},
        )
        data_as_of = result.scalar()

    assert data_as_of == t0


async def test_freshness_seconds_computation(test_tenant, monkeypatch):
    t0 = datetime(2026, 2, 2, 16, 0, 0, tzinfo=timezone.utc)
    frozen = FrozenClock(t0)
    monkeypatch.setattr(clock_module, "utcnow", frozen.utcnow)
    monkeypatch.setenv("REALTIME_REVENUE_CACHE_TTL_SECONDS", "60")

    await _seed_dummy_connection(test_tenant)
    registry = providers.ProviderRegistry(providers=[providers.DummyRevenueProvider(raw_revenue_micros=3_000_000)])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(test_tenant)
    status, body, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 200
    assert body["data_freshness_seconds"] == 0

    frozen.set(t0 - timedelta(seconds=10))
    status, body, _ = await _make_client_request(
        "/api/attribution/revenue/realtime", token, str(uuid4())
    )
    assert status == 200
    assert body["data_freshness_seconds"] == 0

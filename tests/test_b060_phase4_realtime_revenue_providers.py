"""
B0.6 Phase 4: Provider adapters, registry dispatch, and realtime revenue integration.
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient, MockTransport, Response, Timeout
from sqlalchemy import text

os.environ["TESTING"] = "1"
os.environ["AUTH_JWT_SECRET"] = "test-secret"
os.environ["AUTH_JWT_ALGORITHM"] = "HS256"
os.environ["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
os.environ["AUTH_JWT_AUDIENCE"] = "skeldir-api"
os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", "test-platform-key")
os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", "test-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import realtime_revenue_providers as providers  # noqa: E402
from tests.builders.core_builders import (  # noqa: E402
    build_platform_connection,
    build_platform_credentials,
    build_tenant,
)

pytestmark = pytest.mark.asyncio


def _sync_database_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for Phase 4 tests")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


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
        os.environ["AUTH_JWT_SECRET"],
        algorithm=os.environ["AUTH_JWT_ALGORITHM"],
    )


class HttpxClientAdapter:
    def __init__(self, base_url: str, transport) -> None:
        self._base_url = base_url
        self._transport = transport
        self._timeout = Timeout(5.0, connect=2.0)

    async def get(self, path: str, *, headers: dict[str, str], params: dict[str, str]):
        async with AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            resp = await client.get(path, headers=headers, params=params)
        return providers.HttpResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            json_body=resp.json() if resp.content else {},
        )


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations():
    config = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    sync_url = _sync_database_url()
    config.set_main_option("sqlalchemy.url", sync_url)
    os.environ["MIGRATION_DATABASE_URL"] = sync_url
    command.upgrade(config, "head")


async def _fetch_cache_row(tenant_id: UUID):
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        result = await conn.execute(
            text(
                "SELECT payload FROM revenue_cache_entries "
                "WHERE tenant_id = :tenant_id AND cache_key = :cache_key"
            ),
            {
                "tenant_id": str(tenant_id),
                "cache_key": "realtime_revenue:shared:v1",
            },
        )
        return result.mappings().first()


async def test_stripe_adapter_request_and_parsing():
    def handler(request):
        assert request.url.path == "/v1/balance_transactions"
        assert request.url.params.get("limit") == "100"
        assert request.headers.get("Authorization") == "Bearer test-token"
        assert request.headers.get("Stripe-Account") == "acct_123"
        assert request.headers.get("X-Correlation-ID") == "00000000-0000-0000-0000-000000000000"
        return Response(
            200,
            json={
                "data": [
                    {"amount": 2500, "type": "charge"},
                    {"amount": -200, "type": "fee"},
                    {"amount": 1500, "type": "charge"},
                ]
            },
        )

    provider = providers.StripeRevenueProvider(
        base_url="https://stripe.test",
        client=HttpxClientAdapter("https://stripe.test", MockTransport(handler)),
    )
    ctx = providers.ProviderContext(
        tenant_id=uuid4(),
        platform_connection=providers.ProviderConnection(
            id=uuid4(),
            platform="stripe",
            platform_account_id="acct_123",
            status="active",
            metadata=None,
            updated_at=None,
        ),
        credentials=providers.ProviderCredentials(
            access_token="test-token",
            refresh_token=None,
            expires_at=None,
            scope=None,
            token_type=None,
            key_id="test-key",
        ),
        correlation_id=UUID("00000000-0000-0000-0000-000000000000"),
        now=datetime.now(timezone.utc),
    )

    result = await provider.fetch_realtime(ctx)
    assert result.total_revenue_cents == 4000
    assert result.event_count == 2
    assert result.source == "stripe"


async def test_stripe_adapter_error_mapping():
    async def _assert_error(status_code: int, expected_type: str):
        def handler(_request):
            return Response(status_code)

        provider = providers.StripeRevenueProvider(
            base_url="https://stripe.test",
            client=HttpxClientAdapter("https://stripe.test", MockTransport(handler)),
            max_attempts=1,
        )
        ctx = providers.ProviderContext(
            tenant_id=uuid4(),
            platform_connection=providers.ProviderConnection(
                id=uuid4(),
                platform="stripe",
                platform_account_id="acct_123",
                status="active",
                metadata=None,
                updated_at=None,
            ),
            credentials=providers.ProviderCredentials(
                access_token="test-token",
                refresh_token=None,
                expires_at=None,
                scope=None,
                token_type=None,
                key_id="test-key",
            ),
            correlation_id=uuid4(),
            now=datetime.now(timezone.utc),
        )
        with pytest.raises(providers.ProviderFetchError) as exc:
            await provider.fetch_realtime(ctx)
        assert exc.value.error_type == expected_type

    await _assert_error(401, "auth")
    await _assert_error(403, "auth")
    await _assert_error(429, "rate_limit")
    await _assert_error(500, "upstream")


async def test_dummy_provider_normalizes_micros():
    provider = providers.DummyRevenueProvider(raw_revenue_micros=120_000, event_count=1)
    ctx = providers.ProviderContext(
        tenant_id=uuid4(),
        platform_connection=providers.ProviderConnection(
            id=uuid4(),
            platform="dummy",
            platform_account_id="dummy",
            status="active",
            metadata=None,
            updated_at=None,
        ),
        credentials=providers.ProviderCredentials(
            access_token="dummy",
            refresh_token=None,
            expires_at=None,
            scope=None,
            token_type=None,
            key_id="dummy",
        ),
        correlation_id=uuid4(),
        now=datetime.now(timezone.utc),
    )

    result = await provider.fetch_realtime(ctx)
    assert result.total_revenue_cents == 12
    assert result.event_count == 1


async def test_system_integration_realtime_revenue_refresh(monkeypatch):
    tenant = await build_tenant()
    tenant_id = tenant["tenant_id"]

    connection = await build_platform_connection(
        tenant_id=tenant_id,
        platform="stripe",
        platform_account_id="acct_test",
    )
    await build_platform_credentials(
        tenant_id=tenant_id,
        platform="stripe",
        platform_connection_id=connection["id"],
        access_token="stripe-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )

    fake_stripe = FastAPI()

    @fake_stripe.get("/v1/balance_transactions")
    async def _balance_transactions(request: Request):
        assert request.headers.get("Authorization") == "Bearer stripe-token"
        return {
            "data": [
                {"amount": 1200, "type": "charge"},
                {"amount": 800, "type": "charge"},
            ]
        }

    registry = providers.ProviderRegistry(
        providers=[
            providers.StripeRevenueProvider(
                base_url="http://stripe.test",
                client=HttpxClientAdapter("http://stripe.test", ASGITransport(app=fake_stripe)),
            )
        ]
    )
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(tenant_id)
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_revenue"] == 20.0
    assert body["verified"] is False
    assert body["data_freshness_seconds"] >= 0
    assert UUID(body["tenant_id"]) == tenant_id

    cache_row = await _fetch_cache_row(tenant_id)
    assert cache_row is not None


async def test_polymorphism_registry_dispatch_and_aggregation(monkeypatch):
    tenant = await build_tenant()
    tenant_id = tenant["tenant_id"]

    stripe_connection = await build_platform_connection(
        tenant_id=tenant_id,
        platform="stripe",
        platform_account_id="acct_test",
    )
    dummy_connection = await build_platform_connection(
        tenant_id=tenant_id,
        platform="dummy",
        platform_account_id="dummy",
    )

    await build_platform_credentials(
        tenant_id=tenant_id,
        platform="stripe",
        platform_connection_id=stripe_connection["id"],
        access_token="stripe-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )
    await build_platform_credentials(
        tenant_id=tenant_id,
        platform="dummy",
        platform_connection_id=dummy_connection["id"],
        access_token="dummy-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )

    fake_stripe = FastAPI()

    @fake_stripe.get("/v1/balance_transactions")
    async def _balance_transactions(_request: Request):
        return {
            "data": [
                {"amount": 3000, "type": "charge"},
            ]
        }

    registry = providers.ProviderRegistry(
        providers=[
            providers.StripeRevenueProvider(
                base_url="http://stripe.test",
                client=HttpxClientAdapter("http://stripe.test", ASGITransport(app=fake_stripe)),
            ),
            providers.DummyRevenueProvider(raw_revenue_micros=250_000, event_count=2),
        ]
    )
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(tenant_id)
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is False
    assert sorted(body["sources"]) == ["dummy", "stripe"]
    assert body["revenue_total"] == 30.25


async def test_stampede_singleflight_per_provider(monkeypatch):
    tenant = await build_tenant()
    tenant_id = tenant["tenant_id"]

    stripe_connection = await build_platform_connection(
        tenant_id=tenant_id,
        platform="stripe",
        platform_account_id="acct_test",
    )
    dummy_connection = await build_platform_connection(
        tenant_id=tenant_id,
        platform="dummy",
        platform_account_id="dummy",
    )

    await build_platform_credentials(
        tenant_id=tenant_id,
        platform="stripe",
        platform_connection_id=stripe_connection["id"],
        access_token="stripe-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )
    await build_platform_credentials(
        tenant_id=tenant_id,
        platform="dummy",
        platform_connection_id=dummy_connection["id"],
        access_token="dummy-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )

    fake_stripe = FastAPI()

    @fake_stripe.get("/v1/balance_transactions")
    async def _balance_transactions(_request: Request):
        await asyncio.sleep(0.1)
        return {"data": [{"amount": 1000, "type": "charge"}]}

    counter = {"stripe": 0, "dummy": 0}

    class CountingStripe(providers.StripeRevenueProvider):
        async def fetch_realtime(self, ctx):
            counter["stripe"] += 1
            return await super().fetch_realtime(ctx)

    class CountingDummy(providers.DummyRevenueProvider):
        async def fetch_realtime(self, ctx):
            counter["dummy"] += 1
            return await super().fetch_realtime(ctx)

    registry = providers.ProviderRegistry(
        providers=[
            CountingStripe(
                base_url="http://stripe.test",
                client=HttpxClientAdapter("http://stripe.test", ASGITransport(app=fake_stripe)),
            ),
            CountingDummy(raw_revenue_micros=100_000, event_count=1),
        ]
    )
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)

    token = _build_token(tenant_id)
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [
            client.get(
                "/api/attribution/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {token}",
                },
            )
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

    assert all(resp.status_code == 200 for resp in responses)
    assert counter["stripe"] == 1
    assert counter["dummy"] == 1


async def test_failure_cooldown_and_retry_after(monkeypatch):
    tenant = await build_tenant()
    tenant_id = tenant["tenant_id"]

    connection = await build_platform_connection(
        tenant_id=tenant_id,
        platform="stripe",
        platform_account_id="acct_test",
    )
    await build_platform_credentials(
        tenant_id=tenant_id,
        platform="stripe",
        platform_connection_id=connection["id"],
        access_token="stripe-token",
        encryption_key=os.environ["PLATFORM_TOKEN_ENCRYPTION_KEY"],
    )

    counter = {"stripe": 0}

    class FailingStripe(providers.StripeRevenueProvider):
        async def fetch_realtime(self, ctx):
            counter["stripe"] += 1
            raise providers.ProviderFetchError(
                "rate_limited",
                error_type="rate_limit",
                retry_after_seconds=5,
                provider_key="stripe",
            )

    registry = providers.ProviderRegistry(providers=[FailingStripe()])
    monkeypatch.setattr(providers, "DEFAULT_PROVIDER_REGISTRY", registry)
    monkeypatch.setenv("REALTIME_REVENUE_ERROR_COOLDOWN_SECONDS", "5")
    monkeypatch.setenv("REALTIME_REVENUE_SINGLEFLIGHT_WAIT_SECONDS", "2")

    token = _build_token(tenant_id)
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [
            client.get(
                "/api/attribution/revenue/realtime",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "Authorization": f"Bearer {token}",
                },
            )
            for _ in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        status_codes = [resp.status_code for resp in responses]
        assert all(status == 503 for status in status_codes)
        assert all(
            "retry-after" in {k.lower() for k in resp.headers}
            for resp in responses
        )

        resp = await client.get(
            "/api/attribution/revenue/realtime",
            headers={
                "X-Correlation-ID": str(uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert resp.status_code == 503
    assert counter["stripe"] == 1

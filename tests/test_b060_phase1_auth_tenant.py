"""
B0.6 Phase 1: JWT auth + tenant boundary enforcement tests.
"""

import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

os.environ["TESTING"] = "1"
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from app.testing.jwt_rs256 import (  # noqa: E402
    TEST_PRIVATE_KEY_PEM,
    private_ring_payload,
    public_ring_payload,
)

os.environ["AUTH_JWT_SECRET"] = private_ring_payload()
os.environ["AUTH_JWT_PUBLIC_KEY_RING"] = public_ring_payload()
os.environ["AUTH_JWT_ALGORITHM"] = "RS256"
os.environ["AUTH_JWT_ISSUER"] = "https://issuer.skeldir.test"
os.environ["AUTH_JWT_AUDIENCE"] = "skeldir-api"

from app.main import app  # noqa: E402

pytestmark = pytest.mark.asyncio


def _build_token(tenant_id: UUID | None) -> str:
    now = int(time.time())
    payload = {
        "sub": "user-1",
        "iss": os.environ["AUTH_JWT_ISSUER"],
        "aud": os.environ["AUTH_JWT_AUDIENCE"],
        "iat": now,
        "exp": now + 3600,
    }
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)
    return jwt.encode(
        payload,
        TEST_PRIVATE_KEY_PEM,
        algorithm=os.environ["AUTH_JWT_ALGORITHM"],
        headers={"kid": "kid-1"},
    )


@asynccontextmanager
async def _fake_session(tenant_id: UUID, calls: list[UUID]):
    calls.append(tenant_id)
    yield object()


async def test_missing_token_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/revenue/realtime",
            headers={"X-Correlation-ID": "00000000-0000-0000-0000-000000000000"},
        )
    assert resp.status_code == 401
    assert resp.headers.get("content-type", "").startswith("application/problem+json")


async def test_invalid_token_returns_401():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": "00000000-0000-0000-0000-000000000000",
                "Authorization": "Bearer not-a-jwt",
            },
        )
    assert resp.status_code == 401


async def test_missing_tenant_claim_returns_401():
    token = _build_token(None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": "00000000-0000-0000-0000-000000000000",
                "Authorization": f"Bearer {token}",
            },
        )
    assert resp.status_code == 401


async def test_valid_token_sets_tenant_and_calls_session(monkeypatch):
    tenant_id = uuid4()
    token = _build_token(tenant_id)
    calls: list[UUID] = []

    @asynccontextmanager
    async def _patched_get_session(tid: UUID, user_id: UUID | None = None):
        async with _fake_session(tid, calls) as session:
            yield session

    monkeypatch.setattr("app.db.session.get_session", _patched_get_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": "00000000-0000-0000-0000-000000000000",
                "Authorization": f"Bearer {token}",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert UUID(body["tenant_id"]) == tenant_id
    assert calls == [tenant_id]


async def test_two_tokens_yield_distinct_tenants(monkeypatch):
    tenant_a = uuid4()
    tenant_b = uuid4()
    token_a = _build_token(tenant_a)
    token_b = _build_token(tenant_b)
    calls: list[UUID] = []

    @asynccontextmanager
    async def _patched_get_session(tid: UUID, user_id: UUID | None = None):
        async with _fake_session(tid, calls) as session:
            yield session

    monkeypatch.setattr("app.db.session.get_session", _patched_get_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_a = await client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": "00000000-0000-0000-0000-000000000000",
                "Authorization": f"Bearer {token_a}",
            },
        )
        resp_b = await client.get(
            "/api/v1/revenue/realtime",
            headers={
                "X-Correlation-ID": "00000000-0000-0000-0000-000000000000",
                "Authorization": f"Bearer {token_b}",
            },
        )

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert UUID(resp_a.json()["tenant_id"]) == tenant_a
    assert UUID(resp_b.json()["tenant_id"]) == tenant_b
    assert calls == [tenant_a, tenant_b]

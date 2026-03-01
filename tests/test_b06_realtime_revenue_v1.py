"""
B0.6 Phase 0: Canonical v1 realtime revenue contract alignment tests.
"""

import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import jwt
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


async def test_realtime_revenue_v1_response_shape():
    tenant_id = uuid4()
    token = _build_token(tenant_id)
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
    assert isinstance(body["interval"], str)
    assert isinstance(body["currency"], str)
    assert isinstance(body["revenue_total"], (int, float))
    assert isinstance(body["verified"], bool)
    assert "data_as_of" in body
    assert isinstance(body["data_as_of"], str)
    assert "sources" in body
    assert isinstance(body["sources"], list)


async def test_realtime_revenue_v1_requires_authorization():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/revenue/realtime",
            headers={"X-Correlation-ID": "00000000-0000-0000-0000-000000000000"},
        )

    assert resp.status_code == 401
    body = resp.json()
    assert body["status"] == 401
    assert body["correlation_id"] == "00000000-0000-0000-0000-000000000000"

import os
import json
import hashlib
import hmac
import base64
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure RLS-friendly settings
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from app.main import app  # noqa: E402


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def tenant_with_secret():
    tenant_id = uuid4()
    api_key = f"obs_key_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    secret = "shopify_secret"
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    await conn.execute(
        """
        INSERT INTO tenants (id, api_key_hash, name, notification_email, shopify_webhook_secret, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        """,
        str(tenant_id),
        api_key_hash,
        f"Obs Tenant {str(tenant_id)[:8]}",
        f"obs_{str(tenant_id)[:8]}@test.local",
        secret,
    )
    await conn.close()
    return tenant_id, api_key, secret


def sign_shopify(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


@pytest.mark.asyncio
async def test_health_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        liveness = await client.get("/health")
        readiness = await client.get("/health/ready")
    assert liveness.status_code == 200
    assert liveness.json()["status"] == "healthy"
    assert readiness.status_code in (200, 503)
    assert "status" in readiness.json()


@pytest.mark.asyncio
async def test_metrics_exposed_and_counters_increment(tenant_with_secret):
    tenant_id, api_key, secret = tenant_with_secret
    body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "5.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    # Shopify expects base64 signature; reuse hex then convert to base64 bytes? real helper uses base64; mimic using existing API
    signature = sign_shopify(body, secret)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        metrics_resp = await client.get("/metrics")

    assert metrics_resp.status_code == 200
    metrics_text = metrics_resp.text
    assert "events_ingested_total" in metrics_text
    assert "ingestion_duration_seconds_bucket" in metrics_text
    assert str(tenant_id) in metrics_text


@pytest.mark.asyncio
async def test_correlation_header_present(tenant_with_secret):
    _, api_key, secret = tenant_with_secret
    body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "7.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    signature = sign_shopify(body, secret)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    assert resp.headers.get("X-Correlation-ID")

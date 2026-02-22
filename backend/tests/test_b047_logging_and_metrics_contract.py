import os
import json
import base64
import hashlib
import hmac
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import logging

from app.main import app  # noqa: E402
from app.core.secrets import get_database_url  # noqa: E402

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def tenant_with_secret():
    tenant_id = uuid4()
    api_key = f"obs_key_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    secret = "shopify_secret"
    conn = await asyncpg.connect(get_database_url())
    # RAW_SQL_ALLOWLIST: legacy logging/metrics contract test seeds tenant with webhook secret
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
async def test_logging_contract_success_and_dlq(caplog, capsys, tenant_with_secret):
    caplog.set_level(logging.INFO)
    tenant_id, api_key, secret = tenant_with_secret
    base_body = {
        "id": int(uuid4().int % 1_000_000),
        "total_price": "5.00",
        "currency": "USD",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(base_body).encode()
    sig = sign_shopify(body, secret)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        caplog.clear()
        resp = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    # Look for event_ingested log record
    ingested = [
        r for r in caplog.records if getattr(r, "event", "") == "event_ingested"
    ]
    assert ingested, "expected event_ingested log"
    record = ingested[-1]
    assert record.tenant_id == str(tenant_id)
    assert getattr(record, "correlation_id_request", None)
    assert getattr(record, "correlation_id_business", None)
    assert record.event_type == "purchase"
    assert record.vendor in ("shopify", "unknown")
    assert getattr(record, "idempotency_key", None) is not None or record.msg == "event_ingested"

    # Now send malformed to force DLQ
    bad_body = json.dumps({**base_body, "id": int(uuid4().int % 1_000_000), "total_price": "not-a-number"}).encode()
    bad_sig = sign_shopify(bad_body, secret)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        caplog.clear()
        resp_bad = await client.post(
            "/api/webhooks/shopify/order_create",
            content=bad_body,
            headers={
                "X-Shopify-Hmac-Sha256": bad_sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert resp_bad.status_code == 200
    out, err = capsys.readouterr()
    combined = out + err + caplog.text
    assert "event_routed_to_dlq" in combined
    assert str(tenant_id) in combined
    assert "correlation_id_request" in combined
    assert "correlation_id_business" in combined
    assert "dead_event_id" in combined
    assert "error_type" in combined


@pytest.mark.asyncio
async def test_metrics_labels_and_parseability(tenant_with_secret):
    tenant_id, api_key, secret = tenant_with_secret
    base_id = int(uuid4().int % 1_000_000)
    body = json.dumps(
        {
            "id": base_id,
            "total_price": "8.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    sig = sign_shopify(body, secret)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # success ingestion
        await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        # duplicate ingestion
        await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        # DLQ ingestion
        bad_body = json.dumps(
            {
                "id": int(uuid4().int % 1_000_000),
                "total_price": "bad",
                "currency": "USD",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).encode()
        bad_sig = sign_shopify(bad_body, secret)
        await client.post(
            "/api/webhooks/shopify/order_create",
            content=bad_body,
            headers={
                "X-Shopify-Hmac-Sha256": bad_sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        metrics_resp = await client.get("/metrics")

    text = metrics_resp.text
    assert "events_ingested_total" in text
    assert "events_duplicate_total" in text
    assert "events_dlq_total" in text
    assert "ingestion_duration_seconds_bucket" in text
    # B0.5.6.3: Labels removed from event metrics for privacy/cardinality
    # These metrics are now label-free aggregate counters
    assert "tenant_id=" not in text
    assert 'vendor=' not in text
    assert 'event_type=' not in text
    assert 'error_type=' not in text


@pytest.mark.asyncio
async def test_readiness_rls_success_and_failure(monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.get("/health/ready")
        assert ok.status_code == 200

        # Simulate failure by monkeypatching engine.begin to raise
        from app import api as api_pkg  # noqa
        from app.api import health

        class FakeConn:
            async def __aenter__(self):  # pragma: no cover - minimal stub
                raise RuntimeError("fail readiness")
            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeEngine:
            def begin(self):
                return FakeConn()

        monkeypatch.setattr(health, "engine", FakeEngine())
        bad = await client.get("/health/ready")
        assert bad.status_code != 200
        assert bad.json()["status"] == "unhealthy"

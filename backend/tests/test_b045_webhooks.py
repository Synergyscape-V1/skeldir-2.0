"""
B0.4.5 Webhook ingress tests
"""
import os
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL

import asyncio
import pytest
import pytest_asyncio
import asyncpg
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text, func

# Force app_user DSN for RLS validation before importing app
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from app.main import app  # noqa: E402
from app.db.session import engine, get_session  # noqa: E402
from app.models import AttributionEvent, DeadEvent  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(scope="session")
async def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


async def create_tenant_with_secrets():
    tenant_id = uuid4()
    api_key = f"test_api_key_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    secrets = {
        "shopify_webhook_secret": "shopify_secret",
        "stripe_webhook_secret": "stripe_secret",
        "paypal_webhook_secret": "paypal_secret",
        "woocommerce_webhook_secret": "woo_secret",
    }
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    await conn.execute(
        """
        INSERT INTO tenants (id, api_key_hash, name, notification_email,
                             shopify_webhook_secret, stripe_webhook_secret,
                             paypal_webhook_secret, woocommerce_webhook_secret,
                             created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
        """,
        str(tenant_id),
        api_key_hash,
        f"Webhook Tenant {str(tenant_id)[:8]}",
        f"webhook_{str(tenant_id)[:8]}@test.local",
        secrets["shopify_webhook_secret"],
        secrets["stripe_webhook_secret"],
        secrets["paypal_webhook_secret"],
        secrets["woocommerce_webhook_secret"],
    )
    await conn.close()
    return tenant_id, api_key, secrets


def sign_shopify(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def sign_stripe(body: bytes, secret: str) -> str:
    ts = int(datetime.now(timezone.utc).timestamp())
    signed_payload = f"{ts}.{body.decode()}".encode()
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def sign_paypal(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def sign_woocommerce(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


@pytest.mark.asyncio
async def test_shopify_success_and_rls_isolation():
    tenant_a, api_key_a, secrets = await create_tenant_with_secrets()
    tenant_b, _, _ = await create_tenant_with_secrets()

    body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "10.50",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    signature = sign_shopify(body, secrets["shopify_webhook_secret"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
                headers={
                    "X-Shopify-Hmac-Sha256": signature,
                    "X-Skeldir-Tenant-Key": api_key_a,
                    "Content-Type": "application/json",
                },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    event_id = data["event_id"]

    # RLS isolation: tenant B cannot read tenant A's event
    async with get_session(tenant_b) as session:
        result = await session.get(AttributionEvent, event_id)
        assert result is None
    async with get_session(tenant_a) as session:
        result = await session.get(AttributionEvent, event_id)
        assert result is not None


@pytest.mark.asyncio
async def test_signature_enforced_shopify():
    _, api_key, _ = await create_tenant_with_secrets()
    body = json.dumps({"id": int(uuid4().int % 1_000_000), "total_price": "1.00"}).encode()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": "invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
                },
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_paypal_invalid_signature_returns_401():
    tenant_id, api_key, _ = await create_tenant_with_secrets()
    body = json.dumps(
        {
            "id": f"txn_{uuid4().hex[:8]}",
            "amount": {"total": "15.00", "currency": "USD"},
            "create_time": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/paypal/sale_completed",
            content=body,
            headers={
                "PayPal-Transmission-Sig": "invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 401

    async with get_session(tenant_id) as session:
        evt_count = await session.scalar(
            select(func.count()).select_from(AttributionEvent).where(AttributionEvent.tenant_id == tenant_id)
        )
        dead_count = await session.scalar(
            select(func.count()).select_from(DeadEvent).where(DeadEvent.tenant_id == tenant_id)
        )
        assert evt_count == 0
        assert dead_count == 0


@pytest.mark.asyncio
async def test_dlq_routed_on_validation_error():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "not-a-number",  # will fail revenue_amount parsing
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    signature = sign_shopify(body, secrets["shopify_webhook_secret"])

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
    data = resp.json()
    assert data["status"] == "dlq_routed"

    async with get_session(tenant_id) as session:
        res = await session.execute(select(DeadEvent).order_by(DeadEvent.ingested_at.desc()))
        dead_event = res.scalars().first()
        assert dead_event is not None
        assert dead_event.error_type in {"schema_validation", "unknown"}


@pytest.mark.asyncio
async def test_stripe_success_and_invalid_signature():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    body = json.dumps(
        {
            "id": f"pi_{uuid4().hex[:8]}",
            "amount": 5000,
            "currency": "usd",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "status": "succeeded",
        }
    ).encode()
    valid_sig = sign_stripe(body, secrets["stripe_webhook_secret"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=body,
            headers={
                "Stripe-Signature": valid_sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        bad = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=body,
            headers={
                "Stripe-Signature": "t=0,v1=invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert ok.status_code == 200
    assert ok.json()["status"] == "success"
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_paypal_success():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    body = json.dumps(
        {
            "id": f"txn_{uuid4().hex[:8]}",
            "amount": {"total": "20.00", "currency": "USD"},
            "create_time": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    sig = sign_paypal(body, secrets["paypal_webhook_secret"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/paypal/sale_completed",
            content=body,
            headers={
                "PayPal-Transmission-Sig": sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_woocommerce_success_and_pii_stripping():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    body_dict = {
        "id": int(uuid4().int % 1_000_000),
        "total": "30.00",
        "currency": "USD",
        "status": "completed",
        "date_completed": datetime.now(timezone.utc).isoformat(),
        "email": "customer@example.com",  # PII key to be stripped
    }
    body = json.dumps(body_dict).encode()
    sig = sign_woocommerce(body, secrets["woocommerce_webhook_secret"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/woocommerce/order_completed",
            content=body,
            headers={
                "X-WC-Webhook-Signature": sig,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    event_id = data["event_id"]

    async with get_session(tenant_id) as session:
        evt = await session.get(AttributionEvent, event_id)
        assert evt is not None
        assert "email" not in (evt.raw_payload or {})


@pytest.mark.asyncio
async def test_woocommerce_invalid_signature_returns_401():
    tenant_id, api_key, _ = await create_tenant_with_secrets()
    body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total": "25.00",
            "currency": "USD",
            "status": "completed",
            "date_completed": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/woocommerce/order_completed",
            content=body,
            headers={
                "X-WC-Webhook-Signature": "invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 401

    async with get_session(tenant_id) as session:
        evt_count = await session.scalar(
            select(func.count()).select_from(AttributionEvent).where(AttributionEvent.tenant_id == tenant_id)
        )
        dead_count = await session.scalar(
            select(func.count()).select_from(DeadEvent).where(DeadEvent.tenant_id == tenant_id)
        )
        assert evt_count == 0
        assert dead_count == 0


@pytest.mark.asyncio
async def test_openapi_contract_paths_present():
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/webhooks/shopify/order_create" in paths
    assert "/api/webhooks/stripe/payment_intent_succeeded" in paths
    assert "/api/webhooks/paypal/sale_completed" in paths
    assert "/api/webhooks/woocommerce/order_completed" in paths
    # Verify requestBody schemas reference generated models
    shopify_schema_ref = paths["/api/webhooks/shopify/order_create"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert "ShopifyOrderCreateRequest" in shopify_schema_ref
    stripe_schema_ref = paths["/api/webhooks/stripe/payment_intent_succeeded"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert "StripePaymentIntentSucceededRequest" in stripe_schema_ref
    # Verify response schemas expose status + identifier fields for 200 and status for 401
    for path in [
        "/api/webhooks/shopify/order_create",
        "/api/webhooks/stripe/payment_intent_succeeded",
        "/api/webhooks/paypal/sale_completed",
        "/api/webhooks/woocommerce/order_completed",
    ]:
        post_op = paths[path]["post"]
        success_schema = post_op["responses"]["200"]["content"]["application/json"]["schema"]
        if "$ref" in success_schema:
            ref_name = success_schema["$ref"].split("/")[-1]
            success_schema = schema["components"]["schemas"][ref_name]
        assert success_schema.get("type") == "object"
        props = success_schema.get("properties", {})
        assert "status" in props and props["status"].get("type") == "string"
        # At least one identifier field should be present
        assert ("event_id" in props) or ("dead_event_id" in props)

        unauthorized = post_op.get("responses", {}).get("401")
        if unauthorized:
            unauth_schema = unauthorized["content"]["application/json"]["schema"]
            if "$ref" in unauth_schema:
                ref_name = unauth_schema["$ref"].split("/")[-1]
                unauth_schema = schema["components"]["schemas"][ref_name]
            assert unauth_schema.get("type") == "object"
            unauth_props = unauth_schema.get("properties", {})
            assert "status" in unauth_props and unauth_props["status"].get("type") == "string"

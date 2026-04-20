from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = (
    "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@"
    "ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/"
    "neondb?sslmode=require&channel_binding=require"
)

import app.api.webhooks as webhooks_api
from app.core.secrets import get_database_url
from app.db.session import get_session
from app.main import app
from app.models import AttributionEvent, DeadEvent, RawEventPayload
from tests.helpers.webhook_secret_seed import (
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)

@pytest_asyncio.fixture(scope="session")
async def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


async def create_tenant_with_secrets():
    tenant_id = uuid4()
    api_key = f"b22_p2_api_key_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    secrets = {
        "shopify_webhook_secret": "shopify_secret",
        "stripe_webhook_secret": "stripe_secret",
        "paypal_webhook_secret": "paypal_secret",
        "woocommerce_webhook_secret": "woo_secret",
    }

    conn = await asyncpg.connect(get_database_url())
    secret_insert = webhook_secret_insert_params(
        shopify_secret=secrets["shopify_webhook_secret"],
        stripe_secret=secrets["stripe_webhook_secret"],
        paypal_secret=secrets["paypal_webhook_secret"],
        woocommerce_secret=secrets["woocommerce_webhook_secret"],
    )
    await conn.execute(
        """
        INSERT INTO tenants (id, api_key_hash, name, notification_email,
                             """
        + webhook_secret_insert_columns()
        + """,
                             created_at, updated_at)
        VALUES ($1, $2, $3, $4,
                pgp_sym_encrypt($5, $9), $10,
                pgp_sym_encrypt($6, $9), $10,
                pgp_sym_encrypt($7, $9), $10,
                pgp_sym_encrypt($8, $9), $10,
                NOW(), NOW())
        """,
        str(tenant_id),
        api_key_hash,
        f"B22P2 Tenant {str(tenant_id)[:8]}",
        f"b22p2_{str(tenant_id)[:8]}@test.local",
        secrets["shopify_webhook_secret"],
        secrets["stripe_webhook_secret"],
        secrets["paypal_webhook_secret"],
        secrets["woocommerce_webhook_secret"],
        secret_insert["webhook_secret_key"],
        secret_insert["webhook_secret_key_id"],
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


def _assert_no_p2_disallowed_fields(payload_text: str) -> None:
    lowered = payload_text.lower()
    assert "\"ip_address\"" not in lowered
    assert "\"user_agent\"" not in lowered
    assert "\"raw_headers\"" not in lowered
    assert "203.0.113." not in lowered


@pytest.mark.asyncio
async def test_b22_p2_webhook_success_persists_minimized_raw_event_substrate_only():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    order_id = int(uuid4().int % 1_000_000)
    body = json.dumps(
        {
            "id": order_id,
            "total_price": "16.25",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    signature = sign_shopify(body, secrets["shopify_webhook_secret"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": signature,
                "X-Skeldir-Tenant-Key": api_key,
                "User-Agent": "B22P2-Test-Agent/1.0",
                "X-Forwarded-For": "203.0.113.77",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "success"
    event_id = payload["event_id"]

    async with get_session(tenant_id) as session:
        event = await session.get(AttributionEvent, event_id)
        assert event is not None

        result = await session.execute(
            select(RawEventPayload).where(
                RawEventPayload.tenant_id == tenant_id,
                RawEventPayload.event_id == event.id,
            )
        )
        raw_payload = result.scalar_one()
        assert raw_payload.payload_json.get("verified_revenue_state") == "authenticity_verified"
        assert raw_payload.ip_address is None
        assert raw_payload.user_agent is None
        assert raw_payload.raw_headers is None
        _assert_no_p2_disallowed_fields(json.dumps(raw_payload.payload_json, sort_keys=True))


@pytest.mark.asyncio
async def test_b22_p2_webhook_malformed_dlq_path_drops_disallowed_ingress_identifiers():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    raw_body = b"{not-json"
    signature = sign_stripe(raw_body, secrets["stripe_webhook_secret"])
    idempotency_key = str(
        uuid5(
            NAMESPACE_URL,
            f"stripe_payment_intent_succeeded_invalid_json_{hashlib.sha256(raw_body).hexdigest()}",
        )
    )
    expected_correlation = uuid5(NAMESPACE_URL, idempotency_key)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=raw_body,
            headers={
                "Stripe-Signature": signature,
                "X-Skeldir-Tenant-Key": api_key,
                "User-Agent": "B22P2-DLQ-Agent/1.0",
                "X-Forwarded-For": "203.0.113.88",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "dlq_routed"

    async with get_session(tenant_id) as session:
        result = await session.execute(
            select(DeadEvent).where(
                DeadEvent.tenant_id == tenant_id,
                DeadEvent.correlation_id == expected_correlation,
            )
        )
        dead_event = result.scalar_one_or_none()
        assert dead_event is not None
        rendered = json.dumps(dead_event.raw_payload, sort_keys=True)
        _assert_no_p2_disallowed_fields(rendered)


@pytest.mark.asyncio
async def test_b22_p2_duplicate_webhook_does_not_reenqueue_downstream_side_effects(
    monkeypatch: pytest.MonkeyPatch,
):
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    order_id = int(uuid4().int % 1_000_000)
    body = json.dumps(
        {
            "id": order_id,
            "total_price": "24.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    signature = sign_shopify(body, secrets["shopify_webhook_secret"])

    observed_calls: list[str] = []

    def _capture_schedule_downstream_tasks(*, tenant_id, event_timestamp, session_id, correlation_id):
        observed_calls.append(str(correlation_id))

    monkeypatch.setattr(webhooks_api, "_schedule_downstream_tasks", _capture_schedule_downstream_tasks)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        second = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["status"] == "success"
    assert second.json()["status"] == "success"
    assert first.json()["event_id"] == second.json()["event_id"]
    assert len(observed_calls) == 1


def test_b22_p2_negative_control_disallowed_field_detector_is_non_vacuous():
    with pytest.raises(AssertionError):
        _assert_no_p2_disallowed_fields('{"ip_address":"203.0.113.99"}')

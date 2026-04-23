from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

import app.api.webhooks as webhooks_api
from app.core.secrets import get_database_url
from app.db.session import get_session
from app.main import app
from app.models import AttributionEvent, RawEventPayload, WebhookIngressIdentity
from tests.helpers.paypal_signature import (
    build_paypal_auth_headers,
    install_paypal_cert_fetcher,
)
from tests.helpers.webhook_secret_seed import (
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B22_P6_REQUIRE_DB_PROOFS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@pytest_asyncio.fixture(scope="session")
async def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _paypal_signature_material(monkeypatch: pytest.MonkeyPatch) -> None:
    install_paypal_cert_fetcher(monkeypatch)


async def create_tenant_with_secrets():
    tenant_id = uuid4()
    api_key = f"b22_p6_api_key_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    secrets = {
        "shopify_webhook_secret": "shopify_secret",
        "stripe_webhook_secret": "stripe_secret",
        "paypal_webhook_secret": "paypal_secret",
        "woocommerce_webhook_secret": "woo_secret",
    }
    try:
        conn = await asyncpg.connect(get_database_url())
    except Exception as exc:
        if _require_authoritative_db_proofs():
            pytest.fail(f"B2.2-P6 authoritative runtime proof DB is unreachable: {exc}")
        pytest.skip(f"B2.2-P6 runtime proofs require reachable Postgres: {exc}")

    table_ready = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'webhook_ingress_identities'
        )
        """
    )
    if not bool(table_ready):
        await conn.close()
        if _require_authoritative_db_proofs():
            pytest.fail(
                "B2.2-P6 authoritative runtime proof table webhook_ingress_identities is missing."
            )
        pytest.skip("B2.2-P6 runtime proofs require migrated webhook_ingress_identities table.")

    secret_insert = webhook_secret_insert_params(
        shopify_secret=secrets["shopify_webhook_secret"],
        stripe_secret=secrets["stripe_webhook_secret"],
        paypal_secret=secrets["paypal_webhook_secret"],
        woocommerce_secret=secrets["woocommerce_webhook_secret"],
    )
    # RAW_SQL_ALLOWLIST: test-only tenant bootstrap for webhook signature fixtures.
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
        f"B22P6 Tenant {str(tenant_id)[:8]}",
        f"b22p6_{str(tenant_id)[:8]}@test.local",
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


def sign_woocommerce(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def paypal_auth_headers(body: bytes, secret: str) -> dict[str, str]:
    return build_paypal_auth_headers(raw_body=body, webhook_id=secret)


def _provider_cases(*, now_iso: str, secrets: dict[str, str]) -> list[dict[str, object]]:
    shopify_body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "20.00",
            "currency": "USD",
            "created_at": now_iso,
        }
    ).encode()
    woocommerce_body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total": "30.00",
            "currency": "USD",
            "status": "completed",
            "date_completed": now_iso,
        }
    ).encode()
    stripe_body = json.dumps(
        {
            "id": f"evt_{uuid4().hex[:12]}",
            "type": "payment_intent.succeeded",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {
                "object": {
                    "id": f"pi_{uuid4().hex[:12]}",
                    "amount": 6100,
                    "currency": "usd",
                }
            },
        }
    ).encode()
    paypal_body = json.dumps(
        {
            "id": f"txn_{uuid4().hex[:12]}",
            "event_type": "PAYMENT.SALE.COMPLETED",
            "amount": {"total": "15.00", "currency": "USD"},
            "create_time": now_iso,
        }
    ).encode()

    return [
        {
            "provider": "shopify",
            "route": "/api/webhooks/shopify/order_create",
            "body": shopify_body,
            "headers": {
                "X-Shopify-Hmac-Sha256": sign_shopify(
                    shopify_body, secrets["shopify_webhook_secret"]
                ),
                "X-Shopify-Topic": "orders/create",
            },
        },
        {
            "provider": "woocommerce",
            "route": "/api/webhooks/woocommerce/order_completed",
            "body": woocommerce_body,
            "headers": {
                "X-WC-Webhook-Signature": sign_woocommerce(
                    woocommerce_body, secrets["woocommerce_webhook_secret"]
                ),
                "X-WC-Webhook-Topic": "order.completed",
            },
        },
        {
            "provider": "stripe",
            "route": "/api/webhooks/stripe/payment_intent/succeeded",
            "body": stripe_body,
            "headers": {
                "Stripe-Signature": sign_stripe(
                    stripe_body, secrets["stripe_webhook_secret"]
                ),
            },
        },
        {
            "provider": "paypal",
            "route": "/api/webhooks/paypal/sale_completed",
            "body": paypal_body,
            "headers": paypal_auth_headers(paypal_body, secrets["paypal_webhook_secret"]),
        },
    ]


@pytest.mark.asyncio
async def test_b22_p6_supported_providers_emit_one_canonical_verified_ingress_record_each_without_duplicate_side_effects(
    monkeypatch: pytest.MonkeyPatch,
):
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    now_iso = datetime.now(timezone.utc).isoformat()
    cases = _provider_cases(now_iso=now_iso, secrets=secrets)

    observed_calls: list[str] = []

    def _capture_schedule_downstream_tasks(
        *, tenant_id, event_timestamp, session_id, correlation_id
    ):
        observed_calls.append(str(correlation_id))

    monkeypatch.setattr(webhooks_api, "_schedule_downstream_tasks", _capture_schedule_downstream_tasks)

    provider_event_ids: dict[str, str] = {}
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for case in cases:
            route = str(case["route"])
            body = case["body"]
            provider = str(case["provider"])
            headers = dict(case["headers"])
            request_headers = {
                **headers,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            }
            first = await client.post(route, content=body, headers=request_headers)
            second = await client.post(route, content=body, headers=request_headers)

            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            assert first.json()["status"] == "success"
            assert second.json()["status"] == "success"
            assert first.json()["event_id"] == second.json()["event_id"]
            provider_event_ids[provider] = first.json()["event_id"]

    assert len(observed_calls) == 4

    async with get_session(tenant_id=tenant_id) as session:
        event_count = await session.scalar(
            select(func.count())
            .select_from(AttributionEvent)
            .where(AttributionEvent.tenant_id == tenant_id)
        )
        raw_count = await session.scalar(
            select(func.count())
            .select_from(RawEventPayload)
            .where(RawEventPayload.tenant_id == tenant_id)
        )
        identities_result = await session.execute(
            select(WebhookIngressIdentity).where(
                WebhookIngressIdentity.tenant_id == tenant_id
            )
        )
        raw_payload_rows = (
            await session.execute(
                select(RawEventPayload).where(RawEventPayload.tenant_id == tenant_id)
            )
        ).scalars().all()

    identities = list(identities_result.scalars().all())
    assert int(event_count or 0) == 4
    assert int(raw_count or 0) == 4
    assert len(identities) == 4
    assert {identity.provider for identity in identities} == {
        "shopify",
        "woocommerce",
        "stripe",
        "paypal",
    }
    assert {str(identity.event_id) for identity in identities} == set(
        provider_event_ids.values()
    )

    for identity in identities:
        assert identity.tenant_id == tenant_id
        assert identity.provider_native_event_reference
        assert identity.provider_native_commerce_reference
        assert identity.normalized_commerce_reference_kind
        assert identity.normalized_commerce_reference_value
        assert identity.verified_amount_minor >= 0
        assert identity.verified_amount_currency == "USD"
        assert identity.verified_amount_scale == 2
        assert identity.verified_commerce_ingress_state == "authenticity_verified"
        assert identity.verified_at is not None
        assert identity.idempotency_key

    for raw_payload in raw_payload_rows:
        assert raw_payload.tenant_id == tenant_id
        assert raw_payload.ip_address is None
        assert raw_payload.user_agent is None
        assert raw_payload.raw_headers is None


@pytest.mark.asyncio
async def test_b22_p6_provider_authenticity_failures_do_not_persist_verified_ingress_records():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    now_iso = datetime.now(timezone.utc).isoformat()
    cases = _provider_cases(now_iso=now_iso, secrets=secrets)

    forged_headers_by_provider = {
        "shopify": {"X-Shopify-Hmac-Sha256": "invalid", "X-Shopify-Topic": "orders/create"},
        "woocommerce": {"X-WC-Webhook-Signature": "invalid", "X-WC-Webhook-Topic": "order.completed"},
        "stripe": {"Stripe-Signature": "t=0,v1=invalid"},
        "paypal": paypal_auth_headers(b"{}", "wrong_webhook_id"),
    }

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for case in cases:
            provider = str(case["provider"])
            route = str(case["route"])
            body = case["body"]
            forged_headers = forged_headers_by_provider[provider]
            response = await client.post(
                route,
                content=body,
                headers={
                    **forged_headers,
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 401, response.text

    async with get_session(tenant_id=tenant_id) as session:
        event_count = await session.scalar(
            select(func.count())
            .select_from(AttributionEvent)
            .where(AttributionEvent.tenant_id == tenant_id)
        )
        raw_count = await session.scalar(
            select(func.count())
            .select_from(RawEventPayload)
            .where(RawEventPayload.tenant_id == tenant_id)
        )
        identity_count = await session.scalar(
            select(func.count())
            .select_from(WebhookIngressIdentity)
            .where(WebhookIngressIdentity.tenant_id == tenant_id)
        )

    assert int(event_count or 0) == 0
    assert int(raw_count or 0) == 0
    assert int(identity_count or 0) == 0

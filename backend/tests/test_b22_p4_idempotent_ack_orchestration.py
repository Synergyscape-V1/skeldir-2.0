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
from app.models import AttributionEvent
from tests.helpers.paypal_signature import build_paypal_auth_headers, install_paypal_cert_fetcher
from tests.helpers.webhook_secret_seed import (
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B22_P4_REQUIRE_DB_PROOFS", "0").strip().lower() in {
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
    api_key = f"b22_p4_api_key_{uuid4()}"
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
            pytest.fail(f"B2.2-P4 authoritative runtime proof DB is unreachable: {exc}")
        pytest.skip(f"B2.2-P4 runtime proofs require reachable Postgres: {exc}")
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
                "B2.2-P4 authoritative runtime proof table webhook_ingress_identities is missing."
            )
        pytest.skip("B2.2-P4 runtime proofs require migrated webhook_ingress_identities table.")
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
        f"B22P4 Tenant {str(tenant_id)[:8]}",
        f"b22p4_{str(tenant_id)[:8]}@test.local",
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


@pytest.mark.asyncio
async def test_b22_p4_duplicate_replay_suppresses_downstream_tasks_for_all_supported_providers(
    monkeypatch: pytest.MonkeyPatch,
):
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    now_iso = datetime.now(timezone.utc).isoformat()
    shopify_id = int(uuid4().int % 1_000_000)
    woo_id = int(uuid4().int % 1_000_000)
    stripe_pi_id = f"pi_{uuid4().hex[:12]}"
    stripe_event_id = f"evt_{uuid4().hex[:12]}"
    paypal_txn_id = f"txn_{uuid4().hex[:10]}"

    shopify_body = json.dumps(
        {"id": shopify_id, "total_price": "20.00", "currency": "USD", "created_at": now_iso}
    ).encode()
    woo_body = json.dumps(
        {
            "id": woo_id,
            "total": "30.00",
            "currency": "USD",
            "status": "completed",
            "date_completed": now_iso,
        }
    ).encode()
    stripe_v1_body = json.dumps(
        {
            "id": stripe_pi_id,
            "amount": 5500,
            "currency": "usd",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "status": "succeeded",
        }
    ).encode()
    stripe_v2_body = json.dumps(
        {
            "id": stripe_event_id,
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {"object": {"id": stripe_pi_id, "amount": 5500, "currency": "usd"}},
        }
    ).encode()
    paypal_body = json.dumps(
        {"id": paypal_txn_id, "amount": {"total": "15.00", "currency": "USD"}, "create_time": now_iso}
    ).encode()

    observed_calls: list[str] = []

    def _capture_schedule_downstream_tasks(*, tenant_id, event_timestamp, session_id, correlation_id):
        observed_calls.append(str(correlation_id))

    monkeypatch.setattr(webhooks_api, "_schedule_downstream_tasks", _capture_schedule_downstream_tasks)

    cases = [
        (
            "/api/webhooks/shopify/order_create",
            shopify_body,
            {"X-Shopify-Hmac-Sha256": sign_shopify(shopify_body, secrets["shopify_webhook_secret"])},
        ),
        (
            "/api/webhooks/woocommerce/order_completed",
            woo_body,
            {"X-WC-Webhook-Signature": sign_woocommerce(woo_body, secrets["woocommerce_webhook_secret"])},
        ),
        (
            "/api/webhooks/stripe/payment_intent_succeeded",
            stripe_v1_body,
            {"Stripe-Signature": sign_stripe(stripe_v1_body, secrets["stripe_webhook_secret"])},
        ),
        (
            "/api/webhooks/stripe/payment_intent/succeeded",
            stripe_v2_body,
            {"Stripe-Signature": sign_stripe(stripe_v2_body, secrets["stripe_webhook_secret"])},
        ),
        (
            "/api/webhooks/paypal/sale_completed",
            paypal_body,
            paypal_auth_headers(paypal_body, secrets["paypal_webhook_secret"]),
        ),
    ]

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for route, body, auth_headers in cases:
            first = await client.post(
                route,
                content=body,
                headers={
                    **auth_headers,
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            )
            second = await client.post(
                route,
                content=body,
                headers={
                    **auth_headers,
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            )
            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            assert first.json()["status"] == "success"
            assert second.json()["status"] == "success"
            assert first.json()["event_id"] == second.json()["event_id"]

    assert len(observed_calls) == len(cases)

    async with get_session(tenant_id=tenant_id) as session:
        event_count = await session.scalar(
            select(func.count()).select_from(AttributionEvent).where(AttributionEvent.tenant_id == tenant_id)
        )
    assert event_count == len(cases)


@pytest.mark.asyncio
async def test_b22_p4_duplicate_replay_preserves_single_durable_event_row():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "11.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    signature = sign_shopify(body, secrets["shopify_webhook_secret"])

    transport = ASGITransport(app=app, raise_app_exceptions=False)
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

    async with get_session(tenant_id=tenant_id) as session:
        event_count = await session.scalar(
            select(func.count()).select_from(AttributionEvent).where(AttributionEvent.tenant_id == tenant_id)
        )
    assert event_count == 1


@pytest.mark.asyncio
async def test_b22_p4_ack_matrix_is_stable_for_success_duplicate_forged_malformed_oversized_tenant_and_unsupported_outcomes(
    monkeypatch: pytest.MonkeyPatch,
):
    _, api_key, secrets = await create_tenant_with_secrets()
    observed_calls: list[str] = []

    def _capture_schedule_downstream_tasks(*, tenant_id, event_timestamp, session_id, correlation_id):
        observed_calls.append(str(correlation_id))

    monkeypatch.setattr(webhooks_api, "_schedule_downstream_tasks", _capture_schedule_downstream_tasks)

    valid_body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "17.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    valid_signature = sign_shopify(valid_body, secrets["shopify_webhook_secret"])

    malformed_signed_body = b"{not-json"
    malformed_signature = sign_stripe(malformed_signed_body, secrets["stripe_webhook_secret"])

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        success = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_body,
            headers={
                "X-Shopify-Hmac-Sha256": valid_signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        duplicate = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_body,
            headers={
                "X-Shopify-Hmac-Sha256": valid_signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        forged = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_body,
            headers={
                "X-Shopify-Hmac-Sha256": "invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        malformed = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=malformed_signed_body,
            headers={
                "Stripe-Signature": malformed_signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        oversized = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_body,
            headers={
                "X-Shopify-Hmac-Sha256": valid_signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
                "Content-Length": str(10_000_000),
            },
        )
        missing_tenant = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_body,
            headers={
                "X-Shopify-Hmac-Sha256": valid_signature,
                "Content-Type": "application/json",
            },
        )
        wrong_tenant = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_body,
            headers={
                "X-Shopify-Hmac-Sha256": valid_signature,
                "X-Skeldir-Tenant-Key": f"wrong_{uuid4()}",
                "Content-Type": "application/json",
            },
        )
        unsupported = await client.post(
            "/api/webhooks/shopify/orders_paid",
            content=valid_body,
            headers={
                "X-Shopify-Hmac-Sha256": valid_signature,
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert success.status_code == 200, success.text
    assert success.json()["status"] == "success"
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["status"] == "success"
    assert duplicate.json()["event_id"] == success.json()["event_id"]
    assert forged.status_code == 401, forged.text
    assert malformed.status_code == 200, malformed.text
    assert malformed.json()["status"] == "dlq_routed"
    assert oversized.status_code == 413, oversized.text
    assert missing_tenant.status_code == 401, missing_tenant.text
    assert wrong_tenant.status_code == 401, wrong_tenant.text
    assert unsupported.status_code == 404, unsupported.text
    assert len(observed_calls) == 1


@pytest.mark.asyncio
async def test_b22_p4_stripe_alias_and_canonical_routes_share_ack_semantics():
    _, api_key, secrets = await create_tenant_with_secrets()
    pi_id = f"pi_{uuid4().hex[:12]}"
    now_ts = int(datetime.now(timezone.utc).timestamp())
    canonical_body = json.dumps(
        {
            "id": pi_id,
            "amount": 6100,
            "currency": "usd",
            "created": now_ts,
            "status": "succeeded",
        }
    ).encode()
    alias_body = json.dumps(
        {
            "id": f"evt_{uuid4().hex[:12]}",
            "created": now_ts,
            "data": {"object": {"id": pi_id, "amount": 6100, "currency": "usd"}},
        }
    ).encode()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        canonical_ok = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=canonical_body,
            headers={
                "Stripe-Signature": sign_stripe(canonical_body, secrets["stripe_webhook_secret"]),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        alias_ok = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=alias_body,
            headers={
                "Stripe-Signature": sign_stripe(alias_body, secrets["stripe_webhook_secret"]),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        canonical_forged = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=canonical_body,
            headers={
                "Stripe-Signature": "t=0,v1=invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        alias_forged = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=alias_body,
            headers={
                "Stripe-Signature": "t=0,v1=invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert canonical_ok.status_code == 200, canonical_ok.text
    assert canonical_ok.json()["status"] == "success"
    assert alias_ok.status_code == 200, alias_ok.text
    assert alias_ok.json()["status"] == "success"
    assert canonical_forged.status_code == 401, canonical_forged.text
    assert alias_forged.status_code == 401, alias_forged.text

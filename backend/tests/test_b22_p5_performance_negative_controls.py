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
from tests.helpers.paypal_signature import (
    build_paypal_auth_headers,
    install_paypal_cert_fetcher,
)
from tests.helpers.webhook_secret_seed import (
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B22_P5_REQUIRE_DB_PROOFS", "0").strip().lower() in {
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
    api_key = f"b22_p5_api_key_{uuid4()}"
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
            pytest.fail(f"B2.2-P5 authoritative runtime proof DB is unreachable: {exc}")
        pytest.skip(f"B2.2-P5 runtime proofs require reachable Postgres: {exc}")
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
                "B2.2-P5 authoritative runtime proof table webhook_ingress_identities is missing."
            )
        pytest.skip(
            "B2.2-P5 runtime proofs require migrated webhook_ingress_identities table."
        )
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
        f"B22P5 Tenant {str(tenant_id)[:8]}",
        f"b22p5_{str(tenant_id)[:8]}@test.local",
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
    return base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


def sign_stripe(body: bytes, secret: str) -> str:
    ts = int(datetime.now(timezone.utc).timestamp())
    signed_payload = f"{ts}.{body.decode()}".encode()
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def sign_woocommerce(body: bytes, secret: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


def paypal_auth_headers(body: bytes, secret: str) -> dict[str, str]:
    return build_paypal_auth_headers(raw_body=body, webhook_id=secret)


@pytest.mark.asyncio
async def test_b22_p5_negative_control_matrix_includes_route_owned_provider_safe_unsupported_family_semantics(
    monkeypatch: pytest.MonkeyPatch,
):
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    observed_calls: list[str] = []

    def _capture_schedule_downstream_tasks(
        *, tenant_id, event_timestamp, session_id, correlation_id
    ):
        observed_calls.append(str(correlation_id))

    monkeypatch.setattr(
        webhooks_api, "_schedule_downstream_tasks", _capture_schedule_downstream_tasks
    )

    valid_shopify_body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "17.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    malformed_shopify_body = b"{not-json"
    stripe_unsupported_body = json.dumps(
        {
            "id": f"pi_{uuid4().hex[:16]}",
            "amount": 2100,
            "currency": "usd",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "status": "succeeded",
            "type": "charge.succeeded",
        }
    ).encode()
    stripe_alias_unsupported_body = json.dumps(
        {
            "id": f"evt_{uuid4().hex[:16]}",
            "type": "charge.succeeded",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {
                "object": {
                    "id": f"pi_{uuid4().hex[:16]}",
                    "amount": 1200,
                    "currency": "usd",
                }
            },
        }
    ).encode()
    paypal_unsupported_body = json.dumps(
        {
            "id": f"txn_{uuid4().hex[:16]}",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "amount": {"total": "10.00", "currency": "USD"},
            "create_time": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    woo_unsupported_body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total": "11.00",
            "currency": "USD",
            "status": "completed",
            "date_completed": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        success = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_shopify_body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(
                    valid_shopify_body, secrets["shopify_webhook_secret"]
                ),
                "X-Shopify-Topic": "orders/create",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        duplicate = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_shopify_body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(
                    valid_shopify_body, secrets["shopify_webhook_secret"]
                ),
                "X-Shopify-Topic": "orders/create",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        forged_signature = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_shopify_body,
            headers={
                "X-Shopify-Hmac-Sha256": "invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        missing_tenant = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_shopify_body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(
                    valid_shopify_body, secrets["shopify_webhook_secret"]
                ),
                "X-Shopify-Topic": "orders/create",
                "Content-Type": "application/json",
            },
        )
        wrong_tenant = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_shopify_body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(
                    valid_shopify_body, secrets["shopify_webhook_secret"]
                ),
                "X-Shopify-Topic": "orders/create",
                "X-Skeldir-Tenant-Key": f"wrong_{uuid4()}",
                "Content-Type": "application/json",
            },
        )
        malformed_payload = await client.post(
            "/api/webhooks/shopify/order_create",
            content=malformed_shopify_body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(
                    malformed_shopify_body, secrets["shopify_webhook_secret"]
                ),
                "X-Shopify-Topic": "orders/create",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        oversized_payload = await client.post(
            "/api/webhooks/shopify/order_create",
            content=valid_shopify_body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(
                    valid_shopify_body, secrets["shopify_webhook_secret"]
                ),
                "X-Shopify-Topic": "orders/create",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
                "Content-Length": str(10_000_000),
            },
        )

        async with get_session(tenant_id=tenant_id) as session:
            before_unsupported_count = await session.scalar(
                select(func.count())
                .select_from(AttributionEvent)
                .where(AttributionEvent.tenant_id == tenant_id)
            )

        unsupported_cases = [
            await client.post(
                "/api/webhooks/shopify/order_create",
                content=valid_shopify_body,
                headers={
                    "X-Shopify-Hmac-Sha256": sign_shopify(
                        valid_shopify_body, secrets["shopify_webhook_secret"]
                    ),
                    "X-Shopify-Topic": "orders/paid",
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
            await client.post(
                "/api/webhooks/stripe/payment_intent_succeeded",
                content=stripe_unsupported_body,
                headers={
                    "Stripe-Signature": sign_stripe(
                        stripe_unsupported_body, secrets["stripe_webhook_secret"]
                    ),
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
            await client.post(
                "/api/webhooks/stripe/payment_intent/succeeded",
                content=stripe_alias_unsupported_body,
                headers={
                    "Stripe-Signature": sign_stripe(
                        stripe_alias_unsupported_body, secrets["stripe_webhook_secret"]
                    ),
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
            await client.post(
                "/api/webhooks/paypal/sale_completed",
                content=paypal_unsupported_body,
                headers={
                    **paypal_auth_headers(
                        paypal_unsupported_body, secrets["paypal_webhook_secret"]
                    ),
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
            await client.post(
                "/api/webhooks/woocommerce/order_completed",
                content=woo_unsupported_body,
                headers={
                    "X-WC-Webhook-Signature": sign_woocommerce(
                        woo_unsupported_body, secrets["woocommerce_webhook_secret"]
                    ),
                    "X-WC-Webhook-Topic": "order.updated",
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
        ]

        async with get_session(tenant_id=tenant_id) as session:
            after_unsupported_count = await session.scalar(
                select(func.count())
                .select_from(AttributionEvent)
                .where(AttributionEvent.tenant_id == tenant_id)
            )

    assert success.status_code == 200, success.text
    assert success.json()["status"] == "success"
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["status"] == "success"
    assert duplicate.json()["event_id"] == success.json()["event_id"]
    assert forged_signature.status_code == 401, forged_signature.text
    assert missing_tenant.status_code == 401, missing_tenant.text
    assert wrong_tenant.status_code == 401, wrong_tenant.text
    assert malformed_payload.status_code == 200, malformed_payload.text
    assert malformed_payload.json()["status"] == "dlq_routed"
    assert oversized_payload.status_code == 413, oversized_payload.text

    for unsupported in unsupported_cases:
        assert unsupported.status_code == 200, unsupported.text
        payload = unsupported.json()
        assert payload["status"] == "unsupported_event_family_ignored"
        assert payload["error"] == "unsupported_event_family"

    assert int(before_unsupported_count or 0) == int(after_unsupported_count or 0)
    assert len(observed_calls) == 1


@pytest.mark.asyncio
async def test_b22_p5_stripe_alias_and_canonical_routes_have_equivalent_success_failure_and_unsupported_family_semantics():
    _, api_key, secrets = await create_tenant_with_secrets()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payment_intent_id = f"pi_{uuid4().hex[:16]}"

    canonical_success_body = json.dumps(
        {
            "id": payment_intent_id,
            "amount": 5100,
            "currency": "usd",
            "created": now_ts,
            "status": "succeeded",
            "type": "payment_intent.succeeded",
        }
    ).encode()
    alias_success_body = json.dumps(
        {
            "id": f"evt_{uuid4().hex[:16]}",
            "type": "payment_intent.succeeded",
            "created": now_ts,
            "data": {
                "object": {"id": payment_intent_id, "amount": 5100, "currency": "usd"}
            },
        }
    ).encode()
    malformed_body = b"{not-json"
    canonical_unsupported_body = json.dumps(
        {
            "id": f"pi_{uuid4().hex[:16]}",
            "amount": 1100,
            "currency": "usd",
            "created": now_ts,
            "status": "succeeded",
            "type": "charge.succeeded",
        }
    ).encode()
    alias_unsupported_body = json.dumps(
        {
            "id": f"evt_{uuid4().hex[:16]}",
            "type": "charge.succeeded",
            "created": now_ts,
            "data": {
                "object": {
                    "id": f"pi_{uuid4().hex[:16]}",
                    "amount": 1100,
                    "currency": "usd",
                }
            },
        }
    ).encode()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        canonical_success = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=canonical_success_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    canonical_success_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        alias_success = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=alias_success_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    alias_success_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        canonical_forged = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=canonical_success_body,
            headers={
                "Stripe-Signature": "t=0,v1=invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        alias_forged = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=alias_success_body,
            headers={
                "Stripe-Signature": "t=0,v1=invalid",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        canonical_malformed = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=malformed_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    malformed_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        alias_malformed = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=malformed_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    malformed_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        canonical_missing_tenant = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=canonical_success_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    canonical_success_body, secrets["stripe_webhook_secret"]
                ),
                "Content-Type": "application/json",
            },
        )
        alias_missing_tenant = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=alias_success_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    alias_success_body, secrets["stripe_webhook_secret"]
                ),
                "Content-Type": "application/json",
            },
        )
        canonical_wrong_tenant = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=canonical_success_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    canonical_success_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": f"wrong_{uuid4()}",
                "Content-Type": "application/json",
            },
        )
        alias_wrong_tenant = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=alias_success_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    alias_success_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": f"wrong_{uuid4()}",
                "Content-Type": "application/json",
            },
        )
        canonical_unsupported = await client.post(
            "/api/webhooks/stripe/payment_intent_succeeded",
            content=canonical_unsupported_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    canonical_unsupported_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
        alias_unsupported = await client.post(
            "/api/webhooks/stripe/payment_intent/succeeded",
            content=alias_unsupported_body,
            headers={
                "Stripe-Signature": sign_stripe(
                    alias_unsupported_body, secrets["stripe_webhook_secret"]
                ),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert canonical_success.status_code == 200, canonical_success.text
    assert canonical_success.json()["status"] == "success"
    assert alias_success.status_code == 200, alias_success.text
    assert alias_success.json()["status"] == "success"

    assert canonical_forged.status_code == 401, canonical_forged.text
    assert alias_forged.status_code == 401, alias_forged.text

    assert canonical_malformed.status_code == 200, canonical_malformed.text
    assert canonical_malformed.json()["status"] == "dlq_routed"
    assert alias_malformed.status_code == 200, alias_malformed.text
    assert alias_malformed.json()["status"] == "dlq_routed"

    assert canonical_missing_tenant.status_code == 401, canonical_missing_tenant.text
    assert alias_missing_tenant.status_code == 401, alias_missing_tenant.text
    assert canonical_wrong_tenant.status_code == 401, canonical_wrong_tenant.text
    assert alias_wrong_tenant.status_code == 401, alias_wrong_tenant.text

    assert canonical_unsupported.status_code == 200, canonical_unsupported.text
    assert canonical_unsupported.json()["status"] == "unsupported_event_family_ignored"
    assert canonical_unsupported.json()["error"] == "unsupported_event_family"
    assert alias_unsupported.status_code == 200, alias_unsupported.text
    assert alias_unsupported.json()["status"] == "unsupported_event_family_ignored"
    assert alias_unsupported.json()["error"] == "unsupported_event_family"

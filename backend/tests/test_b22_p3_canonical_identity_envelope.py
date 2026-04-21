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
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.core.secrets import get_database_url
from app.db.session import get_session
import app.ingestion.event_service as event_service
from app.main import app
from app.models import WebhookIngressIdentity
from tests.helpers.paypal_signature import build_paypal_auth_headers, install_paypal_cert_fetcher
from tests.helpers.webhook_secret_seed import (
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)


def _require_authoritative_db_proofs() -> bool:
    return os.getenv("SKELDIR_B22_P3_REQUIRE_DB_PROOFS", "0").strip().lower() in {
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
    api_key = f"b22_p3_api_key_{uuid4()}"
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
            pytest.fail(f"B2.2-P3 authoritative runtime proof DB is unreachable: {exc}")
        pytest.skip(f"B2.2-P3 runtime proofs require reachable Postgres: {exc}")
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
                "B2.2-P3 authoritative runtime proof table webhook_ingress_identities is missing."
            )
        pytest.skip("B2.2-P3 runtime proofs require migrated webhook_ingress_identities table.")
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
        f"B22P3 Tenant {str(tenant_id)[:8]}",
        f"b22p3_{str(tenant_id)[:8]}@test.local",
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


def _assert_typed_reference_non_collapse(rows: list[WebhookIngressIdentity]) -> None:
    observed = {(row.provider, row.normalized_commerce_reference_kind) for row in rows}
    expected = {
        ("shopify", "shopify_order_id"),
        ("woocommerce", "woocommerce_order_id"),
        ("stripe", "stripe_payment_intent_id"),
        ("paypal", "paypal_transaction_id"),
    }
    assert observed == expected


@pytest.mark.asyncio
async def test_b22_p3_all_supported_providers_persist_canonical_identity_envelope():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    now_iso = datetime.now(timezone.utc).isoformat()
    shopify_id = int(uuid4().int % 1_000_000)
    woo_id = int(uuid4().int % 1_000_000)
    stripe_pi_id = f"pi_{uuid4().hex[:12]}"
    stripe_event_id = f"evt_{uuid4().hex[:12]}"
    paypal_txn_id = f"txn_{uuid4().hex[:10]}"

    shopify_body = json.dumps(
        {"id": shopify_id, "total_price": "19.95", "currency": "USD", "created_at": now_iso}
    ).encode()
    woo_body = json.dumps(
        {
            "id": woo_id,
            "total": "42.10",
            "currency": "USD",
            "status": "completed",
            "date_completed": now_iso,
        }
    ).encode()
    stripe_body = json.dumps(
        {
            "id": stripe_event_id,
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {
                "object": {
                    "id": stripe_pi_id,
                    "amount": 5500,
                    "currency": "usd",
                    "metadata": {"vendor": "stripe", "order_id": stripe_pi_id},
                }
            },
        }
    ).encode()
    paypal_body = json.dumps(
        {"id": paypal_txn_id, "amount": {"total": "75.50", "currency": "USD"}, "create_time": now_iso}
    ).encode()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.post(
                "/api/webhooks/shopify/order_create",
                content=shopify_body,
                headers={
                    "X-Shopify-Hmac-Sha256": sign_shopify(shopify_body, secrets["shopify_webhook_secret"]),
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
            await client.post(
                "/api/webhooks/woocommerce/order_completed",
                content=woo_body,
                headers={
                    "X-WC-Webhook-Signature": sign_woocommerce(woo_body, secrets["woocommerce_webhook_secret"]),
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
            await client.post(
                "/api/webhooks/stripe/payment_intent/succeeded",
                content=stripe_body,
                headers={
                    "Stripe-Signature": sign_stripe(stripe_body, secrets["stripe_webhook_secret"]),
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
            await client.post(
                "/api/webhooks/paypal/sale_completed",
                content=paypal_body,
                headers={
                    **paypal_auth_headers(paypal_body, secrets["paypal_webhook_secret"]),
                    "X-Skeldir-Tenant-Key": api_key,
                    "Content-Type": "application/json",
                },
            ),
        ]

    for response in responses:
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "success"

    async with get_session(tenant_id) as session:
        result = await session.execute(
            select(WebhookIngressIdentity).where(WebhookIngressIdentity.tenant_id == tenant_id)
        )
        identities = list(result.scalars().all())

    assert len(identities) == 4
    _assert_typed_reference_non_collapse(identities)
    for row in identities:
        assert row.provider_native_event_reference
        assert row.provider_native_commerce_reference
        assert row.normalized_commerce_reference_kind
        assert row.normalized_commerce_reference_value
        assert row.verified_amount_minor >= 0
        assert row.verified_amount_currency == "USD"
        assert row.verified_amount_scale == 2
        assert row.verified_commerce_ingress_state == "authenticity_verified"
        assert row.verified_at is not None
        assert row.idempotency_key
    assert len({row.event_id for row in identities}) == len(identities)


@pytest.mark.asyncio
async def test_b22_p3_verified_state_is_first_class_queryable():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    order_id = int(uuid4().int % 1_000_000)
    body = json.dumps(
        {"id": order_id, "total_price": "10.00", "currency": "USD", "created_at": datetime.now(timezone.utc).isoformat()}
    ).encode()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(body, secrets["shopify_webhook_secret"]),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"

    async with get_session(tenant_id) as session:
        query = await session.execute(
            select(WebhookIngressIdentity).where(
                WebhookIngressIdentity.tenant_id == tenant_id,
                WebhookIngressIdentity.provider == "shopify",
                WebhookIngressIdentity.verified_commerce_ingress_state == "authenticity_verified",
                WebhookIngressIdentity.normalized_commerce_reference_kind == "shopify_order_id",
            )
        )
        rows = list(query.scalars().all())

    assert len(rows) == 1
    assert rows[0].normalized_commerce_reference_value == str(order_id)
    assert rows[0].verified_at is not None


@pytest.mark.asyncio
async def test_b22_p3_authoritative_webhook_path_fails_when_substrate_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    order_id = int(uuid4().int % 1_000_000)
    body = json.dumps(
        {
            "id": order_id,
            "total_price": "10.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    original_flush = event_service.AsyncSession.flush

    async def _fail_flush(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise ProgrammingError(
            "INSERT INTO webhook_ingress_identities (...) VALUES (...)",
            {},
            Exception('relation "webhook_ingress_identities" does not exist'),
        )

    monkeypatch.setattr(event_service.AsyncSession, "flush", _fail_flush)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(body, secrets["shopify_webhook_secret"]),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert response.status_code >= 500
    monkeypatch.setattr(event_service.AsyncSession, "flush", original_flush)


@pytest.mark.asyncio
async def test_b22_p3_authoritative_path_avoids_request_time_schema_introspection(
    monkeypatch: pytest.MonkeyPatch,
):
    _, api_key, secrets = await create_tenant_with_secrets()
    body = json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "10.00",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()
    original_execute = event_service.AsyncSession.execute

    async def _guard_execute(self, statement, *args, **kwargs):  # type: ignore[no-untyped-def]
        statement_text = str(statement).lower()
        assert "information_schema.tables" not in statement_text
        return await original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(event_service.AsyncSession, "execute", _guard_execute)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(body, secrets["shopify_webhook_secret"]),
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200, response.text
    monkeypatch.setattr(event_service.AsyncSession, "execute", original_execute)


def test_b22_p3_verified_at_capture_is_propagated_unchanged() -> None:
    verified_at = datetime(2026, 4, 20, 22, 0, tzinfo=timezone.utc)
    event_timestamp = datetime(2026, 4, 20, 21, 59, tzinfo=timezone.utc)
    payload = event_service._extract_webhook_ingress_identity(
        source="shopify",
        event_data={
            "provider": "shopify",
            "provider_native_event_reference": "evt-1",
            "provider_native_commerce_reference": "ord-1",
            "normalized_commerce_reference_kind": "shopify_order_id",
            "normalized_commerce_reference_value": "ord-1",
            "verified_amount_minor": 100,
            "verified_amount_currency": "USD",
            "verified_amount_scale": 2,
            "verified_commerce_ingress_state": "authenticity_verified",
            "verified_at": verified_at,
        },
        tenant_id=uuid4(),
        idempotency_key="idempotency-1",
        event_id=uuid4(),
        event_timestamp=event_timestamp,
    )
    assert payload is not None
    assert payload["verified_at"] == verified_at


def test_b22_p3_negative_control_typed_reference_detector_is_non_vacuous():
    with pytest.raises(AssertionError):
        _assert_typed_reference_non_collapse(
            [
                WebhookIngressIdentity(  # type: ignore[call-arg]
                    provider="shopify",
                    normalized_commerce_reference_kind="order_id",
                    normalized_commerce_reference_value="1",
                    provider_native_event_reference="1",
                    provider_native_commerce_reference="1",
                    verified_amount_minor=100,
                    verified_amount_currency="USD",
                    verified_amount_scale=2,
                    event_timestamp=datetime.now(timezone.utc),
                    idempotency_key="x",
                    verified_commerce_ingress_state="authenticity_verified",
                    tenant_id=uuid4(),
                    event_id=uuid4(),
                ),
                WebhookIngressIdentity(  # type: ignore[call-arg]
                    provider="stripe",
                    normalized_commerce_reference_kind="order_id",
                    normalized_commerce_reference_value="1",
                    provider_native_event_reference="1",
                    provider_native_commerce_reference="1",
                    verified_amount_minor=100,
                    verified_amount_currency="USD",
                    verified_amount_scale=2,
                    event_timestamp=datetime.now(timezone.utc),
                    idempotency_key="y",
                    verified_commerce_ingress_state="authenticity_verified",
                    tenant_id=uuid4(),
                    event_id=uuid4(),
                ),
            ]
        )

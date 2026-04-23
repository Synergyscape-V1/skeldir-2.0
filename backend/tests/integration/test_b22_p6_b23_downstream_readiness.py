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

from app.core.secrets import get_database_url
from app.db.session import get_session
from app.main import app
from app.models import WebhookIngressIdentity
from app.services.revenue_reconciliation import RevenueReconciliationService
from tests.helpers.paypal_signature import install_paypal_cert_fetcher
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
    api_key = f"b22_p6_b23_api_key_{uuid4()}"
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
        f"B22P6B23 Tenant {str(tenant_id)[:8]}",
        f"b22p6b23_{str(tenant_id)[:8]}@test.local",
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


def _shopify_request_body() -> bytes:
    return json.dumps(
        {
            "id": int(uuid4().int % 1_000_000),
            "total_price": "22.50",
            "currency": "USD",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()


@pytest.mark.asyncio
async def test_b22_p6_b23_compatibility_surface_exposes_canonical_identity_and_verified_state():
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    body = _shopify_request_body()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(body, secrets["shopify_webhook_secret"]),
                "X-Shopify-Topic": "orders/create",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"

    async with get_session(tenant_id=tenant_id) as session:
        result = await session.execute(
            select(WebhookIngressIdentity).where(
                WebhookIngressIdentity.tenant_id == tenant_id
            )
        )
        rows = list(result.scalars().all())

    assert len(rows) == 1
    row = rows[0]
    assert row.provider == "shopify"
    assert row.provider_native_event_reference
    assert row.provider_native_commerce_reference
    assert row.normalized_commerce_reference_kind
    assert row.normalized_commerce_reference_value
    assert row.verified_commerce_ingress_state == "authenticity_verified"
    assert row.verified_at is not None


@pytest.mark.asyncio
async def test_b22_p6_b23_readiness_proves_ingress_path_never_invokes_reconciliation_logic(
    monkeypatch: pytest.MonkeyPatch,
):
    tenant_id, api_key, secrets = await create_tenant_with_secrets()
    body = _shopify_request_body()

    reconciliation_invocations = {"count": 0}

    async def _forbidden_reconcile_order(*args, **kwargs):  # type: ignore[no-untyped-def]
        reconciliation_invocations["count"] += 1
        raise AssertionError("B2.2 ingress path must not invoke reconcile_order")

    async def _forbidden_get_reconciliation(*args, **kwargs):  # type: ignore[no-untyped-def]
        reconciliation_invocations["count"] += 1
        raise AssertionError(
            "B2.2 ingress path must not invoke get_reconciliation_by_order"
        )

    monkeypatch.setattr(
        RevenueReconciliationService,
        "reconcile_order",
        _forbidden_reconcile_order,
    )
    monkeypatch.setattr(
        RevenueReconciliationService,
        "get_reconciliation_by_order",
        _forbidden_get_reconciliation,
    )

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers={
                "X-Shopify-Hmac-Sha256": sign_shopify(body, secrets["shopify_webhook_secret"]),
                "X-Shopify-Topic": "orders/create",
                "X-Skeldir-Tenant-Key": api_key,
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"
    assert reconciliation_invocations["count"] == 0

    async with get_session(tenant_id=tenant_id) as session:
        row = (
            await session.execute(
                select(WebhookIngressIdentity).where(
                    WebhookIngressIdentity.tenant_id == tenant_id
                )
            )
        ).scalars().first()
    assert row is not None
    assert row.verified_commerce_ingress_state == "authenticity_verified"

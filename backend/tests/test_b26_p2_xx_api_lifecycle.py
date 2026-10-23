"""XXIII B2 API-level lifecycle refusal regression.

The derivation-level corpus proved the classifier classes; this test proves
the public Shopify ingress returns a governed refusal and creates no pending
ingress row for terminal lifecycle bodies. A 500 here is the prior defect.
"""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("TESTING", "1")

from app.main import app  # noqa: E402
from app.core.secrets import get_database_url  # noqa: E402
from tests.helpers.webhook_secret_seed import (  # noqa: E402
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)

pytestmark = pytest.mark.asyncio


async def _tenant():
    tenant_id = uuid4()
    api_key = f"b26_p2_xx_api_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    secrets = {
        "shopify_webhook_secret": "shopify_secret",
        "stripe_webhook_secret": "stripe_secret",
        "paypal_webhook_secret": "paypal_secret",
        "woocommerce_webhook_secret": "woo_secret",
    }
    insert = webhook_secret_insert_params(
        shopify_secret=secrets["shopify_webhook_secret"],
        stripe_secret=secrets["stripe_webhook_secret"],
        paypal_secret=secrets["paypal_webhook_secret"],
        woocommerce_secret=secrets["woocommerce_webhook_secret"],
    )
    conn = await asyncpg.connect(get_database_url())
    try:
        # RAW_SQL_ALLOWLIST: test seeds tenant webhook secrets
        await conn.execute(
            """
            INSERT INTO tenants (id, api_key_hash, name, notification_email,
                                 """
            + webhook_secret_insert_columns()
            + """, created_at, updated_at)
            VALUES ($1, $2, $3, $4,
                    pgp_sym_encrypt($5, $8), $9,
                    pgp_sym_encrypt($6, $8), $9,
                    pgp_sym_encrypt($7, $8), $9,
                    pgp_sym_encrypt($10, $8), $9,
                    NOW(), NOW())
            """,
            str(tenant_id),
            api_key_hash,
            f"b26p2-xx-api-{str(tenant_id)[:8]}",
            f"b26p2-xx-api-{str(tenant_id)[:8]}@example.invalid",
            secrets["shopify_webhook_secret"],
            secrets["stripe_webhook_secret"],
            secrets["paypal_webhook_secret"],
            insert["webhook_secret_key"],
            insert["webhook_secret_key_id"],
            secrets["woocommerce_webhook_secret"],
        )
    finally:
        await conn.close()
    return str(tenant_id), api_key, secrets["shopify_webhook_secret"]


def _body(order_id: int, lifecycle: dict) -> bytes:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "id": order_id,
        "total_price": "42.50",
        "currency": "USD",
        "financial_status": "paid",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(lifecycle)
    return json.dumps(payload, separators=(",", ":")).encode()


def _headers(api_key: str, secret: str, body: bytes) -> dict[str, str]:
    signature = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    return {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": api_key,
        "X-Shopify-Hmac-Sha256": signature,
        "X-Shopify-Topic": "orders/create",
    }


@pytest.mark.parametrize(
    "lifecycle",
    [
        {"financial_status": "refunded", "refunds": [{"id": 1}]},
        {"financial_status": "partially_refunded", "refunds": [{"id": 2}]},
        {"financial_status": "voided"},
        {"cancel_reason": "fraud", "financial_status": "voided"},
        {"financial_status": "failed"},
    ],
)
async def test_terminal_shopify_lifecycle_is_governed_refusal(lifecycle):
    tenant_id, api_key, secret = await _tenant()
    order_id = int(uuid4().int % 1_000_000_000)
    body = _body(order_id, lifecycle)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/webhooks/shopify/order_create",
            content=body,
            headers=_headers(api_key, secret, body),
        )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unsupported_event_family_ignored"
    conn = await asyncpg.connect(get_database_url())
    try:
        count = await conn.fetchval(
            """
            SELECT count(*) FROM webhook_ingress_identities
            WHERE tenant_id = $1 AND provider = 'shopify'
              AND provider_native_event_reference = $2
            """,
            tenant_id,
            str(order_id),
        )
    finally:
        await conn.close()
    assert count == 0

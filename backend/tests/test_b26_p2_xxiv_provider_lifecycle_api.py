"""XXIV A9/B2/B7: signed provider lifecycle refusals at the public ingress.

Each supported provider is exercised with a real signature verifier and the
real ASGI webhook route. Terminal lifecycle payloads must return a governed
HTTP 200 refusal and leave no ingress authority row. The positive control
proves the same family shape with a monetary lifecycle state is admitted by
the relay preflight (downstream conduction is covered by the topology and
B2.3 batteries).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("TESTING", "1")

from app.api import webhooks  # noqa: E402
from app.core.secrets import get_database_url  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers.paypal_signature import (  # noqa: E402
    DEFAULT_PAYPAL_TEST_CERT_URL,
    build_paypal_auth_headers,
    install_paypal_cert_fetcher,
)
from tests.helpers.webhook_secret_seed import (  # noqa: E402
    webhook_secret_insert_columns,
    webhook_secret_insert_params,
)

pytestmark = pytest.mark.asyncio

SHOPIFY_SECRET = "shopify_secret"
STRIPE_SECRET = "stripe_secret"
PAYPAL_WEBHOOK_ID = "paypal_webhook_id"
WOO_SECRET = "woo_secret"


async def _tenant() -> tuple[str, str]:
    tenant_id = uuid4()
    api_key = f"b26_p2_xxiv_lifecycle_{uuid4()}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    insert = webhook_secret_insert_params(
        shopify_secret=SHOPIFY_SECRET,
        stripe_secret=STRIPE_SECRET,
        paypal_secret=PAYPAL_WEBHOOK_ID,
        woocommerce_secret=WOO_SECRET,
    )
    conn = await asyncpg.connect(get_database_url())
    try:
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
            f"b26p2-xxiv-lifecycle-{str(tenant_id)[:8]}",
            f"b26p2-xxiv-lifecycle-{str(tenant_id)[:8]}@example.invalid",
            SHOPIFY_SECRET,
            STRIPE_SECRET,
            PAYPAL_WEBHOOK_ID,
            insert["webhook_secret_key"],
            insert["webhook_secret_key_id"],
            WOO_SECRET,
        )
    finally:
        await conn.close()
    return str(tenant_id), api_key


def _stripe_headers(api_key: str, body: bytes) -> dict[str, str]:
    timestamp = int(time.time())
    signature = hmac.new(
        STRIPE_SECRET.encode(),
        f"{timestamp}.{body.decode('utf-8')}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": api_key,
        "Stripe-Signature": f"t={timestamp},v1={signature}",
    }


def _shopify_headers(api_key: str, body: bytes) -> dict[str, str]:
    signature = base64.b64encode(
        hmac.new(SHOPIFY_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": api_key,
        "X-Shopify-Hmac-Sha256": signature,
        "X-Shopify-Topic": "orders/create",
    }


def _woo_headers(api_key: str, body: bytes) -> dict[str, str]:
    signature = base64.b64encode(
        hmac.new(WOO_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": api_key,
        "X-WC-Webhook-Signature": signature,
        "X-WC-Webhook-Topic": "order.completed",
    }


def _paypal_headers(api_key: str, body: bytes) -> dict[str, str]:
    headers = build_paypal_auth_headers(
        raw_body=body,
        webhook_id=PAYPAL_WEBHOOK_ID,
        cert_url=DEFAULT_PAYPAL_TEST_CERT_URL,
    )
    return {
        "Content-Type": "application/json",
        "X-Skeldir-Tenant-Key": api_key,
        **headers,
    }


def _body(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stripe_v2(status: str) -> dict:
    return {
        "id": f"evt_{uuid4().hex[:12]}",
        "type": "payment_intent.succeeded",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": f"pi_{uuid4().hex[:12]}",
                "amount": 4250,
                "currency": "usd",
                "status": status,
            }
        },
    }


def _stripe_v1(status: str) -> dict:
    return {
        "id": f"pi_{uuid4().hex[:12]}",
        "type": "payment_intent.succeeded",
        "amount": 4250,
        "currency": "usd",
        "created": int(time.time()),
        "status": status,
    }


def _paypal(state: str) -> dict:
    return {
        "id": f"txn_{uuid4().hex[:12]}",
        "event_type": "payment.sale.completed",
        "state": state,
        "amount": {"total": "42.50", "currency": "USD"},
        "create_time": _now(),
    }


def _woo(status: str) -> dict:
    now = _now()
    return {
        "id": int(uuid4().int % 1_000_000_000),
        "status": status,
        "currency": "USD",
        "total": "42.50",
        "date_created": now,
        "date_completed": now,
    }


def _shopify(lifecycle: dict) -> dict:
    now = _now()
    payload = {
        "id": int(uuid4().int % 1_000_000_000),
        "total_price": "42.50",
        "currency": "USD",
        "financial_status": "paid",
        "created_at": now,
        "updated_at": now,
    }
    payload.update(lifecycle)
    return payload


async def _post(
    path: str, body: bytes, headers: dict[str, str]
) -> tuple[int, dict]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(path, content=body, headers=headers)
    return response.status_code, response.json()


async def _ingress_count(tenant_id: str, provider: str) -> int:
    conn = await asyncpg.connect(get_database_url())
    try:
        return int(
            await conn.fetchval(
                "SELECT count(*) FROM webhook_ingress_identities"
                " WHERE tenant_id = $1 AND provider = $2",
                tenant_id,
                provider,
            )
        )
    finally:
        await conn.close()


@pytest.mark.parametrize("status", ["failed", "canceled", "requires_payment_method"])
async def test_stripe_v2_terminal_lifecycle_refused(status: str) -> None:
    tenant_id, api_key = await _tenant()
    body = _body(_stripe_v2(status))
    code, payload = await _post(
        "/api/webhooks/stripe/payment_intent/succeeded",
        body,
        _stripe_headers(api_key, body),
    )
    assert code == 200, payload
    assert payload["status"] == "unsupported_event_family_ignored"
    assert await _ingress_count(tenant_id, "stripe") == 0


@pytest.mark.parametrize("status", ["failed", "canceled"])
async def test_stripe_v1_terminal_lifecycle_refused(status: str) -> None:
    tenant_id, api_key = await _tenant()
    body = _body(_stripe_v1(status))
    code, payload = await _post(
        "/api/webhooks/stripe/payment_intent_succeeded",
        body,
        _stripe_headers(api_key, body),
    )
    assert code == 200, payload
    assert payload["status"] == "unsupported_event_family_ignored"
    assert await _ingress_count(tenant_id, "stripe") == 0


@pytest.mark.parametrize("state", ["denied", "refunded", "voided", "failed"])
async def test_paypal_terminal_lifecycle_refused(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    install_paypal_cert_fetcher(monkeypatch)
    tenant_id, api_key = await _tenant()
    body = _body(_paypal(state))
    code, payload = await _post(
        "/api/webhooks/paypal/sale_completed",
        body,
        _paypal_headers(api_key, body),
    )
    assert code == 200, payload
    assert payload["status"] == "unsupported_event_family_ignored"
    assert await _ingress_count(tenant_id, "paypal") == 0


@pytest.mark.parametrize("status", ["cancelled", "refunded", "failed"])
async def test_woocommerce_terminal_lifecycle_refused(status: str) -> None:
    tenant_id, api_key = await _tenant()
    body = _body(_woo(status))
    code, payload = await _post(
        "/api/webhooks/woocommerce/order_completed",
        body,
        _woo_headers(api_key, body),
    )
    assert code == 200, payload
    assert payload["status"] == "unsupported_event_family_ignored"
    assert await _ingress_count(tenant_id, "woocommerce") == 0


@pytest.mark.parametrize(
    "lifecycle",
    [
        {"financial_status": "refunded", "refunds": [{"id": 1}]},
        {"financial_status": "voided"},
        {"cancel_reason": "fraud", "financial_status": "voided"},
        {"financial_status": "failed"},
    ],
)
async def test_shopify_terminal_lifecycle_refused(lifecycle: dict) -> None:
    tenant_id, api_key = await _tenant()
    body = _body(_shopify(lifecycle))
    code, payload = await _post(
        "/api/webhooks/shopify/order_create",
        body,
        _shopify_headers(api_key, body),
    )
    assert code == 200, payload
    assert payload["status"] == "unsupported_event_family_ignored"
    assert await _ingress_count(tenant_id, "shopify") == 0


async def test_supported_lifecycle_states_pass_the_relay_preflight() -> None:
    assert (
        webhooks._unsupported_event_family_reason(
            provider="stripe",
            payload=_stripe_v2("succeeded"),
            request_headers={},
        )
        is None
    )
    assert (
        webhooks._unsupported_event_family_reason(
            provider="paypal",
            payload=_paypal("completed"),
            request_headers={},
        )
        is None
    )
    assert (
        webhooks._unsupported_event_family_reason(
            provider="woocommerce",
            payload=_woo("completed"),
            request_headers={
                "x-wc-webhook-topic": "order.completed",
            },
        )
        is None
    )

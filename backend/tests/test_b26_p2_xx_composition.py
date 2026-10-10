"""B2.6-P2 Corrective XX compositional-closure unit battery (pure, no DB).

H-XX-B: a cancelled, voided, or refunded Shopify body redelivered
under an orders/create topic must not become an orders.create
financial fact; a status-less WooCommerce body must not gain family
from the unsigned topic header. Honest traffic conducts unchanged.
"""

import json

import pytest

from app.webhooks.commerce_derivation import (
    CommerceDerivationError,
    derive_commerce,
    derive_event_family,
    derive_event_family_source,
)


def _shopify_body(**overrides: object) -> bytes:
    base: dict[str, object] = {
        "id": 900001,
        "total_price": "10.00",
        "currency": "USD",
        "created_at": "2026-09-01T00:00:00Z",
    }
    base.update(overrides)
    return json.dumps(base).encode()


def test_xx_honest_shopify_create_conducts() -> None:
    body = _shopify_body()
    assert derive_event_family("shopify", body, topic="orders/create") == (
        "orders.create"
    )
    assert derive_event_family_source(
        "shopify", body, topic="orders/create"
    ) == "transport-topic:x-shopify-topic"
    derived = derive_commerce("shopify", body)
    assert derived.verified_amount_minor == 1000
    assert derived.verified_amount_currency == "USD"


@pytest.mark.parametrize(
    "overrides",
    (
        {"cancelled_at": "2026-09-02T00:00:00Z", "cancel_reason": "customer",
         "financial_status": "voided"},
        {"financial_status": "voided"},
        {"financial_status": "refunded", "refunds": [{"id": 1}]},
        {"financial_status": "partially_refunded", "refunds": [{"id": 2}]},
        {"cancel_reason": "fraud", "financial_status": "voided"},
        {"refunds": [{"id": 3}]},
    ),
)
def test_xx_terminal_shopify_body_refused_as_create(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(CommerceDerivationError):
        derive_commerce("shopify", _shopify_body(**overrides))


def test_xx_fulfilled_shopify_order_still_conducts() -> None:
    # closed_at/fulfilled states are valid sales, not terminal lifecycle.
    body = _shopify_body(
        financial_status="paid", closed_at="2026-09-03T00:00:00Z"
    )
    derived = derive_commerce("shopify", body)
    assert derived.verified_amount_minor == 1000


def test_xx_woo_topic_only_refused() -> None:
    body = json.dumps(
        {"id": 7, "currency": "USD", "total": "5.00",
         "date_created": "2026-09-01T00:00:00Z"}
    ).encode()
    with pytest.raises(CommerceDerivationError):
        derive_event_family("woocommerce", body, topic="order.completed")


def test_xx_woo_body_signal_conducts() -> None:
    body = json.dumps(
        {"id": 7, "currency": "USD", "total": "5.00", "status": "completed",
         "date_completed": "2026-09-01T00:00:00Z"}
    ).encode()
    assert derive_event_family("woocommerce", body) == "order.completed"
    assert derive_event_family_source("woocommerce", body) == (
        "body-signal:status"
    )
    derived = derive_commerce("woocommerce", body)
    assert derived.verified_amount_minor == 500


def test_xx_woo_refunded_status_refused() -> None:
    body = json.dumps(
        {"id": 7, "currency": "USD", "total": "5.00", "status": "refunded"}
    ).encode()
    with pytest.raises(CommerceDerivationError):
        derive_event_family("woocommerce", body)


def test_xx_stripe_paypal_unaffected() -> None:
    stripe = json.dumps(
        {"id": "pi_1", "type": "payment_intent.succeeded",
         "data": {"object": {"id": "pi_1", "amount": 1000,
                             "currency": "usd", "created": 1756684800}}}
    ).encode()
    assert derive_event_family("stripe", stripe) == "payment_intent.succeeded"
    paypal = json.dumps(
        {"id": "txn1", "event_type": "PAYMENT.SALE.COMPLETED",
         "amount": {"total": "10.00", "currency": "USD"},
         "create_time": "2026-09-01T00:00:00Z"}
    ).encode()
    assert derive_event_family("paypal", paypal) == "payment.sale.completed"

"""XXV Shopify post-capture refund parser cells.

The physical Shopify capture/refund journey is the lane falsifier; these cells
pin the provider-body interpretation and its fail-closed boundaries.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.webhooks.commerce_derivation import (
    CommerceDerivationError,
    adjustment_event_references,
    derive_adjustment,
    derive_adjustments,
)


def _refund(**overrides: object) -> bytes:
    payload = {
        "id": 9001,
        "order_id": 7001,
        "created_at": "2026-10-28T18:00:00Z",
        "transactions": [
            {
                "amount": "10.00",
                "currency": "USD",
                "kind": "refund",
                "status": "success",
            }
        ],
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":")).encode()


def test_shopify_refund_is_a_post_capture_adjustment() -> None:
    adjusted = derive_adjustment("shopify", _refund())

    assert adjusted.provider == "shopify"
    assert adjusted.provider_native_event_reference == "9001"
    assert adjusted.provider_native_commerce_reference == "7001"
    assert adjusted.verified_amount_minor == 1000
    assert adjusted.verified_amount_currency == "USD"
    assert adjusted.verified_amount_scale == 2
    assert adjusted.event_timestamp == datetime(2026, 10, 28, 18, tzinfo=timezone.utc)


def test_shopify_refund_sums_successful_transactions_only() -> None:
    body = json.dumps(
        {
            "id": 9002,
            "order_id": 7002,
            "created_at": "2026-10-28T18:00:00Z",
            "transactions": [
                {"amount": "10.00", "currency": "USD", "status": "success"},
                {"amount": "2.50", "currency": "USD", "status": "success"},
                {"amount": "4.00", "currency": "USD", "status": "failure"},
            ],
        },
        separators=(",", ":"),
    ).encode()

    adjusted = derive_adjustment("shopify", body)

    assert adjusted.verified_amount_minor == 1250


def test_shopify_refund_without_order_parent_is_refused() -> None:
    with pytest.raises(CommerceDerivationError, match="parent order id"):
        derive_adjustment("shopify", _refund(order_id=None))


def test_shopify_refund_with_mixed_currencies_is_refused() -> None:
    body = json.dumps(
        {
            "id": 9003,
            "order_id": 7003,
            "created_at": "2026-10-28T18:00:00Z",
            "transactions": [
                {"amount": "10.00", "currency": "USD", "status": "success"},
                {"amount": "2.00", "currency": "EUR", "status": "success"},
            ],
        },
        separators=(",", ":"),
    ).encode()

    with pytest.raises(CommerceDerivationError, match="disagree on currency"):
        derive_adjustment("shopify", body)


def test_shopify_refund_without_successful_transaction_is_refused() -> None:
    with pytest.raises(CommerceDerivationError, match="no successful refund"):
        derive_adjustment(
            "shopify",
            _refund(
                transactions=[
                    {
                        "amount": "10.00",
                        "currency": "USD",
                        "kind": "refund",
                        "status": "failure",
                    }
                ]
            ),
        )


def test_woocommerce_refund_is_a_post_capture_adjustment() -> None:
    body = json.dumps(
        {
            "id": 7101,
            "currency": "USD",
            "date_completed": "2026-10-28T18:00:00Z",
            "refunds": [
                {
                    "id": 9101,
                    "total": "-10.00",
                    "date_created": "2026-10-28T18:05:00Z",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()

    adjusted = derive_adjustment("woocommerce", body)

    assert adjusted.provider == "woocommerce"
    assert adjusted.provider_native_event_reference == "9101"
    assert adjusted.provider_native_commerce_reference == "7101"
    assert adjusted.verified_amount_minor == 1000
    assert adjusted.verified_amount_currency == "USD"


def test_woocommerce_refund_without_refund_entry_is_refused() -> None:
    body = json.dumps(
        {"id": 7102, "currency": "USD", "refunds": []},
        separators=(",", ":"),
    ).encode()

    with pytest.raises(CommerceDerivationError, match="requires a refund entry"):
        derive_adjustment("woocommerce", body)


def _stripe_refund(*, status: str = "succeeded", amount: object = 1000) -> bytes:
    return json.dumps(
        {
            "id": f"evt_{status}",
            "type": "refund.created",
            "created": 1793200000,
            "data": {
                "object": {
                    "id": "re_shared",
                    "object": "refund",
                    "payment_intent": "pi_shared",
                    "amount": amount,
                    "currency": "usd",
                    "created": 1793200000,
                    "status": status,
                }
            },
        },
        separators=(",", ":"),
    ).encode()


def test_stripe_refund_must_be_financially_completed() -> None:
    for status in ("pending", "failed", "canceled"):
        with pytest.raises(CommerceDerivationError, match="financially completed"):
            derive_adjustment("stripe", _stripe_refund(status=status))


def test_stripe_refund_rejects_fractional_minor_units() -> None:
    for amount in (10.5, "10.5", "10.001"):
        with pytest.raises(CommerceDerivationError, match="integer cents"):
            derive_adjustment("stripe", _stripe_refund(amount=amount))


def test_stripe_overlapping_notifications_share_the_refund_identity() -> None:
    refund_created = derive_adjustment("stripe", _stripe_refund())
    charge_refunded = derive_adjustment(
        "stripe",
        json.dumps(
            {
                "id": "evt_charge_refunded",
                "type": "charge.refunded",
                "created": 1793200001,
                "data": {
                    "object": {
                        "id": "ch_shared",
                        "object": "charge",
                        "payment_intent": "pi_shared",
                        "amount_refunded": 1000,
                        "currency": "usd",
                        "refunds": {
                            "data": [
                                {
                                    "id": "re_shared",
                                    "object": "refund",
                                    "payment_intent": "pi_shared",
                                    "amount": 1000,
                                    "currency": "usd",
                                    "created": 1793200000,
                                    "status": "succeeded",
                                }
                            ]
                        },
                    }
                },
            },
            separators=(",", ":"),
        ).encode(),
    )

    assert (
        refund_created.provider_native_event_reference
        == charge_refunded.provider_native_event_reference
        == "re_shared"
    )
    assert refund_created.verified_amount_minor == charge_refunded.verified_amount_minor == 1000


def test_stripe_charge_refunded_reads_latest_refund_not_cumulative_total() -> None:
    adjusted = derive_adjustments(
        "stripe",
        json.dumps(
            {
                "id": "evt_cumulative",
                "type": "charge.refunded",
                "created": 1793200002,
                "data": {
                    "object": {
                        "id": "ch_shared",
                        "object": "charge",
                        "payment_intent": "pi_shared",
                        "amount_refunded": 1500,
                        "currency": "usd",
                        "refunds": {
                            "data": [
                                {
                                    "id": "re_first",
                                    "amount": 1000,
                                    "currency": "usd",
                                    "created": 1793200000,
                                    "status": "succeeded",
                                },
                                {
                                    "id": "re_second",
                                    "amount": 500,
                                    "currency": "usd",
                                    "created": 1793200001,
                                    "status": "succeeded",
                                },
                            ]
                        },
                    }
                },
            },
            separators=(",", ":"),
        ).encode(),
    )

    assert [item.provider_native_event_reference for item in adjusted] == [
        "re_first",
        "re_second",
    ]
    assert [item.verified_amount_minor for item in adjusted] == [1000, 500]
    with pytest.raises(CommerceDerivationError, match="explicit provider event"):
        derive_adjustment(
            "stripe",
            json.dumps(
                {
                    "id": "evt_cumulative",
                    "type": "charge.refunded",
                    "created": 1793200002,
                    "data": {
                        "object": {
                            "object": "charge",
                            "payment_intent": "pi_shared",
                            "currency": "usd",
                            "amount_refunded": 1500,
                            "refunds": {
                                "data": [
                                    {"id": "re_first", "amount": 1000, "status": "succeeded"},
                                    {"id": "re_second", "amount": 500, "status": "succeeded"},
                                ]
                            },
                        }
                    },
                }
            ).encode(),
        )


def test_shopify_refund_rejects_fractional_minor_units() -> None:
    with pytest.raises(CommerceDerivationError, match="amount invalid"):
        derive_adjustment(
            "shopify",
            _refund(
                transactions=[
                    {
                        "amount": "10.001",
                        "currency": "USD",
                        "kind": "refund",
                        "status": "success",
                    }
                ]
            ),
        )


def test_shopify_refund_transaction_without_status_is_refused() -> None:
    with pytest.raises(CommerceDerivationError, match="not completed"):
        derive_adjustment(
            "shopify",
            _refund(
                transactions=[
                    {
                        "amount": "10.00",
                        "currency": "USD",
                        "kind": "refund",
                    }
                ]
            ),
        )


def test_woocommerce_first_snapshot_keeps_every_unseen_refund() -> None:
    body = json.dumps(
        {
            "id": 7201,
            "currency": "USD",
            "date_completed": "2026-10-28T18:00:00Z",
            "refunds": [
                {"id": 9201, "total": "-10.00", "date_created": "2026-10-28T18:01:00Z"},
                {"id": 9202, "total": "-5.00", "date_created": "2026-10-28T18:02:00Z"},
            ],
        },
        separators=(",", ":"),
    ).encode()

    adjustments = derive_adjustments("woocommerce", body)

    assert [item.provider_native_event_reference for item in adjustments] == [
        "9201",
        "9202",
    ]
    assert [item.verified_amount_minor for item in adjustments] == [1000, 500]
    assert adjustment_event_references("woocommerce", body) == ["9201", "9202"]


def test_woocommerce_documented_refund_without_status_is_authoritative() -> None:
    body = json.dumps(
        {
            "id": 7202,
            "currency": "USD",
            "date_completed": "2026-10-28T18:00:00Z",
            "refunds": [
                {
                    "id": 9203,
                    "total": "-10.00",
                    "date_created": "2026-10-28T18:03:00Z",
                }
            ],
        },
        separators=(",", ":"),
    ).encode()

    adjustments = derive_adjustments("woocommerce", body)

    assert len(adjustments) == 1
    assert adjustments[0].verified_amount_minor == 1000


def test_woocommerce_refund_without_native_time_is_qualified() -> None:
    body = json.dumps(
        {
            "id": 7203,
            "currency": "USD",
            "date_completed": "2026-10-28T18:00:00Z",
            "refunds": [{"id": 9204, "total": "-10.00"}],
        },
        separators=(",", ":"),
    ).encode()

    with pytest.raises(CommerceDerivationError, match="date_created is required"):
        derive_adjustments("woocommerce", body)


def test_stripe_charge_refunded_refuses_incomplete_collection() -> None:
    with pytest.raises(CommerceDerivationError, match="collection is incomplete"):
        derive_adjustments(
            "stripe",
            json.dumps(
                {
                    "id": "evt_incomplete",
                    "type": "charge.refunded",
                    "data": {
                        "object": {
                            "object": "charge",
                            "payment_intent": "pi_shared",
                            "currency": "usd",
                            "amount_refunded": 1500,
                            "refunds": {
                                "data": [
                                    {
                                        "id": "re_partial",
                                        "amount": 500,
                                        "status": "succeeded",
                                    }
                                ]
                            },
                        }
                    },
                }
            ).encode(),
        )


def test_stripe_charge_refunded_refuses_unresolved_entry_in_declared_total() -> None:
    with pytest.raises(CommerceDerivationError, match="collection is incomplete"):
        derive_adjustments(
            "stripe",
            json.dumps(
                {
                    "id": "evt_pending_collection",
                    "type": "charge.refunded",
                    "data": {
                        "object": {
                            "object": "charge",
                            "payment_intent": "pi_shared",
                            "currency": "usd",
                            "amount_refunded": 1500,
                            "refunds": {
                                "data": [
                                    {"id": "re_done", "amount": 500, "status": "succeeded"},
                                    {"id": "re_pending", "amount": 1000, "status": "pending"},
                                ]
                            },
                        }
                    },
                }
            ).encode(),
        )


def _paypal_refund(*, status: str = "COMPLETED", value: object = "10.00") -> bytes:
    return json.dumps(
        {
            "id": "WH-refund",
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "create_time": "2026-10-28T18:00:00Z",
            "resource": {
                "id": "re_paypal_1",
                "status": status,
                "create_time": "2026-10-28T18:00:00Z",
                "amount": {"value": value, "currency_code": "USD"},
                "supplementary_data": {
                    "related_ids": {"capture_id": "CAP-1"}
                },
            },
        },
        separators=(",", ":"),
    ).encode()


def test_paypal_completed_refund_is_a_post_capture_adjustment() -> None:
    adjusted = derive_adjustment("paypal", _paypal_refund())
    assert adjusted.provider == "paypal"
    assert adjusted.provider_native_event_reference == "re_paypal_1"
    assert adjusted.provider_native_commerce_reference == "CAP-1"
    assert adjusted.verified_amount_minor == 1000


def test_paypal_refund_must_be_completed() -> None:
    for status in ("PENDING", "FAILED"):
        with pytest.raises(CommerceDerivationError, match="not financially completed"):
            derive_adjustment("paypal", _paypal_refund(status=status))


def test_paypal_refund_rejects_fractional_minor_units() -> None:
    with pytest.raises(CommerceDerivationError, match="amount invalid"):
        derive_adjustment("paypal", _paypal_refund(value="10.001"))

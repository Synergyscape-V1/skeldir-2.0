#!/usr/bin/env python3
"""B2.6-P2 Corrective XVI independent provider-native semantic oracle.

H-XVI-R2/R3: at least one load-bearing semantic oracle must derive
expected commerce meaning from a source INDEPENDENT of the production
derivation implementation. This file is that oracle.

INDEPENDENCE CONTRACT (load-bearing, enforced by the purity gate in the
pytest wrapper): this file MUST NOT import, reference, or reuse the
production derivation helper, the production binding comparator, the
production commerce Pydantic projection, the relay handoff, or anything
under the application package. It uses only the Python standard library (json + decimal + datetime)
and hand-written provider-native fixture law. The expected values below
are fixed golden literals transcribed from the provider contract shapes
(stripe flat payment_intent / envelope event, shopify order JSON,
paypal flat sale per webhooks.paypal.bundled.yaml, woocommerce order
JSON), not computed by any production helper.

The comparison against production output lives OUTSIDE this file (in
the pytest wrapper, which imports both this oracle and the production
helper and asserts equality). This separation is the point: a shared
production-parser bug makes API and root agree on a wrong field while
this oracle stays correct, turning the gate RED.

Each provider has its own gate function so a provider-specific parser
defect fails exactly that provider's gate while shared infrastructure
stays green (H-XVI-R3).

Exit code is the gate. Prints B26_P2_XVI_ORACLE_PASS on success.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

FORBIDDEN_SYMBOLS = (
    "derive_commerce",
    "binding_mismatches",
    "from app",
    "from app.",
    "import app",
    "import app.",
    "relay_envelope",
    "handoff_view",
)


def _epoch(value) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an instant")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.astimezone(timezone.utc).timestamp())
    raise ValueError(f"not an instant: {value!r}")


def _minor(amount_str, scale: int) -> int:
    quant = Decimal(10) ** (-scale)
    rounded = Decimal(str(amount_str)).quantize(quant, rounding=ROUND_HALF_UP)
    return int(rounded * (10**scale))


def oracle_stripe(raw: bytes) -> dict:
    """Independent stripe law: flat payment_intent or envelope event."""
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload root must be an object")
    data = payload.get("data")
    obj = payload
    envelope_id = None
    if isinstance(data, dict):
        inner = data.get("object")
        if isinstance(inner, dict) and inner.get("id"):
            obj = inner
            envelope_id = str(payload.get("id") or "").strip() or None
    commerce_id = str(obj.get("id") or "").strip()
    if not commerce_id:
        raise ValueError("stripe payment intent id is required")
    amount = obj.get("amount")
    if amount is None or isinstance(amount, bool):
        raise ValueError("stripe amount is required")
    amount_minor = int(amount)
    if amount_minor <= 0:
        raise ValueError("stripe amount must be positive")
    currency = str(obj.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("stripe currency must be 3 letters")
    scale = {"JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3}.get(currency, 2)
    created = payload.get("created")
    if created is None:
        created = obj.get("created")
    if created is None:
        raise ValueError("stripe created timestamp is required")
    return {
        "provider": "stripe",
        "provider_native_event_reference": envelope_id or commerce_id,
        "provider_native_commerce_reference": commerce_id,
        "normalized_commerce_reference_kind": "stripe_payment_intent_id",
        "normalized_commerce_reference_value": commerce_id,
        "verified_amount_minor": amount_minor,
        "verified_amount_currency": currency,
        "verified_amount_scale": scale,
        "event_timestamp_epoch": _epoch(created),
    }


def oracle_shopify(raw: bytes) -> dict:
    """Independent shopify law: order JSON."""
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload root must be an object")
    order_id = str(payload.get("id") or "").strip()
    if not order_id:
        raise ValueError("shopify order id is required")
    currency = str(payload.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("shopify currency must be 3 letters")
    scale = {"JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3}.get(currency, 2)
    total = payload.get("total_price")
    if total is None:
        raise ValueError("shopify total_price is required")
    amount_minor = _minor(total, scale)
    if amount_minor <= 0:
        raise ValueError("shopify total_price must be positive")
    created_at = payload.get("created_at")
    if created_at is None:
        raise ValueError("shopify created_at is required")
    return {
        "provider": "shopify",
        "provider_native_event_reference": order_id,
        "provider_native_commerce_reference": order_id,
        "normalized_commerce_reference_kind": "shopify_order_id",
        "normalized_commerce_reference_value": order_id,
        "verified_amount_minor": amount_minor,
        "verified_amount_currency": currency,
        "verified_amount_scale": scale,
        "event_timestamp_epoch": _epoch(created_at),
    }


def oracle_paypal(raw: bytes) -> dict:
    """Independent paypal law: flat sale JSON (contract shape).

    Resource-enveloped PayPal webhooks are OUTSIDE the supported
    contract (webhooks.paypal.bundled.yaml) and must be refused, not
    coerced: a top-level resource object is not a transaction.
    """
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload root must be an object")
    if isinstance(payload.get("resource"), dict):
        raise ValueError("paypal resource envelopes are out of contract")
    txn_id = str(payload.get("id") or "").strip()
    if not txn_id:
        raise ValueError("paypal transaction id is required")
    amount = payload.get("amount")
    if not isinstance(amount, dict):
        raise ValueError("paypal amount object is required")
    currency = str(amount.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("paypal currency must be 3 letters")
    scale = {"JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3}.get(currency, 2)
    total = amount.get("total")
    if total is None:
        raise ValueError("paypal amount.total is required")
    amount_minor = _minor(total, scale)
    if amount_minor <= 0:
        raise ValueError("paypal amount.total must be positive")
    create_time = payload.get("create_time")
    if create_time is None:
        raise ValueError("paypal create_time is required")
    return {
        "provider": "paypal",
        "provider_native_event_reference": txn_id,
        "provider_native_commerce_reference": txn_id,
        "normalized_commerce_reference_kind": "paypal_transaction_id",
        "normalized_commerce_reference_value": txn_id,
        "verified_amount_minor": amount_minor,
        "verified_amount_currency": currency,
        "verified_amount_scale": scale,
        "event_timestamp_epoch": _epoch(create_time),
    }


def oracle_woocommerce(raw: bytes) -> dict:
    """Independent woocommerce law: order JSON."""
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload root must be an object")
    order_id = str(payload.get("id") or "").strip()
    if not order_id:
        raise ValueError("woocommerce order id is required")
    currency = str(payload.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("woocommerce currency must be 3 letters")
    scale = {"JPY": 0, "KRW": 0, "BHD": 3, "KWD": 3}.get(currency, 2)
    total = payload.get("total")
    if total is None:
        raise ValueError("woocommerce total is required")
    amount_minor = _minor(total, scale)
    if amount_minor <= 0:
        raise ValueError("woocommerce total must be positive")
    stamp = payload.get("date_completed")
    if stamp is None:
        stamp = payload.get("date_created")
    if stamp is None:
        raise ValueError("woocommerce date_completed/date_created is required")
    return {
        "provider": "woocommerce",
        "provider_native_event_reference": order_id,
        "provider_native_commerce_reference": order_id,
        "normalized_commerce_reference_kind": "woocommerce_order_id",
        "normalized_commerce_reference_value": order_id,
        "verified_amount_minor": amount_minor,
        "verified_amount_currency": currency,
        "verified_amount_scale": scale,
        "event_timestamp_epoch": _epoch(stamp),
    }


ORACLES = {
    "stripe": oracle_stripe,
    "shopify": oracle_shopify,
    "paypal": oracle_paypal,
    "woocommerce": oracle_woocommerce,
}

GOLDEN_VECTORS = [
    {
        "id": "stripe-flat-usd",
        "provider": "stripe",
        "raw": b'{"id":"pi_3O","amount":7600,"currency":"usd","created":1700000000}',
        "expected": {
            "provider": "stripe",
            "provider_native_event_reference": "pi_3O",
            "provider_native_commerce_reference": "pi_3O",
            "normalized_commerce_reference_kind": "stripe_payment_intent_id",
            "normalized_commerce_reference_value": "pi_3O",
            "verified_amount_minor": 7600,
            "verified_amount_currency": "USD",
            "verified_amount_scale": 2,
            "event_timestamp_epoch": 1700000000,
        },
    },
    {
        "id": "stripe-envelope-eur",
        "provider": "stripe",
        "raw": b'{"id":"evt_9","created":1700000060,"data":{"object":{"id":"pi_77","amount":100,"currency":"eur","created":1700000000}}}',
        "expected": {
            "provider": "stripe",
            "provider_native_event_reference": "evt_9",
            "provider_native_commerce_reference": "pi_77",
            "normalized_commerce_reference_kind": "stripe_payment_intent_id",
            "normalized_commerce_reference_value": "pi_77",
            "verified_amount_minor": 100,
            "verified_amount_currency": "EUR",
            "verified_amount_scale": 2,
            "event_timestamp_epoch": 1700000060,
        },
    },
    {
        "id": "stripe-flat-jpy",
        "provider": "stripe",
        "raw": b'{"id":"pi_j","amount":1000,"currency":"jpy","created":1700000000}',
        "expected": {
            "provider": "stripe",
            "provider_native_event_reference": "pi_j",
            "provider_native_commerce_reference": "pi_j",
            "normalized_commerce_reference_kind": "stripe_payment_intent_id",
            "normalized_commerce_reference_value": "pi_j",
            "verified_amount_minor": 1000,
            "verified_amount_currency": "JPY",
            "verified_amount_scale": 0,
            "event_timestamp_epoch": 1700000000,
        },
    },
    {
        "id": "shopify-order-usd",
        "provider": "shopify",
        "raw": b'{"id":12345,"total_price":"76.00","currency":"USD","created_at":"2024-01-15T10:00:00Z"}',
        "expected": {
            "provider": "shopify",
            "provider_native_event_reference": "12345",
            "provider_native_commerce_reference": "12345",
            "normalized_commerce_reference_kind": "shopify_order_id",
            "normalized_commerce_reference_value": "12345",
            "verified_amount_minor": 7600,
            "verified_amount_currency": "USD",
            "verified_amount_scale": 2,
            "event_timestamp_epoch": 1705312800,
        },
    },
    {
        "id": "shopify-order-bhd",
        "provider": "shopify",
        "raw": b'{"id":777,"total_price":"10.000","currency":"BHD","created_at":"2024-01-15T10:00:00Z"}',
        "expected": {
            "provider": "shopify",
            "provider_native_event_reference": "777",
            "provider_native_commerce_reference": "777",
            "normalized_commerce_reference_kind": "shopify_order_id",
            "normalized_commerce_reference_value": "777",
            "verified_amount_minor": 10000,
            "verified_amount_currency": "BHD",
            "verified_amount_scale": 3,
            "event_timestamp_epoch": 1705312800,
        },
    },
    {
        "id": "paypal-sale-usd",
        "provider": "paypal",
        "raw": b'{"id":"PAY-1","amount":{"total":"50.00","currency":"USD"},"create_time":"2024-01-15T10:00:00Z"}',
        "expected": {
            "provider": "paypal",
            "provider_native_event_reference": "PAY-1",
            "provider_native_commerce_reference": "PAY-1",
            "normalized_commerce_reference_kind": "paypal_transaction_id",
            "normalized_commerce_reference_value": "PAY-1",
            "verified_amount_minor": 5000,
            "verified_amount_currency": "USD",
            "verified_amount_scale": 2,
            "event_timestamp_epoch": 1705312800,
        },
    },
    {
        "id": "woocommerce-order-usd",
        "provider": "woocommerce",
        "raw": b'{"id":999,"total":"19.99","currency":"USD","date_completed":"2024-01-15T10:00:00+00:00"}',
        "expected": {
            "provider": "woocommerce",
            "provider_native_event_reference": "999",
            "provider_native_commerce_reference": "999",
            "normalized_commerce_reference_kind": "woocommerce_order_id",
            "normalized_commerce_reference_value": "999",
            "verified_amount_minor": 1999,
            "verified_amount_currency": "USD",
            "verified_amount_scale": 2,
            "event_timestamp_epoch": 1705312800,
        },
    },
    {
        "id": "woocommerce-date-created-fallback",
        "provider": "woocommerce",
        "raw": b'{"id":1000,"total":"5.00","currency":"USD","date_created":"2024-01-15T10:00:00+00:00"}',
        "expected": {
            "provider": "woocommerce",
            "provider_native_event_reference": "1000",
            "provider_native_commerce_reference": "1000",
            "normalized_commerce_reference_kind": "woocommerce_order_id",
            "normalized_commerce_reference_value": "1000",
            "verified_amount_minor": 500,
            "verified_amount_currency": "USD",
            "verified_amount_scale": 2,
            "event_timestamp_epoch": 1705312800,
        },
    },
]

# Raw shapes that MUST be refused (fail closed, never coerced).
REFUSAL_VECTORS = [
    {
        "id": "stripe-no-timestamp",
        "provider": "stripe",
        "raw": b'{"id":"pi_x","amount":100,"currency":"usd"}',
    },
    {
        "id": "stripe-checkout-session-shape",
        "provider": "stripe",
        "raw": b'{"id":"cs_1","object":"checkout.session","amount_total":5000,"currency":"usd","created":1700000000}',
    },
    {
        "id": "paypal-resource-envelope",
        "provider": "paypal",
        "raw": b'{"id":"WH-1","resource":{"id":"PAY-9","amount":{"total":"9.00","currency":"USD"},"create_time":"2024-01-15T10:00:00Z"}}',
    },
    {
        "id": "shopify-no-timestamp",
        "provider": "shopify",
        "raw": b'{"id":5,"total_price":"1.00","currency":"USD"}',
    },
    {
        "id": "woocommerce-no-timestamp",
        "provider": "woocommerce",
        "raw": b'{"id":6,"total":"1.00","currency":"USD"}',
    },
    {
        "id": "paypal-no-timestamp",
        "provider": "paypal",
        "raw": b'{"id":"PAY-2","amount":{"total":"1.00","currency":"USD"}}',
    },
]


def check_purity() -> list[str]:
    """The oracle file must not share the production semantic helper.

    The symbol blocklist declaration itself is excluded from the scan
    (it names what is forbidden); every other line is scanned.
    """
    import pathlib
    import re

    text = pathlib.Path(__file__).read_text(encoding="utf-8")
    text = re.sub(
        r"FORBIDDEN_SYMBOLS\s*=\s*\(.*?\)",
        "FORBIDDEN_SYMBOLS = ()",
        text,
        flags=re.S,
    )
    return [sym for sym in FORBIDDEN_SYMBOLS if sym in text]


def main() -> int:
    parser = argparse.ArgumentParser(description="XVI independent oracle.")
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    impure = check_purity()
    if impure:
        violations.append(f"oracle_impure:{impure}")
    for vector in GOLDEN_VECTORS:
        if args.provider and vector["provider"] != args.provider:
            continue
        try:
            observed = ORACLES[vector["provider"]](vector["raw"])
        except Exception as exc:
            violations.append(f"oracle_error:{vector['id']}:{exc}")
            continue
        if observed != vector["expected"]:
            keys = sorted(
                set(observed) | set(vector["expected"])
            )
            diff = {
                k: (observed.get(k), vector["expected"].get(k))
                for k in keys
                if observed.get(k) != vector["expected"].get(k)
            }
            violations.append(f"oracle_mismatch:{vector['id']}:{diff}")
    for vector in REFUSAL_VECTORS:
        if args.provider and vector["provider"] != args.provider:
            continue
        try:
            ORACLES[vector["provider"]](vector["raw"])
            violations.append(f"oracle_refusal_missing:{vector['id']}")
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
    if violations:
        print("B26_P2_XVI_ORACLE_FAIL")
        print(";".join(sorted(violations)))
        return 1
    print("B26_P2_XVI_ORACLE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

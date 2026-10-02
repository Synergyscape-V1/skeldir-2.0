"""B2.6-P2 Corrective XV sovereign provider-commerce derivation.

Single semantic authority for provider-native commerce meaning. Both the
general API (handoff construction) and the dedicated authentication trust
root (binding enforcement) derive authoritative financial fields from the
exact verified provider bytes through this module -- never through parallel
per-process parsers.

Law (H-XV-R1/R2):
    authoritative_field == sovereign_derivation(verified_raw_provider_bytes)

The relay handoff is advisory/cross-check information only. The root
re-derives every material field from the verified bytes and refuses any
mismatch before persistence. No LLM, Bayesian, or probabilistic dependency
may enter this path: parsing is deterministic over the raw bytes.

Supported providers: stripe, shopify, paypal, woocommerce.
Rail law (elsewhere): rail == provider.
Money law: integer minor units, ISO 4217 currency exponents. Canonical
reconciliation scope is USD-only (sovereign currency universe {"USD"} in
app/revenue_verification/verification_coverage.py, enforced at the
persistence decision points, not in this parser): this module parses what
the bytes say; the root and the direct finalizer refuse non-USD
persistence with b26_p2_unsupported_currency_refused.
Timestamp law: provider-native instant, UTC, second precision. Missing
provider timestamps fail closed (no wall-clock substitution): an
authoritative timestamp must come from authenticated bytes, not from the
verifier's clock.

Contract shapes (do not widen without a contract revision): stripe flat
payment_intent or envelope event(data.object); shopify order JSON;
paypal flat sale JSON per webhooks.paypal.bundled.yaml; woocommerce
order JSON. Real provider envelope shapes outside the contract
(e.g. PayPal resource-enveloped webhooks, Stripe checkout.session
objects) fail closed here and are DLQ-routed upstream -- never coerced
into authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping


class CommerceDerivationError(ValueError):
    """The verified bytes do not determine commerce meaning for the provider."""


SUPPORTED_PROVIDERS = ("stripe", "shopify", "paypal", "woocommerce")

NORMALIZED_KIND_BY_PROVIDER = MappingProxyType(
    {
        "stripe": "stripe_payment_intent_id",
        "shopify": "shopify_order_id",
        "paypal": "paypal_transaction_id",
        "woocommerce": "woocommerce_order_id",
    }
)

# XVI (H-XVI-R13/R20): ISO 4217 currency exponents. Zero-decimal and
# three-decimal currency sets follow the ISO 4217 standard; everything
# else defaults to 2. This table is authoritative for parsing only:
# canonical persistence is USD-only (enforced by the root / direct
# finalizer), so non-USD exponents never enter authenticated truth.
# They are exact here so independent oracles and DLQ classification
# observe true provider semantics rather than a generic placeholder.
_ZERO_DECIMAL_CURRENCIES = frozenset(
    {
        "BIF",
        "CLP",
        "DJF",
        "GNF",
        "ISK",
        "JPY",
        "KMF",
        "KRW",
        "PYG",
        "RWF",
        "UGX",
        "UYI",
        "VND",
        "VUV",
        "XAF",
        "XOF",
        "XPF",
    }
)
_THREE_DECIMAL_CURRENCIES = frozenset(
    {
        "BHD",
        "IQD",
        "JOD",
        "KWD",
        "LYD",
        "OMR",
        "TND",
    }
)

# The single canonical persistence currency. Must equal the sovereign
# scope currency universe (verification_coverage.
# SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES); a CI gate asserts the
# equality so the two laws cannot silently diverge.
CANONICAL_PERSISTENCE_CURRENCY = "USD"

_FIXED_MONEY_EXPONENT_BY_CURRENCY = MappingProxyType(
    {
        "USD": 2,
        "EUR": 2,
        "GBP": 2,
        "CAD": 2,
        "AUD": 2,
        "NZD": 2,
        "CHF": 2,
        "SEK": 2,
        "NOK": 2,
        "DKK": 2,
        "SGD": 2,
        "HKD": 2,
        "MXN": 2,
        "BRL": 2,
        "INR": 2,
        "CNY": 2,
    }
)
_DEFAULT_MONEY_EXPONENT = 2


@dataclass(frozen=True)
class SovereignCommerce:
    provider: str
    provider_native_event_reference: str
    provider_native_commerce_reference: str
    normalized_commerce_reference_kind: str
    normalized_commerce_reference_value: str
    verified_amount_minor: int
    verified_amount_currency: str
    verified_amount_scale: int
    event_timestamp: datetime


def canonical_money_scale(currency: str | None) -> int:
    normalized = (currency or "").strip().upper()
    if not normalized:
        return _DEFAULT_MONEY_EXPONENT
    if normalized in _ZERO_DECIMAL_CURRENCIES:
        return 0
    if normalized in _THREE_DECIMAL_CURRENCIES:
        return 3
    return int(
        _FIXED_MONEY_EXPONENT_BY_CURRENCY.get(normalized, _DEFAULT_MONEY_EXPONENT)
    )


def decimal_to_minor_units(value: str | int | Decimal, *, scale: int = 2) -> int:
    quantizer = Decimal(10) ** (-scale)
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CommerceDerivationError(f"invalid monetary amount: {value!r}") from exc
    try:
        from decimal import ROUND_HALF_UP as _HALF_UP

        rounded = decimal_value.quantize(quantizer, rounding=_HALF_UP)
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        raise CommerceDerivationError(
            f"unquantizable monetary amount: {value!r}"
        ) from exc
    return int(rounded * (10**scale))


def _require_nonblank(value: Any, *, field: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise CommerceDerivationError(f"{field} is required")
    return text


def _parse_json_object(raw_body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommerceDerivationError(f"payload is not a JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise CommerceDerivationError("payload root must be a JSON object")
    return parsed


def _coerce_utc_instant(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        try:
            parsed = datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise CommerceDerivationError(
                f"{field} is not a valid epoch: {value!r}"
            ) from exc
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise CommerceDerivationError(
                f"{field} is not ISO-8601: {value!r}"
            ) from exc
    else:
        raise CommerceDerivationError(f"{field} is required")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _derive_stripe(payload: Mapping[str, Any]) -> SovereignCommerce:
    obj: Mapping[str, Any] = payload
    envelope_event_id: str | None = None
    data = payload.get("data")
    if isinstance(data, Mapping):
        inner = data.get("object")
        if isinstance(inner, Mapping) and inner.get("id"):
            obj = inner
            envelope_event_id = str(payload.get("id") or "").strip() or None
    commerce_id = _require_nonblank(obj.get("id"), field="stripe payment intent id")
    raw_amount = obj.get("amount")
    if raw_amount is None or isinstance(raw_amount, bool):
        raise CommerceDerivationError("stripe amount is required")
    try:
        amount_minor = int(raw_amount)
    except (TypeError, ValueError) as exc:
        raise CommerceDerivationError(
            f"stripe amount must be integer cents: {raw_amount!r}"
        ) from exc
    if amount_minor <= 0:
        raise CommerceDerivationError("stripe amount must be positive")
    currency = _require_nonblank(obj.get("currency"), field="stripe currency").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise CommerceDerivationError(
            f"stripe currency must be a 3-letter code: {currency!r}"
        )
    scale = canonical_money_scale(currency)
    # Timestamp: prefer the top-level event instant (payload.created) when in
    # envelope shape, matching the API v2 reconciliation-day law; fall back
    # to the object instant. Flat shape: obj IS the payload.
    created = payload.get("created")
    if created is None:
        created = obj.get("created")
    if created is None:
        raise CommerceDerivationError("stripe created timestamp is required")
    event_ts = _coerce_utc_instant(created, field="stripe created")
    event_ref = envelope_event_id or commerce_id
    return SovereignCommerce(
        provider="stripe",
        provider_native_event_reference=event_ref,
        provider_native_commerce_reference=commerce_id,
        normalized_commerce_reference_kind=NORMALIZED_KIND_BY_PROVIDER["stripe"],
        normalized_commerce_reference_value=commerce_id,
        verified_amount_minor=amount_minor,
        verified_amount_currency=currency,
        verified_amount_scale=scale,
        event_timestamp=event_ts,
    )


def _derive_shopify(payload: Mapping[str, Any]) -> SovereignCommerce:
    order_id = payload.get("id")
    commerce_ref = _require_nonblank(order_id, field="shopify order id")
    currency = _require_nonblank(
        payload.get("currency"), field="shopify currency"
    ).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise CommerceDerivationError(
            f"shopify currency must be a 3-letter code: {currency!r}"
        )
    scale = canonical_money_scale(currency)
    raw_total = payload.get("total_price")
    if raw_total is None:
        raise CommerceDerivationError("shopify total_price is required")
    amount_minor = decimal_to_minor_units(raw_total, scale=scale)
    if amount_minor <= 0:
        raise CommerceDerivationError("shopify total_price must be positive")
    created_at = payload.get("created_at")
    if created_at is None:
        raise CommerceDerivationError("shopify created_at is required")
    event_ts = _coerce_utc_instant(created_at, field="shopify created_at")
    return SovereignCommerce(
        provider="shopify",
        provider_native_event_reference=commerce_ref,
        provider_native_commerce_reference=commerce_ref,
        normalized_commerce_reference_kind=NORMALIZED_KIND_BY_PROVIDER["shopify"],
        normalized_commerce_reference_value=commerce_ref,
        verified_amount_minor=amount_minor,
        verified_amount_currency=currency,
        verified_amount_scale=scale,
        event_timestamp=event_ts,
    )


def _derive_paypal(payload: Mapping[str, Any]) -> SovereignCommerce:
    txn_id = _require_nonblank(payload.get("id"), field="paypal transaction id")
    amount = payload.get("amount")
    if not isinstance(amount, Mapping):
        raise CommerceDerivationError("paypal amount object is required")
    currency = _require_nonblank(
        amount.get("currency"), field="paypal currency"
    ).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise CommerceDerivationError(
            f"paypal currency must be a 3-letter code: {currency!r}"
        )
    scale = canonical_money_scale(currency)
    raw_total = amount.get("total")
    if raw_total is None:
        raise CommerceDerivationError("paypal amount.total is required")
    amount_minor = decimal_to_minor_units(raw_total, scale=scale)
    if amount_minor <= 0:
        raise CommerceDerivationError("paypal amount.total must be positive")
    create_time = payload.get("create_time")
    if create_time is None:
        raise CommerceDerivationError("paypal create_time is required")
    event_ts = _coerce_utc_instant(create_time, field="paypal create_time")
    return SovereignCommerce(
        provider="paypal",
        provider_native_event_reference=txn_id,
        provider_native_commerce_reference=txn_id,
        normalized_commerce_reference_kind=NORMALIZED_KIND_BY_PROVIDER["paypal"],
        normalized_commerce_reference_value=txn_id,
        verified_amount_minor=amount_minor,
        verified_amount_currency=currency,
        verified_amount_scale=scale,
        event_timestamp=event_ts,
    )


def _derive_woocommerce(payload: Mapping[str, Any]) -> SovereignCommerce:
    order_id = payload.get("id")
    commerce_ref = _require_nonblank(order_id, field="woocommerce order id")
    currency = _require_nonblank(
        payload.get("currency"), field="woocommerce currency"
    ).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise CommerceDerivationError(
            f"woocommerce currency must be a 3-letter code: {currency!r}"
        )
    scale = canonical_money_scale(currency)
    raw_total = payload.get("total")
    if raw_total is None:
        raise CommerceDerivationError("woocommerce total is required")
    amount_minor = decimal_to_minor_units(raw_total, scale=scale)
    if amount_minor <= 0:
        raise CommerceDerivationError("woocommerce total must be positive")
    stamp = payload.get("date_completed")
    if stamp is None:
        stamp = payload.get("date_created")
    if stamp is None:
        raise CommerceDerivationError(
            "woocommerce date_completed/date_created is required"
        )
    event_ts = _coerce_utc_instant(
        stamp, field="woocommerce date_completed/date_created"
    )
    return SovereignCommerce(
        provider="woocommerce",
        provider_native_event_reference=commerce_ref,
        provider_native_commerce_reference=commerce_ref,
        normalized_commerce_reference_kind=NORMALIZED_KIND_BY_PROVIDER["woocommerce"],
        normalized_commerce_reference_value=commerce_ref,
        verified_amount_minor=amount_minor,
        verified_amount_currency=currency,
        verified_amount_scale=scale,
        event_timestamp=event_ts,
    )


def derive_commerce(provider: str, raw_body: bytes) -> SovereignCommerce:
    """Sovereignly derive commerce meaning from verified provider bytes.

    Raises CommerceDerivationError when the bytes do not determine commerce
    meaning for the provider. Callers must fail closed (refuse persistence).
    """
    normalized = (provider or "").strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise CommerceDerivationError(f"unsupported provider: {provider!r}")
    if not isinstance(raw_body, (bytes, bytearray)) or not bytes(raw_body):
        raise CommerceDerivationError("raw provider body is required")
    payload = _parse_json_object(bytes(raw_body))
    if normalized == "stripe":
        return _derive_stripe(payload)
    if normalized == "shopify":
        return _derive_shopify(payload)
    if normalized == "paypal":
        return _derive_paypal(payload)
    return _derive_woocommerce(payload)


def _handoff_instant_epoch(handoff_timestamp: Any) -> int:
    instant = _coerce_utc_instant(handoff_timestamp, field="handoff event_timestamp")
    return int(instant.timestamp())


def binding_mismatches(
    *,
    provider: str,
    handoff: Mapping[str, Any],
    derived: SovereignCommerce,
) -> list[str]:
    """Compare relay-supplied handoff fields against sovereign derivation.

    Returns the list of mismatching dimensions (empty when bound). Every
    material financial field is compared: event identity, commerce
    reference, normalized kind/value, amount, currency, scale, timestamp
    instant. Comparison is case-sensitive except currency (upper) and
    instants (epoch seconds).
    """
    mismatches: list[str] = []
    normalized_provider = (provider or "").strip().lower()
    if normalized_provider != derived.provider:
        mismatches.append("provider")
    if (
        str(handoff.get("provider_native_event_reference") or "").strip()
        != derived.provider_native_event_reference
    ):
        mismatches.append("provider_native_event_reference")
    if (
        str(handoff.get("provider_native_commerce_reference") or "").strip()
        != derived.provider_native_commerce_reference
    ):
        mismatches.append("provider_native_commerce_reference")
    if (
        str(handoff.get("normalized_commerce_reference_kind") or "").strip()
        != derived.normalized_commerce_reference_kind
    ):
        mismatches.append("normalized_commerce_reference_kind")
    if (
        str(handoff.get("normalized_commerce_reference_value") or "").strip()
        != derived.normalized_commerce_reference_value
    ):
        mismatches.append("normalized_commerce_reference_value")
    try:
        handoff_amount = int(handoff.get("verified_amount_minor"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        handoff_amount = None
    if handoff_amount != derived.verified_amount_minor:
        mismatches.append("verified_amount_minor")
    if (
        str(handoff.get("verified_amount_currency") or "").strip().upper()
        != derived.verified_amount_currency
    ):
        mismatches.append("verified_amount_currency")
    try:
        handoff_scale = int(handoff.get("verified_amount_scale"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        handoff_scale = None
    if handoff_scale != derived.verified_amount_scale:
        mismatches.append("verified_amount_scale")
    try:
        handoff_epoch = _handoff_instant_epoch(handoff.get("event_timestamp"))
    except CommerceDerivationError:
        handoff_epoch = None
    if handoff_epoch != int(derived.event_timestamp.timestamp()):
        mismatches.append("event_timestamp")
    return mismatches

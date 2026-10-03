"""B2.6-P2 Corrective XVII semantic-closure unit gates (no database).

H-XVII-R8/R9/R10/R11/R15: the governed provider semantic contract binds
the production parser at the unit level -- exact money precision, explicit
shape refusals, governed timestamp precedence, regime identity, and
physical evidence/bytes correspondence on the finalization path. The
live database relations are proven by the XVII physics gate and the
negative-control battery; these tests pin the laws in-process so any
drift REDs at the cheapest tier.
"""

import base64
import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    REPO_ROOT
    / "contracts"
    / "reconciliation"
    / "b2.6"
    / "provider-semantic-contract.v1.json"
)

from app.webhooks.commerce_derivation import (  # noqa: E402
    CommerceDerivationError,
    SEMANTIC_CONTRACT_REGIME,
    decimal_to_minor_units,
    derive_commerce,
)


def test_xvii_regime_constant_matches_governed_contract() -> None:
    """Parser regime identity is the contract regime identity."""
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert SEMANTIC_CONTRACT_REGIME == contract["semantic_regime"]
    assert SEMANTIC_CONTRACT_REGIME == "xvii-sovereign-v1"


def test_xvii_money_exact_precision_vectors() -> None:
    """Exact amounts convert; excess precision and notation refuse."""
    assert decimal_to_minor_units("76.00", scale=2) == 7600
    assert decimal_to_minor_units("10.000", scale=3) == 10000
    assert decimal_to_minor_units("10.00", scale=2) == 1000
    assert decimal_to_minor_units(1000, scale=0) == 1000
    for bad in ("10.005", "0.009", "50.005", "19.999", "1000.5", "1e3", "1E2",
                "nan", "inf", "", True, None):
        with pytest.raises(CommerceDerivationError):
            decimal_to_minor_units(bad, scale=2 if bad != "1000.5" else 0)


def test_xvii_money_scale_zero_refuses_fraction() -> None:
    with pytest.raises(CommerceDerivationError):
        decimal_to_minor_units("1000.5", scale=0)


def test_xvii_paypal_resource_envelope_explicitly_refused() -> None:
    """A resource envelope is refused even with valid top-level fields."""
    raw = (
        b'{"id":"WH-2","amount":{"total":"5.00","currency":"USD"},'
        b'"create_time":"2024-01-15T10:00:00Z","resource":{"id":"PAY-9",'
        b'"amount":{"total":"9.00","currency":"USD"},'
        b'"create_time":"2024-01-15T10:00:00Z"}}'
    )
    with pytest.raises(CommerceDerivationError):
        derive_commerce("paypal", raw)


def test_xvii_stripe_ambiguous_wrappers_refused() -> None:
    """Neither flat-fallback nor cherry-pick on ambiguous wrappers."""
    without_inner = (
        b'{"id":"evt_amb","created":1700000000,"amount":500,'
        b'"currency":"usd","data":{"object":{"amount":500,"currency":"usd"}}}'
    )
    with pytest.raises(CommerceDerivationError):
        derive_commerce("stripe", without_inner)
    dual_money = (
        b'{"id":"evt_amb2","created":1700000060,"amount":9999,'
        b'"currency":"usd","data":{"object":{"id":"pi_amb","amount":100,'
        b'"currency":"usd","created":1700000000}}}'
    )
    with pytest.raises(CommerceDerivationError):
        derive_commerce("stripe", dual_money)


def test_xvii_timestamp_day_boundary_vectors() -> None:
    """Competing timestamps resolve per governed precedence law."""
    stripe = (
        b'{"id":"evt_day","created":1705276799,"data":{"object":{'
        b'"id":"pi_day","amount":2500,"currency":"usd",'
        b'"created":1705276800}}}'
    )
    produced = derive_commerce("stripe", stripe)
    assert int(produced.event_timestamp.timestamp()) == 1705276799
    woo = (
        b'{"id":2000,"total":"7.50","currency":"USD",'
        b'"date_completed":"2024-01-15T00:00:01+00:00",'
        b'"date_created":"2024-01-14T23:59:59+00:00"}'
    )
    produced = derive_commerce("woocommerce", woo)
    assert int(produced.event_timestamp.timestamp()) == 1705276801


def _lawful_stripe_finalization():
    raw = (
        b'{"id":"evt_9","created":1700000060,"data":{"object":{'
        b'"id":"pi_77","amount":100,"currency":"usd",'
        b'"created":1700000000}}}'
    )
    derived = derive_commerce("stripe", raw)
    body_sha = hashlib.sha256(raw).hexdigest()
    return {
        "provider": "stripe",
        "provider_native_event_reference": derived.provider_native_event_reference,
        "provider_native_commerce_reference": derived.provider_native_commerce_reference,
        "normalized_commerce_reference_kind": derived.normalized_commerce_reference_kind,
        "normalized_commerce_reference_value": derived.normalized_commerce_reference_value,
        "verified_amount_minor": derived.verified_amount_minor,
        "verified_amount_currency": derived.verified_amount_currency,
        "verified_amount_scale": derived.verified_amount_scale,
        "event_timestamp": derived.event_timestamp,
        "relay_envelope": {"raw_body_b64": base64.b64encode(raw).decode("ascii")},
        "auth_consequence": {"body_sha256": body_sha},
    }, raw


def test_xvii_direct_path_evidence_bytes_correspondence() -> None:
    """Detached digests fail closed before any DB work (H-XVII-R15)."""
    from app.ingestion.event_service import (  # noqa: PLC0415
        ValidationError,
        _assert_sovereign_finalization_binding,
    )

    finalization, _raw = _lawful_stripe_finalization()
    # Lawful shape passes the shared binding law.
    _assert_sovereign_finalization_binding(finalization, context="direct")
    # Detached digest (evidence claims B, bytes are A) refuses.
    tampered = dict(finalization)
    tampered["auth_consequence"] = {"body_sha256": "f" * 64}
    with pytest.raises(ValidationError) as exc:
        _assert_sovereign_finalization_binding(tampered, context="direct")
    assert "evidence_bytes_detached" in str(exc.value)

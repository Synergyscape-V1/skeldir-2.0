"""B2.6-P2 Corrective XVI independent-oracle production correspondence.

H-XVI-R2/R3: the provider-native oracle (scripts/ci/
validate_b26_p2_xvi_semantic_oracle.py) derives expected meaning without
any production semantic helper. THESE TESTS import both the oracle and
the production derivation and assert they agree on every golden vector
and every refusal vector. A shared production-parser mistake (wrong
native amount, wrong event ID, wrong timestamp source, wrong
object/reference source) makes the production side diverge from the
independent expectation and fails exactly that provider's test -- even
though API, root, and the old binding validator would all agree on the
wrong interpretation.

Per-provider test functions give H-XVI-R3 granularity: breaking one
provider's native parser must RED only that provider's gate.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ORACLE_PATH = (
    REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xvi_semantic_oracle.py"
)


def _load_oracle():
    spec = importlib.util.spec_from_file_location(
        "b26_p2_xvi_semantic_oracle", ORACLE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["b26_p2_xvi_semantic_oracle"] = module
    spec.loader.exec_module(module)
    return module


_ORACLE = _load_oracle()

from app.webhooks.commerce_derivation import (  # noqa: E402
    CommerceDerivationError,
    derive_commerce,
)


def _production_snapshot(provider: str, raw: bytes) -> dict:
    produced = derive_commerce(provider, raw)
    return {
        "provider": produced.provider,
        "provider_native_event_reference": produced.provider_native_event_reference,
        "provider_native_commerce_reference": produced.provider_native_commerce_reference,
        "normalized_commerce_reference_kind": produced.normalized_commerce_reference_kind,
        "normalized_commerce_reference_value": produced.normalized_commerce_reference_value,
        "verified_amount_minor": produced.verified_amount_minor,
        "verified_amount_currency": produced.verified_amount_currency,
        "verified_amount_scale": produced.verified_amount_scale,
        "event_timestamp_epoch": int(produced.event_timestamp.timestamp()),
    }


def _vectors(provider: str, kind: str):
    pool = (
        _ORACLE.GOLDEN_VECTORS if kind == "golden" else _ORACLE.REFUSAL_VECTORS
    )
    return [v for v in pool if v["provider"] == provider]


def test_xvi_oracle_file_is_pure() -> None:
    """The oracle must not share the production semantic helper."""
    assert _ORACLE.check_purity() == []


def _assert_provider_correspondence(provider: str) -> None:
    goldens = _vectors(provider, "golden")
    assert goldens, f"no golden vectors for {provider}"
    for vector in goldens:
        expected = _ORACLE.ORACLES[provider](vector["raw"])
        assert expected == vector["expected"], vector["id"]
        observed = _production_snapshot(provider, vector["raw"])
        assert observed == expected, (
            f"production diverges from independent oracle on {vector['id']}: "
            f"{ {k: (observed.get(k), expected.get(k)) for k in expected if observed.get(k) != expected.get(k)} }"
        )
    refusals = _vectors(provider, "refusal")
    assert refusals, f"no refusal vectors for {provider}"
    for vector in refusals:
        with pytest.raises(Exception):
            _ORACLE.ORACLES[provider](vector["raw"])
        with pytest.raises(CommerceDerivationError):
            derive_commerce(provider, vector["raw"])


def test_xvi_oracle_stripe_correspondence() -> None:
    _assert_provider_correspondence("stripe")


def test_xvi_oracle_shopify_correspondence() -> None:
    _assert_provider_correspondence("shopify")


def test_xvi_oracle_paypal_correspondence() -> None:
    _assert_provider_correspondence("paypal")


def test_xvi_oracle_woocommerce_correspondence() -> None:
    _assert_provider_correspondence("woocommerce")


def test_xvi_canonical_currency_matches_scope_universe() -> None:
    """Root USD-only refusal must track the sovereign scope universe."""
    from app.revenue_verification.verification_coverage import (  # noqa: PLC0415
        SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES,
    )
    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        CANONICAL_PERSISTENCE_CURRENCY,
    )

    assert set(SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES) == {
        CANONICAL_PERSISTENCE_CURRENCY
    }

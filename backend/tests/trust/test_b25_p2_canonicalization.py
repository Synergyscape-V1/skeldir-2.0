from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.trust.canonicalization import (
    CANONICALIZATION_PROFILE,
    CanonicalizationError,
    canonicalize_envelope_payload,
)
from app.trust.hash_identity import compute_envelope_payload_hash


ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "contracts/trust-api/examples"


def _fixture(name: str = "revenue_claim_valid_with_verified_revenue_minor.json") -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _reverse_object_order(value):
    if isinstance(value, dict):
        return {key: _reverse_object_order(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_object_order(item) for item in value]
    return value


def test_key_order_permutations_produce_identical_canonical_bytes_and_hash() -> None:
    payload = _fixture()
    permuted = _reverse_object_order(payload)

    assert CANONICALIZATION_PROFILE == "RFC8785-JCS-Skeldir-v1"
    assert canonicalize_envelope_payload(payload) == canonicalize_envelope_payload(permuted)
    assert compute_envelope_payload_hash(payload) == compute_envelope_payload_hash(permuted)


def test_explicit_null_is_preserved_in_canonical_bytes() -> None:
    payload = _fixture()

    canonical = canonicalize_envelope_payload(payload)

    assert b'"artifact_hash":null' in canonical
    assert b'"artifact_ref":null' in canonical
    assert b'"display_text":null' in canonical


def test_missing_required_field_fails_before_canonical_bytes() -> None:
    payload = _fixture()
    del payload["benchmark_metadata"]

    with pytest.raises(CanonicalizationError, match="schema_validation_failed"):
        canonicalize_envelope_payload(payload)


def test_unicode_preserves_nfc_and_nfd_as_distinct_bytes() -> None:
    nfc = _fixture()
    nfd = copy.deepcopy(nfc)
    nfc["untrusted_display_data"]["display_text"] = "café"
    nfd["untrusted_display_data"]["display_text"] = "cafe\u0301"

    assert canonicalize_envelope_payload(nfc) != canonicalize_envelope_payload(nfd)


def test_lone_surrogate_fails_before_canonical_bytes() -> None:
    payload = _fixture()
    payload["untrusted_display_data"]["display_text"] = "\ud800"

    with pytest.raises(CanonicalizationError, match="invalid_unicode_lone_surrogate"):
        canonicalize_envelope_payload(payload)


@pytest.mark.parametrize("bad_value", [1.25, float("nan"), float("inf"), float("-inf")])
def test_float_nan_and_infinity_fail_before_canonical_bytes(bad_value: float) -> None:
    payload = _fixture()
    payload["verified_revenue_minor"] = bad_value

    with pytest.raises(CanonicalizationError):
        canonicalize_envelope_payload(payload)


def test_json_safe_integer_bounds_are_enforced_before_bytes() -> None:
    payload = _fixture()
    payload["verified_revenue_minor"] = 9_007_199_254_740_992

    with pytest.raises(CanonicalizationError):
        canonicalize_envelope_payload(payload)


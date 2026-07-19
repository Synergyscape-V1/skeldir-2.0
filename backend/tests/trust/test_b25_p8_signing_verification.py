"""B2.5-P8 signing, verification, JWKS, and downgrade-defense tests."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.trust.hash_identity import (
    compute_artifact_hash,
    compute_semantic_truth_hash,
)
from app.trust.jwks import (
    TrustJWKSError,
    assert_jwks_public_only,
    build_jwks_response,
    registry_from_public_jwks,
)
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.signing import sign_trust_envelope
from app.trust.verification import verify_trust_envelope

from app.trust.canonicalization import (
    canonicalize_envelope_payload,
    canonicalize_signature_material,
)
from app.trust.signing import (
    encode_ed25519_signature,
    prepare_payload_for_signing,
    verify_ed25519_signature as _verify_ed25519_signature,
)
from unittest.mock import patch
import time as _time


ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "contracts/trust-api/examples"
SIGNING_TIME = datetime(2026, 6, 24, 10, 0, 2, tzinfo=timezone.utc)
VERIFY_TIME = datetime(2026, 6, 24, 10, 5, 0, tzinfo=timezone.utc)


def _private_key(label: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(label.encode()).digest())


def _key(
    kid: str,
    *,
    label: str,
    state: str = "active",
    valid_from: datetime = SIGNING_TIME - timedelta(days=1),
    valid_until: datetime | None = SIGNING_TIME + timedelta(days=30),
    retired_at: datetime | None = None,
) -> TrustSigningKey:
    private_key = _private_key(label)
    return TrustSigningKey(
        kid=kid,
        algorithm="ed25519",
        public_key=private_key.public_key(),
        private_key=private_key if state == "active" else None,
        state=state,  # type: ignore[arg-type]
        valid_from=valid_from,
        valid_until=valid_until,
        retired_at=retired_at if state == "verification_only" else None,
    )


def _registry() -> TrustKeyRegistry:
    return TrustKeyRegistry(
        (
            _key("kid:b25-p8-active-a", label="b25-p8-active-a"),
            _key(
                "kid:b25-p8-verify-old",
                label="b25-p8-verify-old",
                state="verification_only",
                retired_at=SIGNING_TIME,
            ),
        )
    )


def _fixture(name: str = "revenue_claim_valid_with_verified_revenue_minor.json") -> dict[str, Any]:
    payload = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    payload["created_at"] = "2026-06-24T10:00:02Z"
    payload["valid_until"] = "2026-06-25T10:00:02Z"
    return payload


def _signed_payload(name: str = "revenue_claim_valid_with_verified_revenue_minor.json") -> dict[str, Any]:
    return sign_trust_envelope(_fixture(name), key_registry=_registry())


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    target: Any = payload
    for part in parts[:-1]:
        if part.endswith("[0]"):
            target = target[part[:-3]][0]
        else:
            target = target[part]
    final = parts[-1]
    if final.endswith("[0]"):
        target[final[:-3]][0] = value
    else:
        target[final] = value


def _reverse_objects(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse_objects(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_objects(child) for child in value]
    return value


def test_ed25519_signer_verifies_with_public_jwks_only() -> None:
    registry = _registry()
    signed = sign_trust_envelope(_fixture(), key_registry=registry)
    public_registry = registry_from_public_jwks(build_jwks_response(registry))

    result = verify_trust_envelope(
        signed,
        key_registry=public_registry,
        at_time=VERIFY_TIME,
    )

    assert result.verification_status == "verified"
    assert signed["signature"].startswith("ed25519:")
    assert signed["signature_hash"].startswith("sha256:")
    assert signed["semantic_truth_hash"] == compute_semantic_truth_hash(signed)
    assert "p1-contract-placeholder-signature" not in signed["signature"]


def test_hmac_and_jwt_signature_confusion_fail_closed() -> None:
    signed = _signed_payload()
    hmac_fake = copy.deepcopy(signed)
    hmac_fake["signature"] = "hmac-sha256:" + hmac.new(
        b"secret",
        json.dumps(signed, sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()
    jwt_fake = copy.deepcopy(signed)
    jwt_fake["signature"] = jwt.encode(
        {"signature_hash": signed["signature_hash"]},
        "secret",
        algorithm="HS256",
    )

    for payload in (hmac_fake, jwt_fake):
        result = verify_trust_envelope(
            payload,
            key_registry=_registry().public_only(),
            at_time=VERIFY_TIME,
        )
        assert result.verification_status == "rejected"
        assert result.reason_code in {
            "signature_format_unsupported",
            "signature_invalid",
        }


@pytest.mark.parametrize(
    "field_path,value",
    [
        ("verified_revenue_minor", 99999),
        ("currency", "EUR"),
        ("deterministic_verification_status", "disputed"),
        ("confidence_metadata.confidence_status", "available"),
        ("benchmark_metadata.benchmark_status", "available"),
        ("policy_action_authority.policy_state", "approval_required"),
        ("provenance_chain[0].source_snapshot_hash", "sha256:" + "a" * 64),
        ("audit_ref", "urn:skeldir:audit:tampered"),
        ("audit_hash", "sha256:" + "b" * 64),
        ("subject_type", "attribution_result"),
        ("subject_ref", "urn:skeldir:revenue_claim:tampered"),
        ("tenant_id_hash", "sha256:" + "c" * 64),
        ("created_at", "2026-06-24T10:10:02Z"),
        ("valid_until", "2026-06-25T11:00:02Z"),
        ("schema_version", "trust-envelope-schema-v0"),
        ("canonicalization_version", "trust-canonical-json-v999"),
        ("semantic_truth_hash", "sha256:" + "d" * 64),
        ("signature_hash", "sha256:" + "e" * 64),
        ("signing_algorithm", "HS256"),
        ("signing_key_id", "kid:b25-p8-unknown"),
        ("fallback_applied", True),
        ("fallback_reason", "policy_denied"),
    ],
)
def test_load_bearing_tamper_fails_verification(field_path: str, value: Any) -> None:
    payload = _signed_payload()
    _set_path(payload, field_path, value)

    result = verify_trust_envelope(
        payload,
        key_registry=_registry().public_only(),
        at_time=VERIFY_TIME,
    )

    assert result.verification_status == "rejected"


def test_match_verdict_status_tamper_fails_verification() -> None:
    payload = _signed_payload("deterministic_only_verified.json")
    payload["match_verdict_status"] = "unmatched"

    result = verify_trust_envelope(
        payload,
        key_registry=_registry().public_only(),
        at_time=VERIFY_TIME,
    )

    assert result.verification_status == "rejected"


def test_artifact_ref_and_hash_are_signature_bound_when_present() -> None:
    fixture = _fixture("artifact_pruned_degraded.json")
    fixture["artifact_ref"] = "urn:skeldir:artifact:p8_fixture"
    fixture["artifact_hash"] = compute_artifact_hash(b"artifact-p8")
    signed = sign_trust_envelope(fixture, key_registry=_registry())

    for field, value in (
        ("artifact_ref", "urn:skeldir:artifact:tampered"),
        ("artifact_hash", compute_artifact_hash(b"artifact-tampered")),
    ):
        tampered = copy.deepcopy(signed)
        tampered[field] = value
        result = verify_trust_envelope(
            tampered,
            key_registry=_registry().public_only(),
            at_time=VERIFY_TIME,
        )
        assert result.verification_status == "rejected"


def test_key_rotation_preserves_semantic_truth_and_historical_verification() -> None:
    key_a = _key("kid:b25-p8-active-a", label="b25-p8-active-a")
    key_b = _key("kid:b25-p8-active-b", label="b25-p8-active-b")
    registry_a = TrustKeyRegistry((key_a,))
    registry_b = TrustKeyRegistry((key_b,))

    signed_a = sign_trust_envelope(_fixture(), key_registry=registry_a)
    signed_b = sign_trust_envelope(_fixture(), key_registry=registry_b)
    public_registry = TrustKeyRegistry(
        (
            key_a.public_only(),
            key_b.public_only(),
        )
    )

    assert signed_a["semantic_truth_hash"] == signed_b["semantic_truth_hash"]
    assert signed_a["signature_hash"] != signed_b["signature_hash"]
    assert signed_a["signing_key_id"] != signed_b["signing_key_id"]
    assert (
        verify_trust_envelope(signed_a, key_registry=public_registry, at_time=VERIFY_TIME)
        .verification_status
        == "verified"
    )
    assert (
        verify_trust_envelope(signed_b, key_registry=public_registry, at_time=VERIFY_TIME)
        .verification_status
        == "verified"
    )


def test_revoked_expired_unknown_and_temporal_fail_closed() -> None:
    signed = _signed_payload()
    revoked = TrustKeyRegistry(
        (_key("kid:b25-p8-active-a", label="b25-p8-active-a", state="revoked"),)
    )
    expired = TrustKeyRegistry(
        (_key("kid:b25-p8-active-a", label="b25-p8-active-a", state="expired"),)
    )

    for registry in (revoked, expired, TrustKeyRegistry((_key("kid:b25-p8-other", label="x"),))):
        assert (
            verify_trust_envelope(signed, key_registry=registry.public_only(), at_time=VERIFY_TIME)
            .verification_status
            == "rejected"
        )
    assert (
        verify_trust_envelope(
            signed,
            key_registry=_registry().public_only(),
            at_time=datetime(2026, 6, 26, tzinfo=timezone.utc),
        ).reason_code
        == "envelope_expired"
    )


def test_canonical_ordering_produces_stable_signature_material() -> None:
    registry = _registry()
    signed_a = sign_trust_envelope(_fixture(), key_registry=registry)
    signed_b = sign_trust_envelope(_reverse_objects(_fixture()), key_registry=registry)

    assert signed_a["signature_hash"] == signed_b["signature_hash"]
    assert signed_a["signature"] == signed_b["signature"]
    assert (
        verify_trust_envelope(signed_b, key_registry=registry.public_only(), at_time=VERIFY_TIME)
        .verification_status
        == "verified"
    )


def test_schema_canonicalization_and_algorithm_downgrades_fail_closed() -> None:
    signed = _signed_payload()
    cases = (
        ("schema_version", None),
        ("schema_version", "v0"),
        ("schema_version", "trust-envelope-schema-v999"),
        ("canonicalization_version", None),
        ("canonicalization_version", "trust-canonical-json-v999"),
        ("signing_algorithm", None),
        ("signing_algorithm", "HMAC"),
        ("signing_algorithm", "RS256"),
        ("signing_key_id", None),
        ("signature", None),
    )
    for field, value in cases:
        payload = copy.deepcopy(signed)
        if value is None:
            payload.pop(field, None)
        else:
            payload[field] = value
        result = verify_trust_envelope(
            payload,
            key_registry=_registry().public_only(),
            at_time=VERIFY_TIME,
        )
        assert result.verification_status == "rejected"


def test_jwks_public_only_and_private_material_negative_control() -> None:
    jwks = build_jwks_response(_registry())
    text = json.dumps(jwks, sort_keys=True)
    assert assert_jwks_public_only(jwks) == 2
    assert "private" not in text.lower()
    assert "seed" not in text.lower()
    assert "secret" not in text.lower()
    bad = copy.deepcopy(jwks)
    bad["keys"][0]["d"] = "private-scalar"
    with pytest.raises(TrustJWKSError):
        assert_jwks_public_only(bad)


def test_retired_key_cannot_forge_net_new_envelope() -> None:
    """A compromised retired key cannot verify envelopes created after retirement."""
    retired_key = _key(
        "kid:b25-p8-verify-old",
        label="b25-p8-verify-old",
        state="verification_only",
        retired_at=SIGNING_TIME,
    )
    active_key = _key("kid:b25-p8-active-a", label="b25-p8-active-a")
    payload = _fixture()
    payload["created_at"] = "2026-06-25T10:00:02Z"
    payload["valid_until"] = "2026-06-26T10:00:02Z"
    prepared = prepare_payload_for_signing(
        payload, signing_key_id="kid:b25-p8-verify-old", signing_algorithm="ed25519",
    )
    material = canonicalize_signature_material(prepared)
    private_key = _private_key("b25-p8-verify-old")
    prepared["signature"] = encode_ed25519_signature(private_key.sign(material))
    canonicalize_envelope_payload(prepared)
    verify_registry = TrustKeyRegistry((active_key.public_only(), retired_key.public_only()))
    result = verify_trust_envelope(
        prepared, key_registry=verify_registry, at_time=datetime(2026, 6, 25, 10, 5, 0, tzinfo=timezone.utc),
    )
    assert result.verification_status == "rejected"
    assert result.reason_code == "temporal_forgery_rejected:created_after_key_retirement"


def test_historical_envelope_from_retired_key_still_verifies() -> None:
    """Envelopes created at or before retirement remain verifiable."""
    retired_key = _key(
        "kid:b25-p8-verify-old", label="b25-p8-verify-old", state="verification_only", retired_at=SIGNING_TIME,
    )
    active_key = _key("kid:b25-p8-active-a", label="b25-p8-active-a")
    payload = _fixture()
    payload["created_at"] = "2026-06-24T10:00:02Z"
    payload["valid_until"] = "2026-06-25T10:00:02Z"
    prepared = prepare_payload_for_signing(
        payload, signing_key_id="kid:b25-p8-verify-old", signing_algorithm="ed25519",
    )
    material = canonicalize_signature_material(prepared)
    private_key = _private_key("b25-p8-verify-old")
    prepared["signature"] = encode_ed25519_signature(private_key.sign(material))
    canonicalize_envelope_payload(prepared)
    verify_registry = TrustKeyRegistry((active_key.public_only(), retired_key.public_only()))
    result = verify_trust_envelope(prepared, key_registry=verify_registry, at_time=VERIFY_TIME)
    assert result.verification_status == "verified"


def test_invalid_schema_short_circuits_before_crypto() -> None:
    """Invalid schema version is rejected without invoking Ed25519 verification."""
    signed = _signed_payload()
    bad = copy.deepcopy(signed)
    bad["schema_version"] = "trust-envelope-schema-v999"
    crypto_calls: list[int] = []
    original_verify = _verify_ed25519_signature

    def spy(public_key: Any, signature: str, material: bytes) -> None:
        crypto_calls.append(1)
        return original_verify(public_key, signature, material)

    with patch("app.trust.verification.verify_ed25519_signature", spy):
        start = _time.perf_counter()
        result = verify_trust_envelope(bad, key_registry=_registry().public_only(), at_time=VERIFY_TIME)
        elapsed_ms = (_time.perf_counter() - start) * 1000
    assert result.verification_status == "rejected"
    assert result.reason_code == "schema_version_unsupported:trust-envelope-schema-v999"
    assert len(crypto_calls) == 0
    assert elapsed_ms < 1000


def test_missing_schema_short_circuits_before_crypto() -> None:
    """Missing schema version is rejected without invoking Ed25519 verification."""
    signed = _signed_payload()
    bad = copy.deepcopy(signed)
    bad.pop("schema_version", None)
    crypto_calls: list[int] = []
    original_verify = _verify_ed25519_signature

    def spy(public_key: Any, signature: str, material: bytes) -> None:
        crypto_calls.append(1)
        return original_verify(public_key, signature, material)

    with patch("app.trust.verification.verify_ed25519_signature", spy):
        result = verify_trust_envelope(bad, key_registry=_registry().public_only(), at_time=VERIFY_TIME)
    assert result.verification_status == "rejected"
    assert len(crypto_calls) == 0

"""Directive XIII falsifiers for semantic signing and historical replay."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.inference_policy_registry import (
    CURRENT_POLICY_BUNDLE_HASH,
    HISTORICAL_P1_POLICY_BUNDLE_HASH,
    PolicyRegistryError,
    current_manifest,
    current_policy_tuple,
    resolve_policy_bundle,
    resolve_policy_provenance,
    semantic_digest,
)
from app.trust.jwks import build_jwks_response, registry_from_public_jwks
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.signing import TrustEnvelopeSigningError, sign_trust_envelope
from app.trust.verification import verify_trust_envelope


ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = (
    ROOT / "contracts/trust-api/examples/deterministic_with_bayesian_available.json"
)
NOW = datetime(2026, 6, 24, 10, 0, 2, tzinfo=timezone.utc)


class _CountingPrivateKey:
    def __init__(self) -> None:
        seed = hashlib.sha256(b"b25-p13-c13-boundary").digest()
        self.delegate = Ed25519PrivateKey.from_private_bytes(seed)
        self.sign_calls = 0

    def sign(self, material: bytes) -> bytes:
        self.sign_calls += 1
        return self.delegate.sign(material)


def _registry() -> tuple[TrustKeyRegistry, _CountingPrivateKey]:
    private = _CountingPrivateKey()
    key = TrustSigningKey(
        kid="kid:b25-p13-c13",
        algorithm="ed25519",
        public_key=private.delegate.public_key(),
        private_key=private,  # type: ignore[arg-type]
        state="active",
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=30),
        retired_at=None,
    )
    return TrustKeyRegistry((key,)), private


def _provenance(bundle_hash: str = CURRENT_POLICY_BUNDLE_HASH) -> dict[str, object]:
    return {
        "policy_bundle_hash": f"sha256:{bundle_hash}",
        **current_policy_tuple(),
        "confidence_policy_version": "b24-p10-confidence-policy-v1",
        "confidence_semantics_version": "b24-p10-confidence-semantics-v1",
        "authorized_chains": 4,
        "observed_chains": 4,
        "authorized_posterior_draws_total": 4000,
        "observed_posterior_draws_total": 4000,
    }


def _available_payload() -> dict[str, object]:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["confidence_metadata"]["inference_provenance"] = _provenance()
    return payload


def test_c13_current_semantics_sign_and_verify_with_public_jwks() -> None:
    registry, private = _registry()
    signed = sign_trust_envelope(_available_payload(), key_registry=registry)
    public = registry_from_public_jwks(build_jwks_response(registry))

    result = verify_trust_envelope(
        signed, key_registry=public, at_time=NOW + timedelta(minutes=5)
    )

    assert result.verification_status == "verified"
    assert private.sign_calls == 1
    assert signed["signature"].startswith("ed25519:")
    assert signed["signature_hash"].startswith("sha256:")


@pytest.mark.parametrize(
    "field,value",
    [
        ("policy_bundle_hash", "sha256:" + "f" * 64),
        ("inference_profile_version", "forged-inference-profile"),
        ("runtime_policy_version", "forged-runtime-policy"),
        ("sampling_policy_version", "forged-sampling-policy"),
        ("diagnostic_policy_version", "forged-diagnostic-policy"),
        ("confidence_policy_version", "forged-confidence-policy"),
        ("confidence_semantics_version", "forged-confidence-semantics"),
        ("authorized_chains", 1),
        ("observed_chains", 1),
        ("authorized_posterior_draws_total", 1),
        ("observed_posterior_draws_total", 1),
    ],
)
def test_c13_direct_signer_refuses_semantic_forgery_before_crypto(
    field: str, value: object
) -> None:
    payload = _available_payload()
    payload["confidence_metadata"]["inference_provenance"][field] = value
    original = deepcopy(payload)
    registry, private = _registry()

    with pytest.raises(TrustEnvelopeSigningError, match="policy_authority_refused"):
        sign_trust_envelope(payload, key_registry=registry)

    assert private.sign_calls == 0
    assert payload == original


def test_c13_reject_all_boundary_stops_the_only_trust_envelope_signer(
    monkeypatch,
) -> None:
    registry, private = _registry()

    def reject_all(_: object) -> None:
        raise PolicyRegistryError("c13_forced_reject_all")

    monkeypatch.setattr(
        "app.trust.signing.validate_envelope_policy_authority", reject_all
    )
    with pytest.raises(TrustEnvelopeSigningError, match="c13_forced_reject_all"):
        sign_trust_envelope(_available_payload(), key_registry=registry)
    assert private.sign_calls == 0


def test_c13_historical_p1_is_resolvable_but_not_reissuable() -> None:
    old_manifest = resolve_policy_bundle(HISTORICAL_P1_POLICY_BUNDLE_HASH)
    assert semantic_digest(old_manifest) == HISTORICAL_P1_POLICY_BUNDLE_HASH
    assert "trust_issuance_policy" not in old_manifest["components"]
    assert "trust_issuance_policy" in current_manifest()["components"]

    historical = _provenance(HISTORICAL_P1_POLICY_BUNDLE_HASH)
    assert (
        resolve_policy_provenance(historical)["components"]["confidence_policy"][
            "semantics"
        ]["width_ratio_medium_max"]
        == 0.25
    )
    payload = _available_payload()
    payload["confidence_metadata"]["inference_provenance"] = historical
    registry, private = _registry()
    with pytest.raises(TrustEnvelopeSigningError, match="not_issuable"):
        sign_trust_envelope(payload, key_registry=registry)
    assert private.sign_calls == 0


def test_c13_historical_registry_detects_rewrite_and_unknown_hash(monkeypatch) -> None:
    from app import inference_policy_registry as registry_module

    rewritten = deepcopy(resolve_policy_bundle(HISTORICAL_P1_POLICY_BUNDLE_HASH))
    rewritten["components"]["confidence_policy"]["semantics"][
        "width_ratio_medium_max"
    ] = 0.99
    monkeypatch.setitem(
        registry_module._POLICY_MANIFESTS_BY_HASH,
        HISTORICAL_P1_POLICY_BUNDLE_HASH,
        rewritten,
    )
    with pytest.raises(PolicyRegistryError, match="registry_integrity"):
        resolve_policy_bundle(HISTORICAL_P1_POLICY_BUNDLE_HASH)
    with pytest.raises(PolicyRegistryError, match="unknown_or_semantically_rewritten"):
        resolve_policy_bundle("0" * 64)


def test_c13_current_semantics_cannot_be_substituted_for_historical_identity(
    monkeypatch,
) -> None:
    from app import inference_policy_registry as registry_module

    monkeypatch.setitem(
        registry_module._POLICY_MANIFESTS_BY_HASH,
        HISTORICAL_P1_POLICY_BUNDLE_HASH,
        current_manifest(),
    )
    with pytest.raises(PolicyRegistryError, match="registry_integrity"):
        resolve_policy_bundle(HISTORICAL_P1_POLICY_BUNDLE_HASH)

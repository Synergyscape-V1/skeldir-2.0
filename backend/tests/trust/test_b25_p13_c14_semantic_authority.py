"""Directive XIV falsifiers for complete Trust issuance authority."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.confidence_projection.policy import (
    ConfidenceBucket,
    ConfidenceBucketReason,
    ConfidencePolicyDecision,
)
from app.confidence_projection.read_model import B24ConfidenceProjectionRead
from app.inference_policy_registry import (
    CURRENT_POLICY_BUNDLE_HASH,
    current_policy_tuple,
)
from app.trust.audit import (
    TrustAuditRequest,
    build_audit_record,
    build_unsigned_trust_envelope_with_audit,
)
from app.trust.builder import TrustEnvelopeBuildRequest
from app.trust.jwks import build_jwks_response, registry_from_public_jwks
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.semantic_authority import (
    TRUST_ENVELOPE_AUTHORITY_FIELDS,
    TrustSemanticAuthorityError,
    _authorize_audited_trust_envelope,
    validate_trust_semantic_authority,
)
from app.trust.signing import TrustEnvelopeSigningError, sign_trust_envelope
from app.trust.source_adapters import ConfidenceProjectionSource, MatchVerdictSource
from app.trust.verification import verify_trust_envelope


NOW = datetime(2026, 8, 28, 12, 0, 2, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[3]


class _CountingPrivateKey:
    def __init__(self) -> None:
        seed = hashlib.sha256(b"b25-p13-c14-semantic-authority").digest()
        self.delegate = Ed25519PrivateKey.from_private_bytes(seed)
        self.sign_calls = 0

    def sign(self, material: bytes) -> bytes:
        self.sign_calls += 1
        return self.delegate.sign(material)


def _registry() -> tuple[TrustKeyRegistry, _CountingPrivateKey]:
    private = _CountingPrivateKey()
    key = TrustSigningKey(
        kid="kid:b25-p13-c14",
        algorithm="ed25519",
        public_key=private.delegate.public_key(),
        private_key=private,  # type: ignore[arg-type]
        state="active",
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=30),
        retired_at=None,
    )
    return TrustKeyRegistry((key,)), private


def _match_source(tenant_id: UUID, verdict_id: UUID) -> MatchVerdictSource:
    observed = NOW - timedelta(seconds=2)
    return MatchVerdictSource(
        id=verdict_id,
        tenant_id=tenant_id,
        webhook_ingress_identity_id=uuid4(),
        provider="shopify",
        canonical_commerce_reference="order-c14-4827500",
        provider_native_event_reference="evt-c14",
        provider_native_commerce_reference="order-c14",
        status="matched_confirmed",
        match_quality="high",
        canonical_net_verified_amount_minor=4_827_500,
        currency_code="USD",
        last_transition_at=observed,
        created_at=observed,
        updated_at=observed,
    )


def _confidence_source(
    tenant_id: UUID,
    fit_id: UUID,
    *,
    available: bool,
    reason: ConfidenceBucketReason,
) -> ConfidenceProjectionSource:
    policy = current_policy_tuple()
    artifact_missing = reason in {
        ConfidenceBucketReason.ARTIFACT_PRUNED,
        ConfidenceBucketReason.ARTIFACT_UNAVAILABLE,
    }
    return ConfidenceProjectionSource(
        projection=B24ConfidenceProjectionRead(
            tenant_id=tenant_id,
            fit_id=fit_id,
            model_type="bayesian_attribution_confidence",
            model_version="b24-c14-v1",
            source_window_start=NOW - timedelta(days=30),
            source_window_end=NOW - timedelta(seconds=2),
            source_snapshot_hash="a" * 64,
            fit_status="succeeded",
            data_completeness_status="complete",
            fallback_applied=not available,
            fallback_reason=None if available else reason.value,
            diagnostic_status="passed",
            diagnostic_failure_reason=None,
            artifact_ref="b24/c14/artifact",
            artifact_hash="b" * 64,
            artifact_lifecycle_status="pruned" if artifact_missing else "active",
            observed_at=NOW - timedelta(seconds=2),
            evidence_snapshot_at=NOW - timedelta(seconds=2),
            source_read_started_at=NOW - timedelta(seconds=2),
            source_read_completed_at=NOW - timedelta(seconds=1),
            deterministic_revenue_minor=4_827_500,
            deterministic_row_count=8,
            match_verdict_count=4,
            currency_count=1,
            confidence_classified_at=NOW - timedelta(seconds=1),
            confidence_evidence_snapshot_hash="a" * 64,
            snapshot_freshness="current",
            has_snapshot_lineage=True,
            has_later_dirty_evidence=False,
            has_newer_fit=False,
            decision=ConfidencePolicyDecision(
                confidence_available=available,
                confidence_bucket=(
                    ConfidenceBucket.HIGH if available else ConfidenceBucket.UNAVAILABLE
                ),
                confidence_bucket_reason=reason,
            ),
            inference_profile_version=policy["inference_profile_version"],
            runtime_policy_version=policy["runtime_policy_version"],
            sampling_policy_version=policy["sampling_policy_version"],
            diagnostic_policy_version=policy["diagnostic_policy_version"],
            policy_bundle_hash=CURRENT_POLICY_BUNDLE_HASH,
            authorized_chains=4,
            authorized_posterior_draws_total=4000,
            observed_chains=4,
            observed_posterior_draws_total=4000,
        )
    )


async def _authorized_result(monkeypatch, source):
    async def _persist(request: TrustAuditRequest, **_: object):
        return build_audit_record(request)

    monkeypatch.setattr(
        "app.trust.audit.record_trust_audit_event_durable",
        _persist,
    )
    tenant_id = source.tenant_id
    subject_type = (
        "confidence_projection"
        if isinstance(source, ConfidenceProjectionSource)
        else "match_verdict"
    )
    subject_ref = f"urn:skeldir:{subject_type}:{source.id}"
    return await build_unsigned_trust_envelope_with_audit(
        object(),  # source is already the exact prefetched authoritative snapshot
        TrustEnvelopeBuildRequest(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_ref=subject_ref,
            request_context={
                "audience_id": "b25-p13-c14",
                "created_at": NOW,
                "created_at_source": "request_issuance_context",
            },
        ),
        idempotency_key=f"c14:{source.id}",
        source=source,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["deterministic", "available", "degraded"])
async def test_c14_legitimate_authoritative_states_sign_and_publicly_verify(
    monkeypatch, state: str
) -> None:
    tenant_id = uuid4()
    if state == "deterministic":
        source = _match_source(tenant_id, uuid4())
    elif state == "available":
        source = _confidence_source(
            tenant_id,
            uuid4(),
            available=True,
            reason=ConfidenceBucketReason.NARROW_INTERVAL,
        )
    else:
        source = _confidence_source(
            tenant_id,
            uuid4(),
            available=False,
            reason=ConfidenceBucketReason.ARTIFACT_PRUNED,
        )
    result = await _authorized_result(monkeypatch, source)
    registry, private = _registry()

    signed = sign_trust_envelope(result.authorized_envelope, key_registry=registry)
    public = registry_from_public_jwks(build_jwks_response(registry))
    verified = verify_trust_envelope(
        signed,
        key_registry=public,
        at_time=NOW + timedelta(minutes=5),
    )

    assert verified.verification_status == "verified"
    assert private.sign_calls == 1


@pytest.mark.asyncio
async def test_c14_raw_or_post_validation_mutation_cannot_reach_crypto(
    monkeypatch,
) -> None:
    result = await _authorized_result(
        monkeypatch,
        _match_source(uuid4(), uuid4()),
    )
    assert result.authorized_envelope is not None
    exposed = result.authorized_envelope.external_payload_copy()
    exposed["tenant_id_hash"] = "sha256:" + ("f" * 64)
    registry, private = _registry()

    with pytest.raises(TrustEnvelopeSigningError, match="issuance_capability_required"):
        sign_trust_envelope(exposed, key_registry=registry)  # type: ignore[arg-type]
    assert private.sign_calls == 0

    # Even deliberate Python-level corruption of the frozen object is detected
    # by its content address before the private key is selected.
    corrupted_snapshot = bytearray(result.authorized_envelope._payload_snapshot)
    tenant_hash_start = corrupted_snapshot.index(b'"tenant_id_hash":"sha256:')
    first_hex = tenant_hash_start + len(b'"tenant_id_hash":"sha256:')
    corrupted_snapshot[first_hex] = (
        ord("0") if corrupted_snapshot[first_hex] != ord("0") else ord("1")
    )
    object.__setattr__(
        result.authorized_envelope,
        "_payload_snapshot",
        bytes(corrupted_snapshot),
    )
    with pytest.raises(TrustEnvelopeSigningError, match="content_mismatch"):
        sign_trust_envelope(result.authorized_envelope, key_registry=registry)
    assert private.sign_calls == 0


def _mutate_path(payload: dict[str, object], path: str, value: object) -> None:
    target: object = payload
    parts = path.split(".")
    for part in parts[:-1]:
        if part.startswith("provenance_chain["):
            index = int(part.removeprefix("provenance_chain[").removesuffix("]"))
            target = target["provenance_chain"][index]  # type: ignore[index]
        else:
            target = target[part]  # type: ignore[index]
    target[parts[-1]] = value  # type: ignore[index]


@pytest.mark.asyncio
async def test_c14_false_financial_semantics_refuse_authority(
    monkeypatch,
) -> None:
    result = await _authorized_result(
        monkeypatch,
        _match_source(uuid4(), uuid4()),
    )
    assert result.unsigned_payload is not None
    tampered = deepcopy(result.unsigned_payload)
    _mutate_path(
        tampered,
        "provenance_chain[10].source_ref_hash",
        "sha256:" + ("9" * 64),
    )
    with pytest.raises(TrustSemanticAuthorityError):
        _authorize_audited_trust_envelope(
            build_result=result.build_result,
            audit_record=result.audit_record,
            audited_payload=tampered,
            observed_at=NOW,
        )


@pytest.mark.asyncio
async def test_c14_foreign_tenant_and_subject_substitution_refuse_authority(
    monkeypatch,
) -> None:
    result = await _authorized_result(
        monkeypatch,
        _match_source(uuid4(), uuid4()),
    )
    assert result.unsigned_payload is not None
    mutations = (
        ("tenant_id_hash", "sha256:" + ("8" * 64)),
        ("subject_ref", f"urn:skeldir:match_verdict:{uuid4()}"),
    )
    for path, value in mutations:
        tampered = deepcopy(result.unsigned_payload)
        _mutate_path(tampered, path, value)
        with pytest.raises(TrustSemanticAuthorityError):
            _authorize_audited_trust_envelope(
                build_result=result.build_result,
                audit_record=result.audit_record,
                audited_payload=tampered,
                observed_at=NOW,
            )


@pytest.mark.asyncio
async def test_c14_source_snapshot_and_evidence_window_substitution_refuse_authority(
    monkeypatch,
) -> None:
    result = await _authorized_result(
        monkeypatch,
        _match_source(uuid4(), uuid4()),
    )
    assert result.unsigned_payload is not None
    mutations = (
        ("truth_authority.source_snapshot_hash", "sha256:" + ("7" * 64)),
        ("evidence_temporal_boundary.evidence_snapshot_hash", "sha256:" + ("6" * 64)),
        ("evidence_temporal_boundary.source_read_completed_at", "2025-01-01T00:00:00Z"),
    )
    for path, value in mutations:
        tampered = deepcopy(result.unsigned_payload)
        _mutate_path(tampered, path, value)
        with pytest.raises(TrustSemanticAuthorityError):
            _authorize_audited_trust_envelope(
                build_result=result.build_result,
                audit_record=result.audit_record,
                audited_payload=tampered,
                observed_at=NOW,
            )


@pytest.mark.asyncio
async def test_c14_confidence_label_cannot_select_a_weaker_authority_contract(
    monkeypatch,
) -> None:
    result = await _authorized_result(
        monkeypatch,
        _confidence_source(
            uuid4(),
            uuid4(),
            available=True,
            reason=ConfidenceBucketReason.NARROW_INTERVAL,
        ),
    )
    assert result.unsigned_payload is not None
    tampered = deepcopy(result.unsigned_payload)
    metadata = tampered["confidence_metadata"]
    metadata["confidence_status"] = "degraded"
    metadata["inference_provenance"] = None

    with pytest.raises(TrustSemanticAuthorityError):
        _authorize_audited_trust_envelope(
            build_result=result.build_result,
            audit_record=result.audit_record,
            audited_payload=tampered,
            observed_at=NOW,
        )


@pytest.mark.asyncio
async def test_c14_confidence_state_machine_rejects_impossible_combinations(
    monkeypatch,
) -> None:
    available = await _authorized_result(
        monkeypatch,
        _confidence_source(
            uuid4(),
            uuid4(),
            available=True,
            reason=ConfidenceBucketReason.NARROW_INTERVAL,
        ),
    )
    deterministic = await _authorized_result(
        monkeypatch,
        _match_source(uuid4(), uuid4()),
    )
    assert available.unsigned_payload is not None
    assert deterministic.unsigned_payload is not None

    impossible: list[tuple[dict[str, object], tuple[str, object]]] = []
    for path, value in (
        ("confidence_metadata.inference_provenance", None),
        ("confidence_metadata.confidence_status", "degraded"),
        ("confidence_metadata.confidence_authority", "deterministic_only"),
        ("artifact_ref", None),
        ("confidence_metadata.unavailable_reason", "not_applicable"),
    ):
        payload = deepcopy(available.unsigned_payload)
        impossible.append((payload, (path, value)))
    deterministic_bayesian = deepcopy(deterministic.unsigned_payload)
    impossible.append(
        (
            deterministic_bayesian,
            ("confidence_metadata.bayesian_model_type", "pymc_marketing_mmm"),
        )
    )

    for payload, (path, value) in impossible:
        _mutate_path(payload, path, value)
        with pytest.raises(TrustSemanticAuthorityError):
            validate_trust_semantic_authority(
                payload,
                build_result=(
                    deterministic.build_result
                    if payload is deterministic_bayesian
                    else available.build_result
                ),
            )


@pytest.mark.asyncio
async def test_c14_xiii_policy_dimensions_remain_authoritative(monkeypatch) -> None:
    result = await _authorized_result(
        monkeypatch,
        _confidence_source(
            uuid4(),
            uuid4(),
            available=True,
            reason=ConfidenceBucketReason.NARROW_INTERVAL,
        ),
    )
    assert result.unsigned_payload is not None
    payload = deepcopy(result.unsigned_payload)
    provenance = payload["confidence_metadata"]["inference_provenance"]
    provenance["runtime_policy_version"] = "caller-forged-runtime-policy"

    with pytest.raises(TrustSemanticAuthorityError, match="policy_authority_invalid"):
        validate_trust_semantic_authority(payload, build_result=result.build_result)


@pytest.mark.asyncio
async def test_c14_builder_witness_cannot_be_reused_for_another_claim(
    monkeypatch,
) -> None:
    first = await _authorized_result(monkeypatch, _match_source(uuid4(), uuid4()))
    second = await _authorized_result(monkeypatch, _match_source(uuid4(), uuid4()))
    assert second.unsigned_payload is not None
    forged_result = replace(
        first.build_result,
        unsigned_payload=deepcopy(second.build_result.unsigned_payload),
    )

    with pytest.raises(TrustSemanticAuthorityError, match="builder_authority_invalid"):
        _authorize_audited_trust_envelope(
            build_result=forged_result,
            audit_record=second.audit_record,
            audited_payload=second.unsigned_payload,
            observed_at=NOW,
        )


def test_c14_schema_and_governance_matrix_have_closed_world_field_coverage() -> None:
    schema = yaml.safe_load(
        (ROOT / "contracts/trust-api/trust-envelope.v2.yaml").read_text(
            encoding="utf-8"
        )
    )
    matrix = json.loads(
        (
            ROOT / "contracts-internal/governance/"
            "b25_p13_c14_trust_semantic_authority.v1.json"
        ).read_text(encoding="utf-8")
    )
    schema_fields = set(schema["properties"])
    matrix_fields = {row["field"] for row in matrix["fields"]}

    assert schema_fields == TRUST_ENVELOPE_AUTHORITY_FIELDS == matrix_fields
    assert len(matrix_fields) == 41
    assert len(matrix["compound_claims"]) == 5


@pytest.mark.asyncio
async def test_c14_new_signed_field_without_authority_declaration_fails_closed(
    monkeypatch,
) -> None:
    result = await _authorized_result(
        monkeypatch,
        _match_source(uuid4(), uuid4()),
    )
    assert result.unsigned_payload is not None
    expanded = deepcopy(result.unsigned_payload)
    expanded["future_consequence_bearing_claim"] = "undeclared-authority"

    with pytest.raises(
        TrustSemanticAuthorityError, match="undeclared_signed_semantics"
    ):
        validate_trust_semantic_authority(expanded, build_result=result.build_result)

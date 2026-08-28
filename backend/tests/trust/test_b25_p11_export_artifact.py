"""B2.5-P11 signed export artifact identity and tamper proofs."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import trust_export
from app.trust.canonicalization import (
    canonicalize_envelope_payload,
    canonicalize_signature_material,
)
from app.trust.export_artifact import (
    ACTIVE_EXPORT_ARTIFACT_PROTOCOL,
    EXPORT_ARTIFACT_PROTOCOL_V1,
    EXPORT_ARTIFACT_PROTOCOL_V2,
    EXPORT_ARTIFACT_PROTOCOLS,
    EXPORT_ARTIFACT_SIGNING_DOMAIN,
    ExportArtifactError,
    build_export_artifact,
    export_artifact_signature_material,
    sign_export_artifact,
    verify_export_artifact,
)
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.hash_identity import compute_detached_signature_hash
from app.trust.machine_auth import MachineCallerContext
from app.trust.machine_identity import AgentScope
from app.trust.refusal import tenant_hash
from app.trust.signing import (
    TrustEnvelopeSigningError,
    encode_ed25519_signature,
    prepare_payload_for_signing,
    verify_ed25519_signature,
)
from app.trust.source_adapters import MatchVerdictSource


ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "contracts/trust-api/examples"


def _utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _registry() -> TrustKeyRegistry:
    private = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p11-artifact-test-key").digest()
    )
    return TrustKeyRegistry(
        (
            TrustSigningKey(
                kid="kid:b25-p11-artifact-test",
                algorithm="ed25519",
                public_key=private.public_key(),
                private_key=private,
                state="active",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )


def _cryptographically_sign_fixture(
    payload: dict[str, object], registry: TrustKeyRegistry
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    payload["created_at"] = _utc(now)
    payload["valid_until"] = _utc(now + timedelta(days=1))
    key = registry.active_signing_key()
    prepared = prepare_payload_for_signing(
        payload,
        signing_key_id=key.kid,
        signing_algorithm=key.algorithm,
    )
    assert key.private_key is not None
    material = canonicalize_signature_material(prepared)
    prepared["signature"] = encode_ed25519_signature(key.private_key.sign(material))
    canonicalize_envelope_payload(prepared)
    return prepared


def _signed_envelope(registry: TrustKeyRegistry) -> dict[str, object]:
    payload = json.loads(
        (EXAMPLES / "deterministic_only_verified.json").read_text(encoding="utf-8")
    )
    return _cryptographically_sign_fixture(payload, registry)


def _signed_artifact(
    registry: TrustKeyRegistry,
    *,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    envelope = _signed_envelope(registry)
    unsigned = build_export_artifact(
        envelopes=[envelope],
        tenant_id_hash=str(envelope["tenant_id_hash"]),
        generated_at=generated_at or datetime.now(timezone.utc),
    )
    return sign_export_artifact(unsigned, key_registry=registry)


def _historical_v1_artifact(
    registry: TrustKeyRegistry,
    *,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Construct a genuine pre-second-corrective (protocol v1) signed artifact.

    Built through the same production framing functions that originally produced
    such artifacts, so this is a real historical artifact rather than a
    hand-assembled approximation of one.
    """
    envelope = _signed_envelope(registry)
    unsigned = build_export_artifact(
        envelopes=[envelope],
        tenant_id_hash=str(envelope["tenant_id_hash"]),
        generated_at=generated_at or datetime.now(timezone.utc),
        protocol=EXPORT_ARTIFACT_PROTOCOL_V1,
    )
    return sign_export_artifact(
        unsigned, key_registry=registry, allow_historical_protocol=True
    )


def test_protocol_registry_maps_each_version_tuple_to_exactly_one_algorithm() -> None:
    """Gate P11-C3-D: version identity must be a function, not an ambiguity."""
    tuples = list(EXPORT_ARTIFACT_PROTOCOLS)
    assert len(tuples) == len(set(tuples)), "duplicate protocol version tuple"

    # The two governed protocols must be genuinely different algorithms, not
    # aliases; otherwise the separation is cosmetic.
    v1 = EXPORT_ARTIFACT_PROTOCOL_V1
    v2 = EXPORT_ARTIFACT_PROTOCOL_V2
    assert v1.schema_version != v2.schema_version
    assert v1.canonicalization_version != v2.canonicalization_version
    assert v1.signing_domain != v2.signing_domain
    assert v1.identity_bytes is not v2.identity_bytes
    assert v1.signature_material is not v2.signature_material

    # Only the active protocol may be issued.
    assert v2.issuable is True
    assert v1.issuable is False
    assert ACTIVE_EXPORT_ARTIFACT_PROTOCOL is v2


def test_historical_v1_artifact_verifies_through_its_own_protocol() -> None:
    """Gate P11-C3-E: historical artifacts verify, not silently reinterpreted."""
    registry = _registry()
    historical = _historical_v1_artifact(registry)

    assert historical["artifact_schema_version"] == "b25-p11-export-artifact-v1"
    assert historical["canonicalization_version"] == "b25-p11-artifact-framing-v1"

    result = verify_export_artifact(historical, key_registry=registry.public_only())
    assert result.verification_status == "verified", result.reason_code
    assert result.reason_code is None


def test_current_v2_artifact_verifies_and_is_distinct_from_v1() -> None:
    registry = _registry()
    generated_at = datetime.now(timezone.utc)
    current = _signed_artifact(registry, generated_at=generated_at)
    historical = _historical_v1_artifact(registry, generated_at=generated_at)

    assert current["artifact_schema_version"] == "b25-p11-export-artifact-v2"
    assert (
        verify_export_artifact(
            current, key_registry=registry.public_only()
        ).verification_status
        == "verified"
    )
    # Identical content under different protocols must not collide in identity.
    assert current["artifact_hash"] != historical["artifact_hash"]
    assert current["signature"] != historical["signature"]


@pytest.mark.parametrize(
    "schema_version,canonicalization_version",
    [
        # New bytes under an old marker.
        ("b25-p11-export-artifact-v1", "b25-p11-artifact-framing-v2"),
        # Old bytes under a new marker.
        ("b25-p11-export-artifact-v2", "b25-p11-artifact-framing-v1"),
        # Unsupported future protocol.
        ("b25-p11-export-artifact-v3", "b25-p11-artifact-framing-v3"),
    ],
)
def test_mismatched_or_unknown_protocol_tuples_report_protocol_failure(
    schema_version: str, canonicalization_version: str
) -> None:
    """An unsupported protocol must never masquerade as artifact corruption."""
    registry = _registry()
    artifact = copy.deepcopy(_signed_artifact(registry))
    artifact["artifact_schema_version"] = schema_version
    artifact["canonicalization_version"] = canonicalization_version

    result = verify_export_artifact(artifact, key_registry=registry.public_only())
    assert result.verification_status == "rejected"
    assert result.reason_code is not None
    assert result.reason_code.startswith("artifact_protocol_version_unsupported"), (
        "unsupported protocol tuples must be distinguishable from ordinary "
        f"artifact corruption, got {result.reason_code!r}"
    )
    assert "artifact_hash_mismatch" not in result.reason_code


def test_historical_protocol_cannot_be_issued_by_production_paths() -> None:
    """v1 remains verifiable but must be un-issuable without the test-only flag."""
    registry = _registry()
    envelope = _signed_envelope(registry)
    unsigned = build_export_artifact(
        envelopes=[envelope],
        tenant_id_hash=str(envelope["tenant_id_hash"]),
        generated_at=datetime.now(timezone.utc),
        protocol=EXPORT_ARTIFACT_PROTOCOL_V1,
    )
    with pytest.raises(ExportArtifactError) as excinfo:
        sign_export_artifact(unsigned, key_registry=registry)
    assert "artifact_protocol_not_issuable" in str(excinfo.value)


def test_historical_v1_artifact_rejects_tamper_and_wrong_domain() -> None:
    """Historical verification must be real verification, not a bypass."""
    registry = _registry()

    tampered = copy.deepcopy(_historical_v1_artifact(registry))
    tampered["generated_at"] = _utc(datetime.now(timezone.utc) + timedelta(hours=1))
    tampered_result = verify_export_artifact(
        tampered, key_registry=registry.public_only()
    )
    assert tampered_result.verification_status == "rejected"
    assert tampered_result.reason_code == "artifact_hash_mismatch"

    wrong_domain = copy.deepcopy(_historical_v1_artifact(registry))
    wrong_domain["artifact_signing_domain"] = (
        EXPORT_ARTIFACT_PROTOCOL_V2.signing_domain_label
    )
    domain_result = verify_export_artifact(
        wrong_domain, key_registry=registry.public_only()
    )
    assert domain_result.verification_status == "rejected"
    assert domain_result.reason_code == "artifact_signing_domain_mismatch"

    signature_tampered = copy.deepcopy(_historical_v1_artifact(registry))
    signature_tampered["signature"] = _signed_artifact(registry)["signature"]
    signature_result = verify_export_artifact(
        signature_tampered, key_registry=registry.public_only()
    )
    assert signature_result.verification_status == "rejected"


def test_artifact_embeds_full_signed_lineage_and_verifies_with_public_key_only() -> (
    None
):
    registry = _registry()
    artifact = _signed_artifact(registry)
    assert artifact["artifact_hash"].startswith("sha256:")
    assert artifact["signature_hash"].startswith("sha256:")
    assert artifact["signature_hash"] != artifact["artifact_hash"]
    assert artifact["signature_hash"] == compute_detached_signature_hash(
        export_artifact_signature_material(
            str(artifact["artifact_hash"]),
            signing_key_id=str(artifact["signing_key_id"]),
            signing_algorithm=str(artifact["signing_algorithm"]),
        )
    )
    assert artifact["signature"].startswith("ed25519:")
    assert artifact["envelopes"][0]["signature"].startswith("ed25519:")
    assert artifact["envelopes"][0]["provenance_chain"]
    result = verify_export_artifact(artifact, key_registry=registry.public_only())
    assert result.verification_status == "verified", result.reason_code


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("artifact_schema_version", "b25-p11-export-artifact-v0"),
        ("canonicalization_version", "unknown-canonicalization"),
        ("artifact_signing_domain", "skeldir:trust-envelope:v1\\0"),
        ("generated_at", "2026-08-08T12:00:02Z"),
        ("tenant_id_hash", "sha256:" + "9" * 64),
        ("signing_key_id", "kid:b25-p11-mutated-key"),
        ("signing_algorithm", "rsa_pss_sha256"),
    ],
)
def test_each_top_level_authoritative_mutation_is_rejected(field, replacement) -> None:
    registry = _registry()
    artifact = _signed_artifact(registry)
    artifact[field] = replacement
    assert (
        verify_export_artifact(
            artifact, key_registry=registry.public_only()
        ).verification_status
        == "rejected"
    )


def test_embedded_authoritative_value_mutation_and_artifact_hash_mismatch_reject() -> (
    None
):
    registry = _registry()
    artifact = _signed_artifact(registry)
    artifact["envelopes"][0]["match_verdict_status"] = "unmatched"
    result = verify_export_artifact(artifact, key_registry=registry.public_only())
    assert result.verification_status == "rejected"

    artifact = _signed_artifact(registry)
    artifact["artifact_hash"] = "sha256:" + "0" * 64
    result = verify_export_artifact(artifact, key_registry=registry.public_only())
    assert result.verification_status == "rejected"
    assert result.reason_code == "artifact_hash_mismatch"

    artifact = _signed_artifact(registry)
    artifact["signature_hash"] = "sha256:" + "1" * 64
    result = verify_export_artifact(artifact, key_registry=registry.public_only())
    assert result.verification_status == "rejected"
    assert result.reason_code == "signature_hash_mismatch"


def test_wrong_domain_cross_verification_fails_in_both_directions() -> None:
    registry = _registry()
    artifact = _signed_artifact(registry)
    envelope = artifact["envelopes"][0]
    key = registry.public_only().verification_key(str(artifact["signing_key_id"]))

    with pytest.raises(TrustEnvelopeSigningError):
        verify_ed25519_signature(
            key.public_key,
            str(artifact["signature"]),
            canonicalize_signature_material(envelope),
        )
    with pytest.raises(TrustEnvelopeSigningError):
        verify_ed25519_signature(
            key.public_key,
            str(envelope["signature"]),
            export_artifact_signature_material(
                str(artifact["artifact_hash"]),
                signing_key_id=str(artifact["signing_key_id"]),
                signing_algorithm=str(artifact["signing_algorithm"]),
            ),
        )
    assert EXPORT_ARTIFACT_SIGNING_DOMAIN.endswith(b"\x00")


def test_semantic_hash_stable_while_issuance_changes_artifact_hash() -> None:
    registry = _registry()
    envelope = _signed_envelope(registry)
    first = sign_export_artifact(
        build_export_artifact(
            envelopes=[copy.deepcopy(envelope)],
            tenant_id_hash=str(envelope["tenant_id_hash"]),
            generated_at=datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc),
        ),
        key_registry=registry,
    )
    second = sign_export_artifact(
        build_export_artifact(
            envelopes=[copy.deepcopy(envelope)],
            tenant_id_hash=str(envelope["tenant_id_hash"]),
            generated_at=datetime(2026, 8, 8, 12, 1, tzinfo=timezone.utc),
        ),
        key_registry=registry,
    )
    assert (
        first["envelopes"][0]["semantic_truth_hash"]
        == second["envelopes"][0]["semantic_truth_hash"]
    )
    assert first["artifact_hash"] != second["artifact_hash"]


def test_key_rotation_preserves_artifact_identity_and_rebinds_signature() -> None:
    old_private = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p11-artifact-old-key").digest()
    )
    new_private = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p11-artifact-new-key").digest()
    )
    valid_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old_active = TrustSigningKey(
        kid="kid:b25-p11-artifact-old",
        algorithm="ed25519",
        public_key=old_private.public_key(),
        private_key=old_private,
        state="active",
        valid_from=valid_from,
    )
    old_registry = TrustKeyRegistry((old_active,))
    envelope = _signed_envelope(old_registry)
    unsigned = build_export_artifact(
        envelopes=[envelope],
        tenant_id_hash=str(envelope["tenant_id_hash"]),
        generated_at=datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc),
    )
    old_signed = sign_export_artifact(unsigned, key_registry=old_registry)

    rotated_registry = TrustKeyRegistry(
        (
            TrustSigningKey(
                kid=old_active.kid,
                algorithm=old_active.algorithm,
                public_key=old_active.public_key,
                private_key=None,
                state="verification_only",
                valid_from=valid_from,
                retired_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
            ),
            TrustSigningKey(
                kid="kid:b25-p11-artifact-new",
                algorithm="ed25519",
                public_key=new_private.public_key(),
                private_key=new_private,
                state="active",
                valid_from=valid_from,
            ),
        )
    )
    new_signed = sign_export_artifact(unsigned, key_registry=rotated_registry)

    assert old_signed["artifact_hash"] == new_signed["artifact_hash"]
    assert old_signed["signing_key_id"] != new_signed["signing_key_id"]
    assert old_signed["signature_hash"] != new_signed["signature_hash"]
    assert old_signed["signature"] != new_signed["signature"]
    public_registry = rotated_registry.public_only()
    assert (
        verify_export_artifact(
            old_signed, key_registry=public_registry
        ).verification_status
        == "verified"
    )
    assert (
        verify_export_artifact(
            new_signed, key_registry=public_registry
        ).verification_status
        == "verified"
    )


def test_artifact_identity_uses_p2_hash_authority_without_local_json_hashing() -> None:
    source = (ROOT / "backend/app/trust/export_artifact.py").read_text(encoding="utf-8")
    assert "compute_artifact_hash(" in source
    assert "hashlib" not in source
    assert "json.dumps" not in source


def _caller(tenant_id: UUID) -> MachineCallerContext:
    return MachineCallerContext(
        agent_client_id=uuid4(),
        tenant_id=tenant_id,
        audience="b25-p11-route-test",
        scopes=frozenset({AgentScope.EXPORT_CREATE_LIMITED}),
        nonce_value="nonce-0123456789abcdef",
        request_identity_hash="sha256:" + "4" * 64,
    )


def _source(tenant_id: UUID, verdict_id: UUID) -> MatchVerdictSource:
    now = datetime.now(timezone.utc)
    return MatchVerdictSource(
        id=verdict_id,
        tenant_id=tenant_id,
        webhook_ingress_identity_id=None,
        provider="stripe",
        canonical_commerce_reference=f"order-{verdict_id}",
        provider_native_event_reference=f"event-{verdict_id}",
        provider_native_commerce_reference=f"commerce-{verdict_id}",
        status="matched_confirmed",
        match_quality="high",
        canonical_net_verified_amount_minor=1250,
        currency_code="USD",
        last_transition_at=now,
        created_at=now,
        updated_at=now,
    )


def _unsigned_for_route(tenant_id: UUID, subject_ref: str) -> dict[str, object]:
    payload = json.loads(
        (EXAMPLES / "deterministic_only_verified.json").read_text(encoding="utf-8")
    )
    now = datetime.now(timezone.utc)
    hashed_tenant = tenant_hash(tenant_id)
    payload["tenant_id_hash"] = hashed_tenant
    payload["subject_ref"] = subject_ref
    payload["subject_ref_hash"] = "sha256:" + "c" * 64
    payload["subject_authority"]["subject_ref"] = subject_ref
    payload["subject_authority"]["subject_ref_hash"] = "sha256:" + "c" * 64
    payload["created_at"] = _utc(now)
    payload["valid_until"] = _utc(now + timedelta(days=1))
    return payload


def _headers(tenant_id: UUID, idempotency: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-machine-token-value",
        "X-Tenant-ID": str(tenant_id),
        "X-Trust-Nonce": f"nonce-{idempotency}-0123456789",
        "X-Correlation-ID": str(uuid4()),
        "X-Idempotency-Key": idempotency,
    }


@pytest.mark.asyncio
async def test_machine_route_pages_at_two_and_emits_verifiable_artifacts(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    caller = _caller(tenant_id)
    registry = _registry()
    verdict_ids = [uuid4(), uuid4(), uuid4()]
    refs = [f"urn:skeldir:match_verdict:{value}" for value in verdict_ids]
    sources = {value: _source(tenant_id, value) for value in verdict_ids}
    audit_modes: list[bool] = []
    row_limits: list[int] = []

    app = FastAPI()
    app.include_router(trust_export.router, prefix="/api")
    app.add_exception_handler(
        trust_export.TrustExportRequestBoundaryException,
        trust_export.trust_export_request_boundary_exception_handler,
    )

    async def fake_session():
        yield object()

    async def fake_caller() -> MachineCallerContext:
        return caller

    async def fake_registry() -> TrustKeyRegistry:
        return registry

    async def fake_query(session, *, tenant_id, subject_refs, row_limit, **kwargs):
        _ = session, tenant_id, kwargs
        row_limits.append(row_limit)
        return tuple(sources[UUID(value.rsplit(":", 1)[1])] for value in subject_refs)

    async def fake_build(session, request, **kwargs):
        _ = session
        audit_modes.append(bool(kwargs["access_log_only"]))
        return SimpleNamespace(
            authorized_envelope=_unsigned_for_route(
                request.tenant_id, request.subject_ref
            )
        )

    app.dependency_overrides[trust_export.get_machine_export_db_session] = fake_session
    app.dependency_overrides[trust_export.require_export_tenant_context] = fake_caller
    app.dependency_overrides[trust_export.get_runtime_signing_registry] = fake_registry
    monkeypatch.setattr(trust_export, "query_match_verdict_sources", fake_query)
    monkeypatch.setattr(
        trust_export,
        "build_unsigned_trust_envelope_with_audit",
        fake_build,
    )
    monkeypatch.setattr(
        trust_export,
        "sign_trust_envelope",
        lambda payload, *, key_registry: _cryptographically_sign_fixture(
            payload, key_registry
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/trust/v1/exports/match-verdicts",
            headers=_headers(tenant_id, "p11-page-1"),
            json={"subject_refs": refs},
        )
        second = await client.post(
            "/api/trust/v1/exports/match-verdicts",
            headers=_headers(tenant_id, "p11-page-2"),
            json={
                "subject_refs": refs,
                "continuation_token": first.headers["X-Trust-Continuation"],
            },
        )

    assert first.status_code == second.status_code == 200
    assert len(first.json()["envelopes"]) == 2
    assert len(second.json()["envelopes"]) == 1
    assert first.headers["X-Export-Remaining-Count"] == "1"
    assert second.headers["X-Export-Remaining-Count"] == "0"
    assert "X-Trust-Continuation" not in second.headers
    assert row_limits == [3, 3]
    assert audit_modes == [False, False, False]
    for response in (first, second):
        result = verify_export_artifact(
            response.json(),
            key_registry=registry.public_only(),
        )
        assert result.verification_status == "verified", result.reason_code
        assert str(tenant_id) not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"subject_refs": [f"urn:skeldir:match_verdict:{uuid4()}" for _ in range(51)]},
        {
            "subject_type": "attribution_result",
            "subject_refs": [f"urn:skeldir:match_verdict:{uuid4()}"],
        },
    ],
)
async def test_over_limit_and_reserved_subject_inputs_reject_before_db(payload) -> None:
    db_touches = 0
    app = FastAPI()
    app.include_router(trust_export.router, prefix="/api")

    async def touched_session():
        nonlocal db_touches
        db_touches += 1
        yield object()

    app.dependency_overrides[trust_export.get_machine_export_db_session] = (
        touched_session
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/trust/v1/exports/match-verdicts",
            headers=_headers(uuid4(), "p11-rejected"),
            json=payload,
        )
    assert response.status_code == 422
    assert db_touches == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ["missing", "non_exportable"])
async def test_atomic_preflight_rejects_full_mixed_set_before_any_p7_issuance(
    monkeypatch,
    failure_mode: str,
) -> None:
    tenant_id = uuid4()
    caller = _caller(tenant_id)
    registry = _registry()
    verdict_ids = [uuid4() for _ in range(50)]
    refs = [f"urn:skeldir:match_verdict:{value}" for value in verdict_ids]
    sources = [_source(tenant_id, value) for value in verdict_ids]
    if failure_mode == "missing":
        sources.pop(24)
    else:
        failed = sources[24]
        sources[24] = MatchVerdictSource(
            **{
                **failed.__dict__,
                "canonical_net_verified_amount_minor": None,
            }
        )
    build_calls = 0
    observed_limits: list[int] = []

    app = FastAPI()
    app.include_router(trust_export.router, prefix="/api")

    async def fake_session():
        yield object()

    async def fake_caller() -> MachineCallerContext:
        return caller

    async def fake_registry() -> TrustKeyRegistry:
        return registry

    async def fake_query(session, *, tenant_id, subject_refs, row_limit, **kwargs):
        _ = session, tenant_id, subject_refs, kwargs
        observed_limits.append(row_limit)
        return tuple(sources)

    async def forbidden_build(*args, **kwargs):
        nonlocal build_calls
        build_calls += 1
        raise AssertionError("P7 issuance reached before atomic preflight completed")

    app.dependency_overrides[trust_export.get_machine_export_db_session] = fake_session
    app.dependency_overrides[trust_export.require_export_tenant_context] = fake_caller
    app.dependency_overrides[trust_export.get_runtime_signing_registry] = fake_registry
    monkeypatch.setattr(trust_export, "query_match_verdict_sources", fake_query)
    monkeypatch.setattr(
        trust_export,
        "build_unsigned_trust_envelope_with_audit",
        forbidden_build,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/trust/v1/exports/match-verdicts",
            headers=_headers(tenant_id, f"p11-atomic-{failure_mode}"),
            json={"subject_refs": refs},
        )

    assert response.status_code == 422
    assert response.json()["status"] == "refused"
    assert "X-Trust-Continuation" not in response.headers
    assert observed_limits == [50]
    assert build_calls == 0

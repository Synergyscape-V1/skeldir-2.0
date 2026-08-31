"""B2.5-P7 tenant-scoped trust audit persistence substrate."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.trust.audit_hash import (
    audit_ref_from_identity,
    compute_audit_hash,
    idempotency_key_hash,
    request_identity_hash,
)
from app.trust.builder import (
    TrustEnvelopeBuildRequest,
    TrustEnvelopeBuildResult,
    build_unsigned_trust_envelope,
)
from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.hash_identity import (
    compute_envelope_payload_hash,
    compute_semantic_truth_hash,
    compute_signature_hash,
)
from app.trust.provenance import replace_audit_provenance_entries
from app.trust.reason_codes import ReasonCode
from app.trust.reason_truth_matrix import assert_reason_known
from app.trust.refusal import tagged_sha256, tenant_hash, utc_second
from app.trust.semantic_authority import (
    AuthorizedTrustEnvelope,
    _authorize_audited_trust_envelope,
)
from app.trust.issuance_session import trust_issuance_session_factory
from app.trust.key_registry import TrustKeyRegistry
from app.trust.runtime_keys import load_runtime_verification_registry
from app.trust.signer_session import trust_signer_session_factory
from app.trust.signing import decode_ed25519_signature
from app.trust.signing_consequence import (
    SignedTrustEnvelopeConsequence,
    SigningConsequenceError,
    redeem_signing_consequence,
)
from app.trust.signing_authorization import (
    DurableSigningAuthorization,
    DurableSigningAuthorizationMaterial,
    mint_durable_signing_authorization,
)
from app.trust.source_adapters import ConfidenceProjectionSource, MatchVerdictSource
from app.trust.verification import verify_trust_envelope


AuditEventType = Literal["issuance", "refusal", "scope_denial", "replay"]
AuditStatus = Literal["success", "refused", "degraded", "replayed"]
AuditTimestampSource = Literal["request_issuance_context", "persisted_original"]
AuditSessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
AuditCpuRunner = Callable[..., Awaitable[Any]]
AUDIT_TIMESTAMP_AUTHORITY_SOURCES: frozenset[str] = frozenset(
    {"request_issuance_context", "persisted_original"}
)

SAFE_REFUSAL_REASONS = {
    ReasonCode.SCOPE_DENIED.value,
    ReasonCode.TENANT_MISMATCH.value,
    ReasonCode.REPLAY_REJECTED.value,
    ReasonCode.SUBJECT_NOT_FOUND.value,
    ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE.value,
    ReasonCode.MONEY_SOURCE_NOT_AUTHORITATIVE.value,
    ReasonCode.PROVIDER_TEXT_QUARANTINED.value,
    ReasonCode.SCHEMA_VERSION_UNSUPPORTED.value,
    ReasonCode.CANONICALIZATION_VERSION_UNSUPPORTED.value,
    ReasonCode.SUBJECT_AUTHORITY_REJECTED.value,
    ReasonCode.MUTABLE_WORKFLOW_SUBJECT_REJECTED.value,
    ReasonCode.HUMAN_WORKFLOW_STATE_REJECTED.value,
    ReasonCode.MONEY_AMOUNT_EXCEEDS_JSON_SAFE_INTEGER.value,
    ReasonCode.VALIDATION_FAILED.value,
    ReasonCode.UNSUPPORTED_SUBJECT_TYPE.value,
    ReasonCode.RESPONSE_BUDGET_EXCEEDED.value,
    ReasonCode.TENANT_CONTEXT_MISSING.value,
}


class TrustAuditError(ValueError):
    """Raised when P7 audit material or persistence is unsafe."""


@dataclass(frozen=True)
class TrustAuditRequest:
    """Minimal, PII-free trust audit write request."""

    tenant_id: UUID
    event_type: AuditEventType
    status: AuditStatus
    idempotency_key: str
    subject_type: str
    subject_ref_hash: str | None
    tenant_id_hash: str
    policy_state: str
    reason_code: str | None
    created_at: datetime
    created_at_source: AuditTimestampSource
    semantic_truth_hash: str | None = None
    envelope_hash: str | None = None
    audience_id_hash: str | None = None
    evidence_refs_allowed: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.created_at, datetime):
            raise TrustAuditError("audit_created_at_required")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise TrustAuditError("audit_created_at_timezone_required")
        if self.created_at_source not in AUDIT_TIMESTAMP_AUTHORITY_SOURCES:
            raise TrustAuditError("audit_created_at_source_authority_required")


@dataclass(frozen=True)
class TrustAuditRecord:
    """Persisted or replayed audit identity."""

    audit_ref: str
    audit_hash: str
    idempotency_key_hash: str
    request_identity_hash: str
    event_type: str
    status: str
    replayed: bool

    def external_projection(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TrustEnvelopeAuditResult:
    """P7 wrapper result around the P5 builder."""

    build_result: TrustEnvelopeBuildResult
    audit_record: TrustAuditRecord
    unsigned_payload: dict[str, Any] | None
    authorized_envelope: AuthorizedTrustEnvelope | None
    refusal_payload: dict[str, Any] | None


def _reason_value(reason_code: str | ReasonCode | None) -> str | None:
    if reason_code is None or reason_code == "none":
        return None
    return assert_reason_known(reason_code).value


def _audit_material(request: TrustAuditRequest) -> dict[str, object]:
    reason = _reason_value(request.reason_code)
    if request.event_type in {"refusal", "scope_denial"}:
        if reason not in SAFE_REFUSAL_REASONS:
            raise TrustAuditError(f"unsafe_refusal_reason:{reason}")
        if request.evidence_refs_allowed:
            raise TrustAuditError("refusal_evidence_refs_must_be_suppressed")
    subject_ref_hash = (
        request.subject_ref_hash
        if request.evidence_refs_allowed
        and request.event_type not in {"refusal", "scope_denial"}
        else None
    )
    idempotency_hash = idempotency_key_hash(
        tenant_id_hash=request.tenant_id_hash,
        idempotency_key=request.idempotency_key,
    )
    identity_hash = request_identity_hash(
        tenant_id_hash=request.tenant_id_hash,
        subject_type=request.subject_type,
        subject_ref_hash=subject_ref_hash,
        audience_id_hash=request.audience_id_hash,
    )
    audit_ref = audit_ref_from_identity(
        event_type=request.event_type,
        idempotency_key_hash=idempotency_hash,
    )
    created_at = utc_second(request.created_at)
    return {
        "audit_ref": audit_ref,
        "tenant_id_hash": request.tenant_id_hash,
        "event_type": request.event_type,
        "status": request.status,
        "reason_code": reason or "none",
        "request_identity_hash": identity_hash,
        "idempotency_key_hash": idempotency_hash,
        "subject_type": request.subject_type,
        "subject_ref_hash": subject_ref_hash,
        "semantic_truth_hash": request.semantic_truth_hash,
        "policy_state": request.policy_state,
        "evidence_refs_allowed": request.evidence_refs_allowed,
        "created_at": created_at,
        "created_at_source": request.created_at_source,
    }


def build_audit_record(request: TrustAuditRequest) -> TrustAuditRecord:
    """Build deterministic audit ref/hash material without touching the DB."""
    material = _audit_material(request)
    return TrustAuditRecord(
        audit_ref=str(material["audit_ref"]),
        audit_hash=compute_audit_hash(material),
        idempotency_key_hash=str(material["idempotency_key_hash"]),
        request_identity_hash=str(material["request_identity_hash"]),
        event_type=request.event_type,
        status=request.status,
        replayed=False,
    )


async def _upsert_access_log(
    db_session: AsyncSession,
    *,
    request: TrustAuditRequest,
    record: TrustAuditRecord,
) -> TrustAuditRecord:
    result = await db_session.execute(
        text(
            """
            INSERT INTO public.trust_access_log (
                tenant_id,
                event_type,
                status,
                request_identity_hash,
                idempotency_key_hash,
                subject_type,
                subject_ref_hash,
                envelope_hash,
                semantic_truth_hash,
                policy_state,
                reason_code,
                audit_ref,
                audit_hash,
                evidence_refs_allowed,
                issuance_state,
                created_at,
                updated_at
            )
            VALUES (
                :tenant_id,
                :event_type,
                :status,
                :request_identity_hash,
                :idempotency_key_hash,
                :subject_type,
                :subject_ref_hash,
                :envelope_hash,
                :semantic_truth_hash,
                :policy_state,
                :reason_code,
                :audit_ref,
                :audit_hash,
                :evidence_refs_allowed,
                CASE WHEN :event_type = 'issuance'
                     THEN 'authorized' ELSE 'not_applicable' END,
                :created_at,
                :created_at
            )
            ON CONFLICT (tenant_id, event_type, idempotency_key_hash)
            DO UPDATE SET
                replay_count = public.trust_access_log.replay_count + 1,
                last_replayed_at = now(),
                updated_at = now()
            WHERE public.trust_access_log.audit_hash = EXCLUDED.audit_hash
            RETURNING
                audit_ref,
                audit_hash,
                idempotency_key_hash,
                request_identity_hash,
                event_type,
                status,
                (replay_count > 0) AS replayed
            """
        ),
        _params(request, record),
    )
    row = result.mappings().first()
    if row is None:
        raise TrustAuditError("idempotency_conflict")
    return TrustAuditRecord(
        audit_ref=str(row["audit_ref"]),
        audit_hash=str(row["audit_hash"]),
        idempotency_key_hash=str(row["idempotency_key_hash"]),
        request_identity_hash=str(row["request_identity_hash"]),
        event_type=str(row["event_type"]),
        status=str(row["status"]),
        replayed=bool(row["replayed"]),
    )


async def _insert_issuance_log(
    db_session: AsyncSession,
    *,
    request: TrustAuditRequest,
    record: TrustAuditRecord,
) -> None:
    if request.status != "success":
        return
    await db_session.execute(
        text(
            """
            INSERT INTO public.trust_envelope_issuance_log (
                tenant_id,
                access_audit_ref,
                idempotency_key_hash,
                subject_type,
                subject_ref_hash,
                envelope_hash,
                semantic_truth_hash,
                policy_state,
                audit_ref,
                audit_hash,
                status,
                created_at
            )
            VALUES (
                :tenant_id,
                :audit_ref,
                :idempotency_key_hash,
                :subject_type,
                :subject_ref_hash,
                :envelope_hash,
                :semantic_truth_hash,
                :policy_state,
                :audit_ref,
                :audit_hash,
                :status,
                :created_at
            )
            ON CONFLICT (tenant_id, idempotency_key_hash)
            DO NOTHING
            """
        ),
        _params(request, record),
    )


async def _insert_scope_denial_log(
    db_session: AsyncSession,
    *,
    request: TrustAuditRequest,
    record: TrustAuditRecord,
) -> None:
    if request.event_type != "scope_denial":
        return
    await db_session.execute(
        text(
            """
            INSERT INTO public.trust_scope_denial_events (
                tenant_id,
                request_identity_hash,
                idempotency_key_hash,
                subject_type,
                subject_ref_hash,
                status,
                reason_code,
                evidence_refs_leaked,
                audit_ref,
                audit_hash,
                created_at
            )
            VALUES (
                :tenant_id,
                :request_identity_hash,
                :idempotency_key_hash,
                :subject_type,
                NULL,
                :status,
                :reason_code,
                false,
                :audit_ref,
                :audit_hash,
                :created_at
            )
            ON CONFLICT (tenant_id, idempotency_key_hash)
            DO NOTHING
            """
        ),
        _params(request, record),
    )


async def _insert_replay_log(
    db_session: AsyncSession,
    *,
    request: TrustAuditRequest,
    record: TrustAuditRecord,
) -> None:
    if not record.replayed:
        return
    await db_session.execute(
        text(
            """
            INSERT INTO public.trust_replay_events (
                tenant_id,
                request_identity_hash,
                idempotency_key_hash,
                original_audit_ref,
                replay_status,
                audit_hash,
                created_at
            )
            VALUES (
                :tenant_id,
                :request_identity_hash,
                :idempotency_key_hash,
                :audit_ref,
                'idempotent_replay',
                :audit_hash,
                :created_at
            )
            ON CONFLICT (tenant_id, idempotency_key_hash, original_audit_ref)
            DO NOTHING
            """
        ),
        _params(request, record),
    )


def _params(
    request: TrustAuditRequest,
    record: TrustAuditRecord,
) -> dict[str, object]:
    subject_ref_hash = (
        request.subject_ref_hash
        if request.evidence_refs_allowed
        and request.event_type not in {"refusal", "scope_denial"}
        else None
    )
    return {
        "tenant_id": str(request.tenant_id),
        "event_type": request.event_type,
        "status": request.status,
        "request_identity_hash": record.request_identity_hash,
        "idempotency_key_hash": record.idempotency_key_hash,
        "subject_type": request.subject_type,
        "subject_ref_hash": subject_ref_hash,
        "envelope_hash": request.envelope_hash,
        "semantic_truth_hash": request.semantic_truth_hash,
        "policy_state": request.policy_state,
        "reason_code": _reason_value(request.reason_code),
        "audit_ref": record.audit_ref,
        "audit_hash": record.audit_hash,
        "evidence_refs_allowed": request.evidence_refs_allowed,
        "created_at": request.created_at.astimezone(timezone.utc).replace(
            microsecond=0
        ),
    }


async def record_trust_audit_event(
    db_session: AsyncSession,
    request: TrustAuditRequest,
    *,
    access_log_only: bool = False,
) -> TrustAuditRecord:
    """Persist an idempotent trust audit event and companion event row."""
    record = build_audit_record(request)
    persisted = await _upsert_access_log(db_session, request=request, record=record)
    if not access_log_only:
        await _insert_issuance_log(db_session, request=request, record=persisted)
        await _insert_scope_denial_log(db_session, request=request, record=persisted)
        await _insert_replay_log(db_session, request=request, record=persisted)
    return persisted


async def record_trust_audit_event_durable(
    request: TrustAuditRequest,
    *,
    audit_session_factory: AuditSessionFactory | None = None,
    access_log_only: bool = False,
) -> TrustAuditRecord:
    """Persist an audit event in an independent committed transaction."""
    if audit_session_factory is None:
        from app.db.session import AsyncSessionLocal

        audit_session_factory = AsyncSessionLocal

    async with audit_session_factory() as audit_session:
        begin = getattr(audit_session, "begin", None)
        if callable(begin):
            async with begin():
                await audit_session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(request.tenant_id)},
                )
                return await record_trust_audit_event(
                    audit_session,
                    request,
                    access_log_only=access_log_only,
                )

        await audit_session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(request.tenant_id)},
        )
        return await record_trust_audit_event(
            audit_session,
            request,
            access_log_only=access_log_only,
        )


async def _execute_durable_issuance_update(
    *,
    tenant_id: UUID,
    statement: Any,
    params: dict[str, Any],
    expected_rows: int,
    failure_reason: str,
    audit_session_factory: AuditSessionFactory | None,
) -> None:
    """Execute one tenant-scoped issuance transition and prove its cardinality.

    B2.5-P13 Corrective XVI (XVI-B). Consequence-bearing transitions run under
    the dedicated ``app_trust_issuer`` principal, never the ordinary runtime
    DSN. The database enforces the same separation independently, so passing an
    ordinary session here fails closed at the trigger rather than silently
    writing issuance history with ordinary authority.
    """
    if audit_session_factory is None:
        audit_session_factory = trust_issuance_session_factory()
    params = {**params, "tenant_id": str(tenant_id)}

    async def execute(audit_session: AsyncSession) -> None:
        await audit_session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        result = await audit_session.execute(statement, params)
        observed_rows = int(getattr(result, "rowcount", -1))
        if observed_rows != expected_rows:
            raise TrustAuditError(
                f"{failure_reason}:expected={expected_rows}:observed={observed_rows}"
            )

    async with audit_session_factory() as audit_session:
        begin = getattr(audit_session, "begin", None)
        if callable(begin):
            async with begin():
                await execute(audit_session)
                return
        await execute(audit_session)


def _issuance_crypto_evidence(
    signed_envelope: dict[str, Any],
) -> tuple[str, str, bytes]:
    """Extract the retained public cryptographic evidence for an issued row."""
    if not isinstance(signed_envelope, dict):
        raise TrustAuditError("issuance_completion_requires_signed_envelope")
    signing_key_id = signed_envelope.get("signing_key_id")
    signature_hash = signed_envelope.get("signature_hash")
    encoded_signature = signed_envelope.get("signature")
    if not isinstance(signing_key_id, str):
        raise TrustAuditError("issuance_completion_requires_signature_identity")
    if not isinstance(signature_hash, str):
        raise TrustAuditError("issuance_completion_requires_signature_identity")
    if not isinstance(encoded_signature, str):
        raise TrustAuditError("issuance_completion_requires_signature_identity")
    try:
        signature = decode_ed25519_signature(encoded_signature)
    except Exception as exc:
        raise TrustAuditError(
            "issuance_completion_requires_valid_signature_bytes"
        ) from exc
    if len(signature) != 64:
        raise TrustAuditError("issuance_completion_requires_valid_signature_bytes")
    return signing_key_id, signature_hash, signature


async def record_trust_issuance_attempt_started(
    *,
    tenant_id: UUID,
    audit_ref: str,
    audit_session_factory: AuditSessionFactory | None = None,
) -> UUID:
    """Durably create one append-only attempt before private-key use."""
    factory = audit_session_factory or trust_issuance_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            transitioned = (
                await audit_session.execute(
                    text(
                        """
                        UPDATE public.trust_access_log
                        SET issuance_state = 'signing',
                            issuance_attempted_at = now(),
                            issuance_outcome_unknown_at = NULL,
                            issuance_attempt_count = issuance_attempt_count + 1,
                            updated_at = now()
                        WHERE tenant_id = :tenant_id
                          AND audit_ref = :audit_ref
                          AND event_type = 'issuance'
                          AND issuance_state IN (
                              'authorized', 'failed', 'signature_outcome_unknown'
                          )
                        RETURNING issuance_attempt_count
                        """
                    ),
                    {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
                )
            ).scalar_one_or_none()
            if transitioned is None:
                raise TrustAuditError(
                    "issuance_attempt_transition_refused:expected=1:observed=0"
                )
            attempt_id = uuid4()
            await audit_session.execute(
                text(
                    """
                    INSERT INTO public.trust_issuance_attempts (
                        id, tenant_id, audit_ref, attempt_number, attempt_state
                    ) VALUES (
                        :attempt_id, :tenant_id, :audit_ref, :attempt_number, 'signing'
                    )
                    """
                ),
                {
                    "attempt_id": str(attempt_id),
                    "tenant_id": str(tenant_id),
                    "audit_ref": audit_ref,
                    "attempt_number": int(transitioned),
                },
            )
    return attempt_id


async def authorize_durable_trust_signing_request(
    *,
    tenant_id: UUID,
    audit_ref: str,
    attempt_id: UUID,
    unsigned_envelope: dict[str, Any],
    audit_session_factory: AuditSessionFactory | None = None,
) -> DurableSigningAuthorization:
    """Re-establish exact P7 authority inside the isolated signer process.

    The public API may request signing, but it cannot mint this capability.
    The signer principal independently proves that the requested bytes are the
    bytes authorized by the current tenant-bound audit row and attempt.
    """
    if not isinstance(unsigned_envelope, dict):
        raise TrustAuditError("durable_signing_payload_required")
    try:
        canonicalize_envelope_payload(unsigned_envelope)
        envelope_hash = compute_envelope_payload_hash(unsigned_envelope)
    except Exception as exc:
        raise TrustAuditError("durable_signing_payload_invalid") from exc
    if unsigned_envelope.get("tenant_id_hash") != tenant_hash(tenant_id):
        raise TrustAuditError("durable_signing_tenant_mismatch")
    if unsigned_envelope.get("audit_ref") != audit_ref:
        raise TrustAuditError("durable_signing_audit_ref_mismatch")

    factory = audit_session_factory or trust_signer_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            row = (
                (
                    await audit_session.execute(
                        text(
                            """
                        SELECT log.envelope_hash, log.audit_hash,
                               log.issuance_attempt_count,
                               attempt.attempt_number
                        FROM public.trust_access_log AS log
                        JOIN public.trust_issuance_attempts AS attempt
                          ON attempt.tenant_id = log.tenant_id
                         AND attempt.audit_ref = log.audit_ref
                        WHERE log.tenant_id = :tenant_id
                          AND log.audit_ref = :audit_ref
                          AND log.event_type = 'issuance'
                          AND log.issuance_state = 'signing'
                          AND attempt.id = :attempt_id
                          AND attempt.attempt_state = 'signing'
                        """
                        ),
                        {
                            "tenant_id": str(tenant_id),
                            "audit_ref": audit_ref,
                            "attempt_id": str(attempt_id),
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
    if row is None:
        raise TrustAuditError("durable_signing_attempt_not_authorized")
    if int(row["attempt_number"]) != int(row["issuance_attempt_count"]):
        raise TrustAuditError("durable_signing_attempt_not_current")
    if row["envelope_hash"] != envelope_hash:
        raise TrustAuditError("durable_signing_envelope_hash_mismatch")
    if unsigned_envelope.get("audit_hash") != row["audit_hash"]:
        raise TrustAuditError("durable_signing_audit_hash_mismatch")
    return mint_durable_signing_authorization(
        DurableSigningAuthorizationMaterial(
            tenant_id=tenant_id,
            audit_ref=audit_ref,
            attempt_id=attempt_id,
            unsigned_envelope=unsigned_envelope,
        )
    )


async def record_trust_signature_consequence(
    consequence: SignedTrustEnvelopeConsequence,
    *,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, Any]:
    """Persist the exact signer-produced artifact before completion projection."""
    try:
        material = redeem_signing_consequence(consequence)
    except SigningConsequenceError as exc:
        raise TrustAuditError(str(exc)) from exc
    signing_key_id, signature_hash, signature = _issuance_crypto_evidence(
        material.signed_envelope
    )
    if material.signed_envelope.get("tenant_id_hash") != tenant_hash(
        material.tenant_id
    ):
        raise TrustAuditError("signing_consequence_tenant_mismatch")
    signed_envelope_hash = compute_envelope_payload_hash(material.signed_envelope)
    factory = audit_session_factory or trust_signer_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(material.tenant_id)},
            )
            known_at = (
                await audit_session.execute(
                    text(
                        """
                        UPDATE public.trust_issuance_attempts
                        SET attempt_state = 'signature_known',
                            signature_known_at = now(),
                            signing_key_id = :signing_key_id,
                            signature_hash = :signature_hash,
                            signature = :signature,
                            signed_envelope_hash = :signed_envelope_hash,
                            signed_envelope = CAST(:signed_envelope AS jsonb),
                            updated_at = now()
                        WHERE tenant_id = :tenant_id AND audit_ref = :audit_ref
                          AND id = :attempt_id AND attempt_state = 'signing'
                        RETURNING signature_known_at
                        """
                    ),
                    {
                        "tenant_id": str(material.tenant_id),
                        "audit_ref": material.audit_ref,
                        "attempt_id": str(material.attempt_id),
                        "signing_key_id": signing_key_id,
                        "signature_hash": signature_hash,
                        "signature": signature,
                        "signed_envelope_hash": signed_envelope_hash,
                        "signed_envelope": json.dumps(material.signed_envelope),
                    },
                )
            ).scalar_one_or_none()
            if known_at is None:
                raise TrustAuditError("signing_consequence_attempt_transition_refused")
            result = await audit_session.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET issuance_state = 'signature_known',
                        known_signature_at = :known_at,
                        issued_attempt_id = :attempt_id,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id AND audit_ref = :audit_ref
                      AND event_type = 'issuance' AND issuance_state = 'signing'
                    """
                ),
                {
                    "tenant_id": str(material.tenant_id),
                    "audit_ref": material.audit_ref,
                    "attempt_id": str(material.attempt_id),
                    "known_at": known_at,
                },
            )
            if int(getattr(result, "rowcount", -1)) != 1:
                raise TrustAuditError("signing_consequence_projection_refused")
    return deepcopy(material.signed_envelope)


async def record_trust_issuance_completed(
    *,
    tenant_id: UUID,
    audit_ref: str,
    signed_envelope: dict[str, Any] | None = None,
    attempt_id: UUID | None = None,
    key_registry: TrustKeyRegistry | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Project completion only from the exact durable signer attempt."""
    del signed_envelope  # C16 compatibility; caller-authored bytes carry no authority.
    factory = audit_session_factory or trust_issuance_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            artifact = (
                await audit_session.execute(
                    text(
                        """
                        SELECT attempt.signed_envelope
                        FROM public.trust_access_log AS log
                        JOIN public.trust_issuance_attempts AS attempt
                          ON attempt.tenant_id = log.tenant_id
                         AND attempt.audit_ref = log.audit_ref
                         AND attempt.id = log.issued_attempt_id
                        WHERE log.tenant_id = :tenant_id
                          AND log.audit_ref = :audit_ref
                          AND log.issuance_state = 'signature_known'
                          AND attempt.attempt_state = 'signature_known'
                          AND (CAST(:attempt_id AS uuid) IS NULL
                               OR attempt.id = CAST(:attempt_id AS uuid))
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "audit_ref": audit_ref,
                        "attempt_id": str(attempt_id) if attempt_id else None,
                    },
                )
            ).scalar_one_or_none()
            if artifact is None:
                raise TrustAuditError("issuance_completion_attempt_missing")
            verification_registries = []
            if key_registry is not None:
                verification_registries.append(key_registry.public_only())
            verification_registries.append(
                load_runtime_verification_registry().public_only()
            )
            verification = None
            for registry in verification_registries:
                candidate = verify_trust_envelope(
                    dict(artifact),
                    key_registry=registry,
                )
                verification = candidate
                if candidate.verification_status == "verified":
                    break
            if verification is None or verification.verification_status != "verified":
                raise TrustAuditError(
                    "issuance_completion_signature_invalid:"
                    f"{verification.reason_code if verification else 'no_registry'}"
                )
            result = await audit_session.execute(
                text(
                    """
                    UPDATE public.trust_access_log AS log
                    SET issuance_state = 'issued', issued_at = now(),
                        issued_signing_key_id = attempt.signing_key_id,
                        issued_signature_hash = attempt.signature_hash,
                        issued_signature = attempt.signature,
                        issued_envelope = attempt.signed_envelope,
                        updated_at = now()
                    FROM public.trust_issuance_attempts AS attempt
                    WHERE log.tenant_id = :tenant_id AND log.audit_ref = :audit_ref
                      AND log.event_type = 'issuance'
                      AND log.issuance_state = 'signature_known'
                      AND attempt.tenant_id = log.tenant_id
                      AND attempt.audit_ref = log.audit_ref
                      AND attempt.id = log.issued_attempt_id
                      AND (CAST(:attempt_id AS uuid) IS NULL
                           OR attempt.id = CAST(:attempt_id AS uuid))
                      AND attempt.attempt_state = 'signature_known'
                    RETURNING attempt.id
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "audit_ref": audit_ref,
                    "attempt_id": str(attempt_id) if attempt_id else None,
                },
            )
            completed_attempt = result.scalar_one_or_none()
            if completed_attempt is None:
                raise TrustAuditError("issuance_completion_transition_refused")
            await audit_session.execute(
                text(
                    """
                    UPDATE public.trust_issuance_attempts
                    SET attempt_state = 'issued', issued_at = now(), updated_at = now()
                    WHERE tenant_id = :tenant_id AND audit_ref = :audit_ref
                      AND id = :attempt_id AND attempt_state = 'signature_known'
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "audit_ref": audit_ref,
                    "attempt_id": str(completed_attempt),
                },
            )


async def load_durable_trust_issuance_artifact(
    *,
    tenant_id: UUID,
    audit_ref: str,
    audit_session_factory: AuditSessionFactory | None = None,
) -> tuple[str, UUID, dict[str, Any]] | None:
    """Return exact known/issued artifact for retry without recomputing truth."""
    factory = audit_session_factory or trust_issuance_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            row = (
                (
                    await audit_session.execute(
                        text(
                            """
                        SELECT log.issuance_state, attempt.id,
                               attempt.signed_envelope
                        FROM public.trust_access_log AS log
                        JOIN public.trust_issuance_attempts AS attempt
                          ON attempt.tenant_id = log.tenant_id
                         AND attempt.audit_ref = log.audit_ref
                         AND attempt.id = log.issued_attempt_id
                        WHERE log.tenant_id = :tenant_id
                          AND log.audit_ref = :audit_ref
                          AND log.issuance_state IN ('signature_known', 'issued')
                          AND attempt.attempt_state IN ('signature_known', 'issued')
                        """
                        ),
                        {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
                    )
                )
                .mappings()
                .one_or_none()
            )
    if row is None:
        return None
    return (
        str(row["issuance_state"]),
        UUID(str(row["id"])),
        dict(row["signed_envelope"]),
    )


async def load_durable_trust_issuance_replay(
    *,
    tenant_id: UUID,
    subject_type: str,
    subject_ref: str,
    audience_id: str,
    idempotency_key: str,
    audit_session_factory: AuditSessionFactory | None = None,
) -> tuple[str, str, UUID, dict[str, Any]] | None:
    """Resolve an exact prior artifact before rebuilding mutable current truth."""
    tenant_id_hash = tenant_hash(tenant_id)
    expected_identity = request_identity_hash(
        tenant_id_hash=tenant_id_hash,
        subject_type=subject_type,
        subject_ref_hash=tagged_sha256({"subject_ref": subject_ref}),
        audience_id_hash=tagged_sha256({"audience_id": audience_id}),
    )
    key_hash = idempotency_key_hash(
        tenant_id_hash=tenant_id_hash,
        idempotency_key=idempotency_key,
    )
    factory = audit_session_factory or trust_issuance_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            row = (
                (
                    await audit_session.execute(
                        text(
                            """
                        SELECT log.audit_ref, log.issuance_state, attempt.id,
                               attempt.signed_envelope
                        FROM public.trust_access_log AS log
                        JOIN public.trust_issuance_attempts AS attempt
                          ON attempt.tenant_id = log.tenant_id
                         AND attempt.audit_ref = log.audit_ref
                         AND attempt.id = log.issued_attempt_id
                        WHERE log.tenant_id = :tenant_id
                          AND log.event_type = 'issuance'
                          AND log.idempotency_key_hash = :key_hash
                          AND log.request_identity_hash = :request_identity_hash
                          AND log.issuance_state IN ('signature_known', 'issued')
                          AND attempt.attempt_state IN ('signature_known', 'issued')
                        """
                        ),
                        {
                            "tenant_id": str(tenant_id),
                            "key_hash": key_hash,
                            "request_identity_hash": expected_identity,
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
    if row is None:
        return None
    return (
        str(row["audit_ref"]),
        str(row["issuance_state"]),
        UUID(str(row["id"])),
        dict(row["signed_envelope"]),
    )


async def record_trust_export_attempt_started(
    *,
    tenant_id: UUID,
    request_binding_hash: str,
    page_start: int,
    audit_session_factory: AuditSessionFactory | None = None,
) -> UUID:
    """Write ahead of the independent outer-artifact signing consequence."""
    factory = audit_session_factory or trust_issuance_session_factory()
    attempt_id = uuid4()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            next_number = (
                await audit_session.execute(
                    text(
                        """
                        SELECT COALESCE(max(attempt_number), 0) + 1
                        FROM public.trust_export_artifact_attempts
                        WHERE tenant_id = :tenant_id
                          AND request_binding_hash = :request_binding_hash
                          AND page_start = :page_start
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "request_binding_hash": request_binding_hash,
                        "page_start": page_start,
                    },
                )
            ).scalar_one()
            await audit_session.execute(
                text(
                    """
                    INSERT INTO public.trust_export_artifact_attempts (
                        id, tenant_id, request_binding_hash, page_start,
                        attempt_number, attempt_state
                    ) VALUES (
                        :attempt_id, :tenant_id, :request_binding_hash,
                        :page_start, :attempt_number, 'signing'
                    )
                    """
                ),
                {
                    "attempt_id": str(attempt_id),
                    "tenant_id": str(tenant_id),
                    "request_binding_hash": request_binding_hash,
                    "page_start": page_start,
                    "attempt_number": int(next_number),
                },
            )
    return attempt_id


async def assert_durable_export_signing_request(
    *,
    tenant_id: UUID,
    attempt_id: UUID,
    unsigned_artifact: dict[str, Any],
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Bind one unsigned wrapper to a current signer-custody attempt."""
    if unsigned_artifact.get("tenant_id_hash") != tenant_hash(tenant_id):
        raise TrustAuditError("export_signing_tenant_mismatch")
    factory = audit_session_factory or trust_signer_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            exists = (
                await audit_session.execute(
                    text(
                        """
                        SELECT 1
                        FROM public.trust_export_artifact_attempts
                        WHERE tenant_id = :tenant_id AND id = :attempt_id
                          AND attempt_state = 'signing'
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "attempt_id": str(attempt_id),
                    },
                )
            ).scalar_one_or_none()
    if exists is None:
        raise TrustAuditError("export_signing_attempt_not_authorized")


async def record_trust_export_artifact_issued(
    *,
    tenant_id: UUID,
    attempt_id: UUID,
    artifact: dict[str, Any],
    key_registry: Any,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Verify and durably retain the exact outer artifact before delivery."""
    from app.trust.export_artifact import verify_export_artifact

    verification = verify_export_artifact(
        artifact,
        key_registry=key_registry.public_only(),
    )
    if verification.verification_status != "verified":
        raise TrustAuditError(
            f"export_artifact_consequence_invalid:{verification.reason_code}"
        )
    signature = decode_ed25519_signature(str(artifact.get("signature")))
    factory = audit_session_factory or trust_signer_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            result = await audit_session.execute(
                text(
                    """
                    UPDATE public.trust_export_artifact_attempts
                    SET attempt_state = 'issued', issued_at = now(),
                        artifact_hash = :artifact_hash,
                        signing_key_id = :signing_key_id,
                        signature_hash = :signature_hash,
                        signature = :signature,
                        signed_artifact = CAST(:signed_artifact AS jsonb),
                        updated_at = now()
                    WHERE tenant_id = :tenant_id AND id = :attempt_id
                      AND attempt_state = 'signing'
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "attempt_id": str(attempt_id),
                    "artifact_hash": artifact["artifact_hash"],
                    "signing_key_id": artifact["signing_key_id"],
                    "signature_hash": artifact["signature_hash"],
                    "signature": signature,
                    "signed_artifact": json.dumps(artifact),
                },
            )
            if int(getattr(result, "rowcount", -1)) != 1:
                raise TrustAuditError("export_artifact_consequence_transition_refused")


async def record_trust_export_attempt_unknown(
    *,
    tenant_id: UUID,
    attempt_id: UUID,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Preserve ambiguity when outer-artifact signing does not return."""
    await _execute_durable_issuance_update(
        tenant_id=tenant_id,
        statement=text(
            """
            UPDATE public.trust_export_artifact_attempts
            SET attempt_state = 'signature_outcome_unknown',
                outcome_unknown_at = now(), updated_at = now()
            WHERE tenant_id = :tenant_id AND id = :attempt_id
              AND attempt_state = 'signing'
            """
        ),
        params={"attempt_id": str(attempt_id)},
        expected_rows=1,
        failure_reason="export_artifact_unknown_transition_refused",
        audit_session_factory=audit_session_factory,
    )


async def load_durable_trust_export_artifact(
    *,
    tenant_id: UUID,
    request_binding_hash: str,
    page_start: int,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, Any] | None:
    """Return the exact previously issued wrapper for idempotent re-service."""
    factory = audit_session_factory or trust_issuance_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            artifact = (
                await audit_session.execute(
                    text(
                        """
                        SELECT signed_artifact
                        FROM public.trust_export_artifact_attempts
                        WHERE tenant_id = :tenant_id
                          AND request_binding_hash = :request_binding_hash
                          AND page_start = :page_start
                          AND attempt_state = 'issued'
                        ORDER BY attempt_number DESC LIMIT 1
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "request_binding_hash": request_binding_hash,
                        "page_start": page_start,
                    },
                )
            ).scalar_one_or_none()
    return dict(artifact) if artifact is not None else None


async def record_trust_issuance_failed(
    *,
    tenant_id: UUID,
    audit_ref: str,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Abandon an authorization that never crossed the signing boundary."""
    await _execute_durable_issuance_update(
        tenant_id=tenant_id,
        statement=text(
            """
            UPDATE public.trust_access_log
            SET issuance_state = 'failed', updated_at = now()
            WHERE tenant_id = :tenant_id
              AND audit_ref = :audit_ref
              AND event_type = 'issuance'
              AND issuance_state = 'authorized'
            """
        ),
        params={"audit_ref": audit_ref},
        expected_rows=1,
        failure_reason="issuance_failure_transition_refused",
        audit_session_factory=audit_session_factory,
    )


async def record_trust_issuance_outcome_unknown(
    *,
    tenant_id: UUID,
    audit_ref: str,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Record that private-key use began but physical completion is unknowable."""
    factory = audit_session_factory or trust_issuance_session_factory()
    async with factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            attempt_result = await audit_session.execute(
                text(
                    """
                    UPDATE public.trust_issuance_attempts AS attempt
                    SET attempt_state = 'signature_outcome_unknown',
                        outcome_unknown_at = now(), updated_at = now()
                    FROM public.trust_access_log AS log
                    WHERE log.tenant_id = :tenant_id AND log.audit_ref = :audit_ref
                      AND log.issuance_state = 'signing'
                      AND attempt.tenant_id = log.tenant_id
                      AND attempt.audit_ref = log.audit_ref
                      AND attempt.attempt_number = log.issuance_attempt_count
                      AND attempt.attempt_state = 'signing'
                    """
                ),
                {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
            )
            if int(getattr(attempt_result, "rowcount", -1)) != 1:
                raise TrustAuditError("issuance_unknown_attempt_transition_refused")
            result = await audit_session.execute(
                text(
                    """
                    UPDATE public.trust_access_log
                    SET issuance_state = 'signature_outcome_unknown',
                        issuance_outcome_unknown_at = now(),
                        issuance_unknown_outcome_count =
                            issuance_unknown_outcome_count + 1,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id AND audit_ref = :audit_ref
                      AND event_type = 'issuance' AND issuance_state = 'signing'
                    """
                ),
                {"tenant_id": str(tenant_id), "audit_ref": audit_ref},
            )
            if int(getattr(result, "rowcount", -1)) != 1:
                raise TrustAuditError("issuance_unknown_transition_refused")


async def record_trust_issuance_batch_completed(
    *,
    tenant_id: UUID,
    completions: Sequence[tuple[str, dict[str, Any]]],
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Finalize every envelope issued for one request in a single transaction.

    The export route signs several envelopes per HTTP request. Opening one
    durable session per envelope put N committed transactions inside a handler
    that must answer within ``EXPORT_HANDLER_DEADLINE_SECONDS``, which is both
    needless cost and the wrong granularity: the consequence boundary is the
    request, not the loop iteration. One transaction per request keeps the same
    truth -- ``issued`` still requires the signature that justifies it, enforced
    by ``ck_trust_access_log_issued_requires_crypto`` -- at one round trip.
    """

    if not completions:
        return

    rows: list[dict[str, Any]] = []
    for audit_ref, signed_envelope in completions:
        signing_key_id, signature_hash, signature = _issuance_crypto_evidence(
            signed_envelope
        )
        rows.append(
            {
                "audit_ref": audit_ref,
                "signing_key_id": signing_key_id,
                "signature_hash": signature_hash,
                "signature": signature,
            }
        )

    statement = text(
        """
        UPDATE public.trust_access_log AS log
        SET issuance_state = 'issued',
            issued_at = now(),
            issued_signing_key_id = completion.signing_key_id,
            issued_signature_hash = completion.signature_hash,
            issued_signature = completion.signature,
            issuance_outcome_unknown_at = NULL,
            updated_at = now()
        FROM (
            SELECT
                unnest(CAST(:audit_refs AS text[])) AS audit_ref,
                unnest(CAST(:signing_key_ids AS text[])) AS signing_key_id,
                unnest(CAST(:signature_hashes AS text[])) AS signature_hash,
                unnest(CAST(:signatures AS bytea[])) AS signature
        ) AS completion
        WHERE log.tenant_id = :tenant_id
          AND log.audit_ref = completion.audit_ref
          AND log.event_type = 'issuance'
          AND log.issuance_state = 'signing'
        """
    )
    params = {
        "tenant_id": str(tenant_id),
        "audit_refs": [row["audit_ref"] for row in rows],
        "signing_key_ids": [row["signing_key_id"] for row in rows],
        "signature_hashes": [row["signature_hash"] for row in rows],
        "signatures": [row["signature"] for row in rows],
    }
    await _execute_durable_issuance_update(
        tenant_id=tenant_id,
        statement=statement,
        params=params,
        expected_rows=len(rows),
        failure_reason="issuance_batch_completion_transition_refused",
        audit_session_factory=audit_session_factory,
    )


async def record_trust_issuance_batch_outcome_unknown(
    *,
    tenant_id: UUID,
    audit_refs: Sequence[str],
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Mark every in-flight export signature as physically indeterminate."""
    refs = list(dict.fromkeys(audit_refs))
    if not refs:
        return
    for audit_ref in refs:
        await record_trust_issuance_outcome_unknown(
            tenant_id=tenant_id,
            audit_ref=audit_ref,
            audit_session_factory=audit_session_factory,
        )


async def reconcile_stale_trust_issuance_states(
    *,
    tenant_id: UUID,
    stale_before: datetime,
    batch_size: int,
    key_registry: TrustKeyRegistry | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, int]:
    """Bound stale pre-sign rows and in-flight signing rows to truthful states."""
    if batch_size < 1:
        raise ValueError("batch_size_must_be_positive")
    if audit_session_factory is None:
        audit_session_factory = trust_issuance_session_factory()
    params = {
        "tenant_id": str(tenant_id),
        "stale_before": stale_before,
        "batch_size": batch_size,
    }
    counts: dict[str, int] = {
        "authorized_to_failed": 0,
        "signing_to_unknown": 0,
        "signature_known_to_issued": 0,
        "invalid_signature_known_refused": 0,
    }
    async with audit_session_factory() as audit_session:
        async with audit_session.begin():
            await audit_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            # Known signatures converge upward to issued from durable exact
            # evidence. Recovery never calls a private key and never guesses.
            known_rows = (
                (
                    await audit_session.execute(
                        text(
                            """
                        SELECT log.id, log.audit_ref, log.issued_attempt_id,
                               attempt.signed_envelope
                        FROM public.trust_access_log AS log
                        JOIN public.trust_issuance_attempts AS attempt
                          ON attempt.tenant_id = log.tenant_id
                         AND attempt.audit_ref = log.audit_ref
                         AND attempt.id = log.issued_attempt_id
                        WHERE log.tenant_id = :tenant_id
                          AND log.event_type = 'issuance'
                          AND log.issuance_state = 'signature_known'
                          AND attempt.attempt_state = 'signature_known'
                          AND log.updated_at < :stale_before
                        ORDER BY log.updated_at, log.id
                        LIMIT :batch_size
                        FOR UPDATE SKIP LOCKED
                        """
                        ),
                        params,
                    )
                )
                .mappings()
                .all()
            )
            for row in known_rows:
                registry = key_registry or load_runtime_verification_registry()
                verification = verify_trust_envelope(
                    dict(row["signed_envelope"]),
                    key_registry=registry.public_only(),
                )
                if verification.verification_status != "verified":
                    counts["invalid_signature_known_refused"] += 1
                    continue
                completed = await audit_session.execute(
                    text(
                        """
                        UPDATE public.trust_access_log AS log
                        SET issuance_state = 'issued', issued_at = now(),
                            issued_signing_key_id = attempt.signing_key_id,
                            issued_signature_hash = attempt.signature_hash,
                            issued_signature = attempt.signature,
                            issued_envelope = attempt.signed_envelope,
                            updated_at = now()
                        FROM public.trust_issuance_attempts AS attempt
                        WHERE log.id = :log_id AND log.tenant_id = :tenant_id
                          AND log.issuance_state = 'signature_known'
                          AND attempt.id = log.issued_attempt_id
                          AND attempt.tenant_id = log.tenant_id
                          AND attempt.audit_ref = log.audit_ref
                          AND attempt.attempt_state = 'signature_known'
                        """
                    ),
                    {**params, "log_id": row["id"]},
                )
                if int(getattr(completed, "rowcount", -1)) == 1:
                    await audit_session.execute(
                        text(
                            """
                            UPDATE public.trust_issuance_attempts
                            SET attempt_state = 'issued', issued_at = now(),
                                updated_at = now()
                            WHERE tenant_id = :tenant_id AND id = :attempt_id
                              AND attempt_state = 'signature_known'
                            """
                        ),
                        {**params, "attempt_id": row["issued_attempt_id"]},
                    )
                    counts["signature_known_to_issued"] += 1

            signing_rows = (
                (
                    await audit_session.execute(
                        text(
                            """
                        SELECT id, audit_ref, issuance_attempt_count
                        FROM public.trust_access_log
                        WHERE tenant_id = :tenant_id
                          AND event_type = 'issuance'
                          AND issuance_state = 'signing'
                          AND updated_at < :stale_before
                        ORDER BY updated_at, id
                        LIMIT :batch_size
                        FOR UPDATE SKIP LOCKED
                        """
                        ),
                        params,
                    )
                )
                .mappings()
                .all()
            )
            for row in signing_rows:
                attempt = await audit_session.execute(
                    text(
                        """
                        UPDATE public.trust_issuance_attempts
                        SET attempt_state = 'signature_outcome_unknown',
                            outcome_unknown_at = now(), updated_at = now()
                        WHERE tenant_id = :tenant_id AND audit_ref = :audit_ref
                          AND attempt_number = :attempt_number
                          AND attempt_state = 'signing'
                        """
                    ),
                    {
                        **params,
                        "audit_ref": row["audit_ref"],
                        "attempt_number": row["issuance_attempt_count"],
                    },
                )
                if int(getattr(attempt, "rowcount", -1)) != 1:
                    continue
                changed = await audit_session.execute(
                    text(
                        """
                        UPDATE public.trust_access_log
                        SET issuance_state = 'signature_outcome_unknown',
                            issuance_outcome_unknown_at = now(),
                            issuance_unknown_outcome_count =
                                issuance_unknown_outcome_count + 1,
                            updated_at = now()
                        WHERE id = :log_id AND tenant_id = :tenant_id
                          AND issuance_state = 'signing'
                        """
                    ),
                    {**params, "log_id": row["id"]},
                )
                counts["signing_to_unknown"] += max(
                    int(getattr(changed, "rowcount", -1)), 0
                )

            failed = await audit_session.execute(
                text(
                    """
                    WITH candidates AS (
                        SELECT id FROM public.trust_access_log
                        WHERE tenant_id = :tenant_id AND event_type = 'issuance'
                          AND issuance_state = 'authorized'
                          AND updated_at < :stale_before
                        ORDER BY updated_at, id LIMIT :batch_size
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE public.trust_access_log AS log
                    SET issuance_state = 'failed', updated_at = now()
                    FROM candidates WHERE log.id = candidates.id
                    """
                ),
                params,
            )
            counts["authorized_to_failed"] = max(
                int(getattr(failed, "rowcount", -1)), 0
            )
    return counts


def attach_audit_to_unsigned_payload(
    payload: dict[str, Any],
    *,
    audit_record: TrustAuditRecord,
    observed_at: datetime | str,
) -> dict[str, Any]:
    """Attach P7 audit material to an unsigned P5 TrustEnvelope payload."""
    updated = deepcopy(payload)
    updated["audit_ref"] = audit_record.audit_ref
    updated["audit_hash"] = audit_record.audit_hash
    updated["provenance_chain"] = replace_audit_provenance_entries(
        list(updated["provenance_chain"]),
        audit_ref=audit_record.audit_ref,
        audit_hash=audit_record.audit_hash,
        observed_at=observed_at,
    )
    updated["semantic_truth_hash"] = "sha256:" + ("0" * 64)
    updated["signature_hash"] = "sha256:" + ("0" * 64)
    updated["semantic_truth_hash"] = compute_semantic_truth_hash(updated)
    updated["signature_hash"] = compute_signature_hash(updated)
    canonicalize_envelope_payload(updated)
    return updated


def _created_at_source_from_context(
    request_context: dict[str, object],
) -> AuditTimestampSource:
    source = request_context.get("created_at_source")
    if source not in AUDIT_TIMESTAMP_AUTHORITY_SOURCES:
        raise TrustAuditError("audit_created_at_source_authority_required")
    return source  # type: ignore[return-value]


async def build_unsigned_trust_envelope_with_audit(
    db_session: AsyncSession,
    request: TrustEnvelopeBuildRequest,
    *,
    idempotency_key: str,
    audit_session_factory: AuditSessionFactory | None = None,
    access_log_only: bool = False,
    source: MatchVerdictSource | ConfidenceProjectionSource | None = None,
    cpu_runner: AuditCpuRunner | None = None,
) -> TrustEnvelopeAuditResult:
    """Build through P5, persist P7 audit, and attach audit refs to the payload."""
    build_result = await build_unsigned_trust_envelope(
        db_session,
        request,
        source=source,
        payload_runner=cpu_runner if source is not None else None,
    )
    tenant_id_hash = tenant_hash(request.tenant_id)
    created_at = request.request_context.get("created_at")
    if not isinstance(created_at, datetime):
        raise TrustAuditError("audit_created_at_required")
    created_at_source = _created_at_source_from_context(request.request_context)
    observed_at = created_at
    if build_result.status == "success" and build_result.unsigned_payload is not None:
        provisional = deepcopy(build_result.unsigned_payload)
        semantic_truth_hash = str(provisional["semantic_truth_hash"])
        subject_ref_hash = str(provisional["subject_ref_hash"])
        policy_state = str(
            provisional["policy_action_authority"].get("policy_state", "read_only")
        )
        audit_request = TrustAuditRequest(
            tenant_id=request.tenant_id,
            event_type="issuance",
            status="success",
            idempotency_key=idempotency_key,
            subject_type=request.subject_type,
            subject_ref_hash=subject_ref_hash,
            tenant_id_hash=tenant_id_hash,
            policy_state=policy_state,
            reason_code=None,
            semantic_truth_hash=semantic_truth_hash,
            envelope_hash=None,
            audience_id_hash=str(
                provisional["audience_binding"].get("audience_id_hash")
            ),
            evidence_refs_allowed=True,
            created_at=created_at,
            created_at_source=created_at_source,
        )
        initial_record = build_audit_record(audit_request)
        if cpu_runner is None:
            updated_payload = attach_audit_to_unsigned_payload(
                provisional,
                audit_record=initial_record,
                observed_at=observed_at,
            )
            envelope_hash = compute_envelope_payload_hash(updated_payload)
        else:
            updated_payload = await cpu_runner(
                attach_audit_to_unsigned_payload,
                provisional,
                audit_record=initial_record,
                observed_at=observed_at,
            )
            envelope_hash = await cpu_runner(
                compute_envelope_payload_hash,
                updated_payload,
            )
        final_request = TrustAuditRequest(
            **{
                **asdict(audit_request),
                "envelope_hash": envelope_hash,
            }
        )
        persisted = await record_trust_audit_event_durable(
            final_request,
            audit_session_factory=audit_session_factory,
            access_log_only=access_log_only,
        )
        if persisted.audit_hash != initial_record.audit_hash:
            if cpu_runner is None:
                updated_payload = attach_audit_to_unsigned_payload(
                    updated_payload,
                    audit_record=persisted,
                    observed_at=observed_at,
                )
            else:
                updated_payload = await cpu_runner(
                    attach_audit_to_unsigned_payload,
                    updated_payload,
                    audit_record=persisted,
                    observed_at=observed_at,
                )
        if cpu_runner is None:
            authorized_envelope = _authorize_audited_trust_envelope(
                build_result=build_result,
                audit_record=persisted,
                audited_payload=updated_payload,
                observed_at=observed_at,
            )
        else:
            authorized_envelope = await cpu_runner(
                _authorize_audited_trust_envelope,
                build_result=build_result,
                audit_record=persisted,
                audited_payload=updated_payload,
                observed_at=observed_at,
            )
        return TrustEnvelopeAuditResult(
            build_result=build_result,
            audit_record=persisted,
            unsigned_payload=updated_payload,
            authorized_envelope=authorized_envelope,
            refusal_payload=None,
        )

    refusal_payload = build_result.refusal_payload
    reason_code = build_result.reason_code or (
        str(refusal_payload.get("reason_code"))
        if refusal_payload
        else "validation_failed"
    )
    audit_request = TrustAuditRequest(
        tenant_id=request.tenant_id,
        event_type="refusal",
        status="refused",
        idempotency_key=idempotency_key,
        subject_type=request.subject_type,
        subject_ref_hash=None,
        tenant_id_hash=tenant_id_hash,
        policy_state="read_only",
        reason_code=reason_code,
        semantic_truth_hash=None,
        envelope_hash=None,
        audience_id_hash=(
            str(refusal_payload.get("audience_binding", {}).get("audience_id_hash"))
            if refusal_payload
            else None
        ),
        evidence_refs_allowed=False,
        created_at=created_at,
        created_at_source=created_at_source,
    )
    persisted = await record_trust_audit_event_durable(
        audit_request,
        audit_session_factory=audit_session_factory,
        access_log_only=access_log_only,
    )
    safe_refusal = deepcopy(refusal_payload) if refusal_payload else None
    if safe_refusal is not None:
        safe_refusal["audit_ref"] = persisted.audit_ref
        safe_refusal["audit_hash"] = persisted.audit_hash
    return TrustEnvelopeAuditResult(
        build_result=build_result,
        audit_record=persisted,
        unsigned_payload=None,
        authorized_envelope=None,
        refusal_payload=safe_refusal,
    )

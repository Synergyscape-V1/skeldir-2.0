"""B2.5-P7 tenant-scoped trust audit persistence substrate."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

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
from app.trust.refusal import tenant_hash, utc_second
from app.trust.semantic_authority import (
    AuthorizedTrustEnvelope,
    _authorize_audited_trust_envelope,
)
from app.trust.source_adapters import ConfidenceProjectionSource, MatchVerdictSource


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


async def _finalize_issuance_state(
    *,
    tenant_id: UUID,
    audit_ref: str,
    issuance_state: str,
    signed_envelope: dict[str, Any] | None,
    audit_session_factory: AuditSessionFactory | None,
) -> None:
    """Record the physical outcome of an authorised issuance.

    B2.5-P13 Corrective XV (H-XV-02/03). The pre-sign audit row records that an
    issuance was *authorised*. This is the second, separate durable write that
    records whether cryptographic issuance actually happened. It runs in its own
    committed transaction so the completion fact survives independently of the
    request transaction, exactly as the authorisation write does.

    ``ck_trust_access_log_issued_requires_crypto`` means PostgreSQL rejects an
    ``issued`` row that lacks a key id and signature hash, so this function
    cannot claim completion it did not witness.
    """

    if audit_session_factory is None:
        from app.db.session import AsyncSessionLocal

        audit_session_factory = AsyncSessionLocal

    if issuance_state == "issued":
        if not isinstance(signed_envelope, dict):
            raise TrustAuditError("issuance_completion_requires_signed_envelope")
        signing_key_id = signed_envelope.get("signing_key_id")
        signature_hash = signed_envelope.get("signature_hash")
        if not isinstance(signing_key_id, str) or not isinstance(signature_hash, str):
            raise TrustAuditError("issuance_completion_requires_signature_identity")
    else:
        signing_key_id = None
        signature_hash = None

    # A retry of the same logical request may complete an issuance that
    # previously failed, so 'failed' -> 'issued' is permitted: one logical
    # issuance keeps one lineage that ends at the truth. The reverse is not.
    # 'issued' is terminal, so a later failure cannot un-issue real history.
    permitted_previous = (
        ("authorized", "failed") if issuance_state == "issued" else ("authorized",)
    )
    params = {
        "tenant_id": str(tenant_id),
        "audit_ref": audit_ref,
        "issuance_state": issuance_state,
        "signing_key_id": signing_key_id,
        "signature_hash": signature_hash,
        "permitted_previous": list(permitted_previous),
    }
    statement = text(
        """
        UPDATE public.trust_access_log
        SET issuance_state = :issuance_state,
            issued_at = CASE WHEN :issuance_state = 'issued' THEN now() ELSE NULL END,
            issued_signing_key_id = :signing_key_id,
            issued_signature_hash = :signature_hash,
            updated_at = now()
        WHERE tenant_id = :tenant_id
          AND audit_ref = :audit_ref
          AND event_type = 'issuance'
          AND issuance_state = ANY(:permitted_previous)
        """
    )

    async with audit_session_factory() as audit_session:
        begin = getattr(audit_session, "begin", None)
        if callable(begin):
            async with begin():
                await audit_session.execute(
                    text(
                        "SELECT set_config('app.current_tenant_id', :tenant_id, true)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
                await audit_session.execute(statement, params)
                return
        await audit_session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        await audit_session.execute(statement, params)


async def record_trust_issuance_completed(
    *,
    tenant_id: UUID,
    audit_ref: str,
    signed_envelope: dict[str, Any],
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Durably record that a signature for this authorisation physically exists."""

    await _finalize_issuance_state(
        tenant_id=tenant_id,
        audit_ref=audit_ref,
        issuance_state="issued",
        signed_envelope=signed_envelope,
        audit_session_factory=audit_session_factory,
    )


async def record_trust_issuance_failed(
    *,
    tenant_id: UUID,
    audit_ref: str,
    audit_session_factory: AuditSessionFactory | None = None,
) -> None:
    """Durably record that an authorised issuance never produced a signature."""

    await _finalize_issuance_state(
        tenant_id=tenant_id,
        audit_ref=audit_ref,
        issuance_state="failed",
        signed_envelope=None,
        audit_session_factory=audit_session_factory,
    )


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

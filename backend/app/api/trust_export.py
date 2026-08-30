"""B2.5-P11 bounded machine-authorized signed export surface."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.trust_api import (
    TrustRequestBoundaryException,
    get_runtime_signing_registry,
    machine_bearer,
)
from app.db import session as db_session
from app.trust.audit import (
    build_unsigned_trust_envelope_with_audit,
    record_trust_issuance_batch_completed,
    record_trust_issuance_failed,
)
from app.trust.builder import TrustEnvelopeBuildRequest
from app.trust.export_artifact import build_export_artifact, sign_export_artifact
from app.trust.key_registry import TrustKeyRegistry
from app.trust.machine_auth import MachineCallerContext, authenticate_machine_caller
from app.trust.machine_identity import AgentScope
from app.trust.money_source_adapter import resolve_authoritative_money
from app.trust.query_continuation import (
    MAX_CURSOR_TOKEN_BYTES,
    TrustQueryContinuationError,
    continuation_expiry,
    issue_trust_query_continuation,
    trust_query_binding_hash,
    verify_trust_query_continuation,
)
from app.trust.reason_codes import ReasonCode
from app.trust.refusal import tenant_hash
from app.trust.signing import sign_trust_envelope
from app.trust.source_adapters import (
    MatchVerdictSource,
    parse_match_verdict_subject_ref,
    query_match_verdict_sources,
)
from app.trust.tenant_security import assert_authenticated_tenant_context


router = APIRouter()

MAX_EXPORT_BODY_BYTES = 65_536
MAX_ACCEPTED_EXPORT_REFS = 50
MAX_EVALUATED_EXPORT_REFS = 2
MAX_SIGNED_EXPORT_ENVELOPES = 2
MAX_EXPORT_ARTIFACT_BYTES = 1_048_576
MAX_CONCURRENT_EXPORT_EXECUTIONS = 2
EXPORT_HANDLER_DEADLINE_SECONDS = 1.5
SUPPORTED_EXPORT_SUBJECT_TYPES = frozenset({"match_verdict"})

_EXPORT_CONCURRENCY_LIMIT = asyncio.Semaphore(MAX_CONCURRENT_EXPORT_EXECUTIONS)
_FORBIDDEN_REF_TOKENS = ("*", "?", "%", "\\", "[", "]", "{", "}", "(", ")", "|")


class TrustExportRequestBoundaryException(TrustRequestBoundaryException):
    """Typed P11 request refusal that occurs before database access."""


class ExportMatchVerdictRequest(BaseModel):
    """Closed exact-reference request; the route fixes subject type itself."""

    model_config = ConfigDict(extra="forbid")

    subject_refs: list[str] = Field(min_length=1, max_length=MAX_ACCEPTED_EXPORT_REFS)
    continuation_token: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_CURSOR_TOKEN_BYTES,
    )

    @field_validator("subject_refs")
    @classmethod
    def validate_exact_unique_refs(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("subject_refs_must_be_unique")
        for value in values:
            if not value or len(value) > 512:
                raise ValueError("subject_ref_length_invalid")
            if any(token in value for token in _FORBIDDEN_REF_TOKENS):
                raise ValueError("wildcard_or_regex_subject_ref_forbidden")
            if parse_match_verdict_subject_ref(value) is None:
                raise ValueError("match_verdict_subject_ref_required")
        return values


async def trust_export_request_boundary_exception_handler(
    request: Request,
    exc: TrustExportRequestBoundaryException,
) -> JSONResponse:
    """Return a sanitized typed shape for declared and streamed overages."""
    _ = request
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "refused", "reason_code": exc.reason_code},
    )


async def _read_bounded_request_body(request: Request, *, limit: int) -> bytes:
    """Read no more than ``limit + 1`` bytes before any dependency opens a DB."""
    content_encoding = request.headers.get("content-encoding", "").strip().lower()
    if content_encoding not in {"", "identity"}:
        raise TrustExportRequestBoundaryException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            reason_code="unsupported_content_encoding",
        )
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            parsed_length = int(declared_length)
        except ValueError as exc:
            raise TrustExportRequestBoundaryException(
                status_code=status.HTTP_400_BAD_REQUEST,
                reason_code="invalid_content_length",
            ) from exc
        if parsed_length < 0:
            raise TrustExportRequestBoundaryException(
                status_code=status.HTTP_400_BAD_REQUEST,
                reason_code="invalid_content_length",
            )
        if parsed_length > limit:
            request.state.p11_ingress_bytes_consumed = 0
            raise TrustExportRequestBoundaryException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                reason_code="request_body_too_large",
            )
    payload = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        remaining = limit + 1 - len(payload)
        if remaining <= 0:
            request.state.p11_ingress_bytes_consumed = limit + 1
            raise TrustExportRequestBoundaryException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                reason_code="request_body_too_large",
            )
        payload.extend(chunk[:remaining])
        if len(chunk) > remaining or len(payload) > limit:
            request.state.p11_ingress_bytes_consumed = limit + 1
            raise TrustExportRequestBoundaryException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                reason_code="request_body_too_large",
            )
    request.state.p11_ingress_bytes_consumed = len(payload)
    return bytes(payload)


async def validate_export_request(request: Request) -> ExportMatchVerdictRequest:
    """Validate bounded JSON before the machine DB dependency is evaluated."""
    payload = await _read_bounded_request_body(request, limit=MAX_EXPORT_BODY_BYTES)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid bounded TrustEnvelope export request.",
        )
    try:
        return ExportMatchVerdictRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid bounded TrustEnvelope export request.",
        ) from exc


async def get_machine_export_db_session(
    request: Request,
    x_tenant_id: Annotated[UUID, Header(alias="X-Tenant-ID")],
) -> AsyncGenerator[AsyncSession, None]:
    """Open the same tenant-bound RLS session used by the P10 machine API."""
    async with db_session.get_session(x_tenant_id) as session:
        request.state.db_session = session
        yield session


async def require_export_scope(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_machine_export_db_session)],
    x_trust_nonce: Annotated[
        str,
        Header(alias="X-Trust-Nonce", min_length=16, max_length=256),
    ],
    _: Annotated[HTTPAuthorizationCredentials | None, Security(machine_bearer)],
) -> MachineCallerContext:
    _ = x_trust_nonce
    return await authenticate_machine_caller(
        request,
        session,
        required_scope=AgentScope.EXPORT_CREATE_LIMITED,
    )


async def require_export_tenant_context(
    request: Request,
    caller: Annotated[MachineCallerContext, Depends(require_export_scope)],
    session: Annotated[AsyncSession, Depends(get_machine_export_db_session)],
) -> MachineCallerContext:
    """Preserve authenticated identity continuity through the active RLS GUC."""
    return await assert_authenticated_tenant_context(request, session, caller)


def _assert_external_payload_safe(payload: object) -> None:
    if isinstance(payload, dict):
        if "tenant_id" in payload:
            raise RuntimeError("raw_tenant_id_response_forbidden")
        for key, value in payload.items():
            normalized_key = key.strip().lower()
            if normalized_key in {
                "tenant_id",
                "agent_client_id",
                "user_id",
                "private_key",
                "private_key_material",
                "secret",
                "seed",
                "credential",
                "database_url",
                "sql",
                "guc",
                "stack_trace",
                "traceback",
                "provider_native_payload",
            }:
                raise RuntimeError(f"unsafe_external_field_forbidden:{normalized_key}")
            if isinstance(value, float):
                raise RuntimeError("floating_point_export_response_forbidden")
            _assert_external_payload_safe(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_external_payload_safe(value)


def _json_response(payload: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    _assert_external_payload_safe(payload)
    return JSONResponse(status_code=status_code, content=payload)


def _typed_error_response(
    reason_code: ReasonCode | str,
    *,
    status_code: int,
) -> JSONResponse:
    reason = reason_code.value if isinstance(reason_code, ReasonCode) else reason_code
    return _json_response(
        {"status": "refused", "reason_code": reason},
        status_code=status_code,
    )


async def _issue_export_envelope(
    *,
    session: AsyncSession,
    caller: MachineCallerContext,
    subject_ref: str,
    idempotency_key: str,
    key_registry: TrustKeyRegistry,
    issued_at: datetime,
    source: MatchVerdictSource,
) -> tuple[dict[str, Any], str] | None:
    result = await build_unsigned_trust_envelope_with_audit(
        session,
        TrustEnvelopeBuildRequest(
            tenant_id=caller.tenant_id,
            subject_type="match_verdict",
            subject_ref=subject_ref,
            request_context={
                "audience_id": caller.audience,
                "created_at": issued_at,
                "created_at_source": "request_issuance_context",
            },
        ),
        idempotency_key=idempotency_key,
        access_log_only=False,
        source=source,
        cpu_runner=asyncio.to_thread,
    )
    if result.authorized_envelope is None:
        return None
    # B2.5-P13 Corrective XV (H-XV-02/03): the durable record says 'authorized'
    # until a signature physically exists, on the export path as on the read path.
    try:
        signed = await asyncio.to_thread(
            sign_trust_envelope,
            result.authorized_envelope,
            key_registry=key_registry,
        )
        _assert_external_payload_safe(signed)
    except BaseException:
        await record_trust_issuance_failed(
            tenant_id=caller.tenant_id,
            audit_ref=result.audit_record.audit_ref,
        )
        raise
    # Completion is finalised once per request by the caller, not once per
    # envelope: the consequence boundary is the request, and N durable
    # transactions inside a deadline-bounded handler is the wrong granularity.
    return signed, result.audit_record.audit_ref


async def _create_export_with_capacity(
    *,
    export_request: ExportMatchVerdictRequest,
    caller: MachineCallerContext,
    session: AsyncSession,
    key_registry: TrustKeyRegistry,
    idempotency_key: str,
) -> JSONResponse:
    now = datetime.now(timezone.utc)
    accepted_count = len(export_request.subject_refs)
    binding_hash = trust_query_binding_hash(
        tenant_id=caller.tenant_id,
        subject_types=["match_verdict"],
        subject_refs=export_request.subject_refs,
        updated_at_after=None,
        updated_at_before=None,
    )
    if export_request.continuation_token is None:
        start_position = 0
        expires_at = continuation_expiry(now)
    else:
        try:
            continuation = verify_trust_query_continuation(
                export_request.continuation_token,
                key_registry=key_registry,
                expected_binding_hash=binding_hash,
                expected_total=accepted_count,
                now=now,
            )
        except TrustQueryContinuationError as exc:
            reason = (
                ReasonCode.CONTINUATION_EXPIRED
                if exc.reason == "continuation_expired"
                else ReasonCode.CONTINUATION_INVALID
            )
            return _typed_error_response(
                reason,
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        start_position = continuation.next_position
        expires_at = continuation.expires_at

    end_position = min(
        start_position + MAX_EVALUATED_EXPORT_REFS,
        accepted_count,
    )
    page_refs = export_request.subject_refs[start_position:end_position]
    # Model A: bounded atomic preflight. No page-one authority is emitted unless
    # every accepted reference exists for this tenant and satisfies P4 money
    # authority. Only the current two-reference page is subsequently built,
    # audited, and signed.
    sources = await query_match_verdict_sources(
        session,
        tenant_id=caller.tenant_id,
        subject_refs=export_request.subject_refs,
        row_limit=accepted_count,
    )
    if len(sources) != accepted_count:
        return _typed_error_response(
            ReasonCode.SUBJECT_NOT_FOUND,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    sources_by_id = {source.id: source for source in sources}
    if any(
        resolve_authoritative_money(
            source_domain="b23_match_verdicts",
            source_field_path="canonical_net_verified_amount_minor",
            raw_value=source.canonical_net_verified_amount_minor,
            currency=source.currency_code,
            intended_trust_field="verified_revenue_minor",
        ).amount_minor
        is None
        for source in sources
    ):
        return _typed_error_response(
            ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    envelopes: list[dict[str, Any]] = []
    issuance_completions: list[tuple[str, dict[str, Any]]] = []
    for page_offset, subject_ref in enumerate(page_refs):
        verdict_id = parse_match_verdict_subject_ref(subject_ref)
        source = sources_by_id.get(verdict_id)
        if source is None:
            return _typed_error_response(
                ReasonCode.SUBJECT_NOT_FOUND,
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        issued = await _issue_export_envelope(
            session=session,
            caller=caller,
            subject_ref=subject_ref,
            idempotency_key=(
                f"{idempotency_key}:export:{binding_hash.removeprefix('sha256:')}:"
                f"{start_position + page_offset}"
            ),
            key_registry=key_registry,
            issued_at=now,
            source=source,
        )
        if issued is None:
            return _typed_error_response(
                ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE,
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        envelope, envelope_audit_ref = issued
        envelopes.append(envelope)
        issuance_completions.append((envelope_audit_ref, envelope))
    if len(envelopes) > MAX_SIGNED_EXPORT_ENVELOPES:
        raise RuntimeError("p11_signed_envelope_ceiling_breached")

    unsigned_artifact = await asyncio.to_thread(
        build_export_artifact,
        envelopes=envelopes,
        tenant_id_hash=tenant_hash(caller.tenant_id),
        generated_at=now,
    )
    artifact = await asyncio.to_thread(
        sign_export_artifact,
        unsigned_artifact,
        key_registry=key_registry,
    )
    response = _json_response(artifact)
    if len(response.body) > MAX_EXPORT_ARTIFACT_BYTES:
        return _typed_error_response(
            ReasonCode.RESPONSE_BUDGET_EXCEEDED,
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )

    # B2.5-P13 Corrective XV (H-XV-02/03). Every envelope in this artifact now
    # has a signature that physically exists, so durable history may say so --
    # in one transaction for the whole request rather than one per envelope.
    await record_trust_issuance_batch_completed(
        tenant_id=caller.tenant_id,
        completions=issuance_completions,
    )

    remaining_count = accepted_count - end_position
    response.headers["X-Export-Accepted-Count"] = str(accepted_count)
    response.headers["X-Export-Evaluated-Count"] = str(end_position)
    response.headers["X-Export-Remaining-Count"] = str(remaining_count)
    if remaining_count:
        response.headers["X-Trust-Continuation"] = issue_trust_query_continuation(
            key_registry=key_registry,
            binding_hash=binding_hash,
            next_position=end_position,
            total_accepted=accepted_count,
            expires_at=expires_at,
        )
    return response


@router.post(
    "/trust/v1/exports/match-verdicts",
    operation_id="createMatchVerdictExportArtifact",
)
async def create_match_verdict_export_artifact(
    export_request: Annotated[
        ExportMatchVerdictRequest, Depends(validate_export_request)
    ],
    caller: Annotated[MachineCallerContext, Depends(require_export_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_machine_export_db_session)],
    key_registry: Annotated[TrustKeyRegistry, Depends(get_runtime_signing_registry)],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[
        str,
        Header(alias="X-Idempotency-Key", min_length=1, max_length=256),
    ],
) -> JSONResponse:
    _ = x_correlation_id
    async with _EXPORT_CONCURRENCY_LIMIT:
        try:
            async with asyncio.timeout(EXPORT_HANDLER_DEADLINE_SECONDS):
                return await _create_export_with_capacity(
                    export_request=export_request,
                    caller=caller,
                    session=session,
                    key_registry=key_registry,
                    idempotency_key=x_idempotency_key,
                )
        except TimeoutError:
            return _typed_error_response(
                "export_handler_deadline_exceeded",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

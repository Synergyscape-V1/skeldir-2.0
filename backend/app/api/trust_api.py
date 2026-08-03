"""B2.5-P10 authenticated, bounded, read-only Trust API surface."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as db_session
from app.trust.audit import build_unsigned_trust_envelope_with_audit
from app.trust.builder import TrustEnvelopeBuildRequest
from app.trust.key_registry import TrustKeyRegistry
from app.trust.machine_auth import MachineCallerContext, authenticate_machine_caller
from app.trust.machine_identity import AgentScope
from app.trust.query_continuation import (
    MAX_CURSOR_TOKEN_BYTES,
    TrustQueryContinuationError,
    continuation_expiry,
    issue_trust_query_continuation,
    trust_query_binding_hash,
    verify_trust_query_continuation,
)
from app.trust.reason_codes import ReasonCode
from app.trust.runtime_keys import (
    RuntimeTrustKeyConfigurationError,
    load_runtime_signing_registry,
    load_runtime_verification_registry,
)
from app.trust.signing import sign_trust_envelope
from app.trust.source_adapters import (
    SUPPORTED_P5_SUBJECT_TYPES,
    MatchVerdictSource,
    parse_match_verdict_subject_ref,
    query_match_verdict_sources,
)
from app.trust.tenant_security import assert_authenticated_tenant_context
from app.trust.verification import verify_trust_envelope


router = APIRouter()
machine_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="MachineBearer",
    bearerFormat="opaque-machine-token",
)
MAX_QUERY_RANGE = timedelta(days=30)
MAX_QUERY_BODY_BYTES = 64 * 1024
MAX_ACCEPTED_SUBJECT_TYPES = 5
MAX_ACCEPTED_SUBJECT_REFS = 50
MAX_EXPANDED_LOOKUP_PAIRS = 50
MAX_EVALUATED_REFS_PER_PAGE = 2
MAX_RETURNED_OUTCOMES = 2
MAX_SIGNATURES_PER_REQUEST = 2
MAX_ISSUANCE_AUDIT_EFFECTS = 2
MAX_CONCURRENT_QUERY_REQUESTS = 2
MAX_SERIALIZED_ENVELOPE_BYTES = 64 * 1024
MAX_AGGREGATE_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_VERIFY_BODY_BYTES = 256 * 1024

if (
    MAX_RETURNED_OUTCOMES * MAX_SERIALIZED_ENVELOPE_BYTES + 1024
    > MAX_AGGREGATE_RESPONSE_BYTES
):
    raise RuntimeError("p10_static_aggregate_budget_is_not_closed")
_QUERY_CONCURRENCY_LIMIT = asyncio.Semaphore(MAX_CONCURRENT_QUERY_REQUESTS)
_FORBIDDEN_QUERY_TOKENS = (
    "*",
    "?",
    "%",
    "\\",
    "[",
    "]",
    "{",
    "}",
    "(",
    ")",
    "|",
)


def _utc_now() -> datetime:
    """One injectable aware clock for query continuation and issuance."""
    return datetime.now(timezone.utc)


class TrustSubjectType(str, Enum):
    """P1-governed TrustEnvelope subject vocabulary."""

    REVENUE_CLAIM = "revenue_claim"
    MATCH_VERDICT = "match_verdict"
    ATTRIBUTION_RESULT = "attribution_result"
    RECONCILIATION_DISCREPANCY = "reconciliation_discrepancy"
    CONFIDENCE_PROJECTION = "confidence_projection"


SUPPORTED_TRUST_SUBJECT_TYPES = frozenset({TrustSubjectType.MATCH_VERDICT})
RESERVED_TRUST_SUBJECT_TYPES = (
    frozenset(TrustSubjectType) - SUPPORTED_TRUST_SUBJECT_TYPES
)

if {
    value.value for value in SUPPORTED_TRUST_SUBJECT_TYPES
} != SUPPORTED_P5_SUBJECT_TYPES:
    raise RuntimeError("trust_api_p5_subject_capability_drift")


class TrustResponseBudgetExceeded(RuntimeError):
    """A governed response exceeded a fixed P10 serialization budget."""


class TrustRequestBoundaryException(HTTPException):
    """Typed pre-parsing ingress refusal emitted without downstream work."""

    def __init__(self, *, status_code: int, reason_code: str) -> None:
        self.status_code = status_code
        self.reason_code = reason_code
        super().__init__(
            status_code=status_code,
            detail={"status": "refused", "reason_code": reason_code},
        )


class TrustQueryRequest(BaseModel):
    """Strictly bounded exact-match query contract; no generic query AST exists."""

    model_config = ConfigDict(extra="forbid")

    subject_types: list[TrustSubjectType] = Field(
        min_length=1,
        max_length=MAX_ACCEPTED_SUBJECT_TYPES,
    )
    subject_refs: list[str] = Field(
        min_length=1,
        max_length=MAX_ACCEPTED_SUBJECT_REFS,
    )
    created_at_after: datetime | None = None
    created_at_before: datetime | None = None
    continuation_token: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_CURSOR_TOKEN_BYTES,
    )

    @field_validator("subject_types")
    @classmethod
    def validate_unique_subject_types(
        cls, values: list[TrustSubjectType]
    ) -> list[TrustSubjectType]:
        if len(set(values)) != len(values):
            raise ValueError("subject_types_must_be_unique")
        return values

    @field_validator("subject_refs")
    @classmethod
    def validate_exact_subject_refs(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("subject_refs_must_be_unique")
        for value in values:
            if not value or len(value) > 512:
                raise ValueError("subject_ref_length_invalid")
            if any(token in value for token in _FORBIDDEN_QUERY_TOKENS):
                raise ValueError("wildcard_or_regex_subject_ref_forbidden")
        return values

    @field_validator("created_at_after", "created_at_before")
    @classmethod
    def validate_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("query_timestamp_timezone_required")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "TrustQueryRequest":
        if len(self.subject_types) * len(self.subject_refs) > MAX_EXPANDED_LOOKUP_PAIRS:
            raise ValueError("expanded_lookup_pair_limit_exceeded")
        if self.created_at_after is None and self.created_at_before is None:
            return self
        if self.created_at_after is None or self.created_at_before is None:
            raise ValueError("query_date_range_requires_both_bounds")
        if self.created_at_before < self.created_at_after:
            raise ValueError("query_date_range_reversed")
        if self.created_at_before - self.created_at_after > MAX_QUERY_RANGE:
            raise ValueError("query_date_range_exceeds_30_days")
        return self


class TrustVerifyRequest(RootModel[dict[str, Any]]):
    """One supplied TrustEnvelope for authenticated verification."""


class TrustQueryPageState(BaseModel):
    """Machine-readable conservation state for one bounded query page."""

    model_config = ConfigDict(extra="forbid")

    accepted_count: int = Field(ge=1, le=MAX_ACCEPTED_SUBJECT_REFS)
    evaluated_count: int = Field(ge=1, le=MAX_ACCEPTED_SUBJECT_REFS)
    page_evaluated_count: int = Field(ge=1, le=MAX_EVALUATED_REFS_PER_PAGE)
    remaining_count: int = Field(ge=0, le=MAX_ACCEPTED_SUBJECT_REFS)
    complete: bool

    @model_validator(mode="after")
    def validate_conservation(self) -> "TrustQueryPageState":
        if self.evaluated_count + self.remaining_count != self.accepted_count:
            raise ValueError("query_page_work_conservation_failed")
        if self.complete != (self.remaining_count == 0):
            raise ValueError("query_page_completion_state_false")
        return self


class TrustQueryResponse(BaseModel):
    """Bounded envelopes plus explicit completion or continuation state."""

    model_config = ConfigDict(extra="forbid")

    envelopes: list[dict[str, Any]] = Field(max_length=MAX_RETURNED_OUTCOMES)
    page: TrustQueryPageState
    continuation_token: str | None = Field(
        default=None,
        max_length=MAX_CURSOR_TOKEN_BYTES,
    )

    @model_validator(mode="after")
    def validate_continuation_state(self) -> "TrustQueryResponse":
        if self.page.complete and self.continuation_token is not None:
            raise ValueError("terminal_query_page_has_continuation")
        if not self.page.complete and self.continuation_token is None:
            raise ValueError("nonterminal_query_page_missing_continuation")
        return self


async def trust_request_boundary_exception_handler(
    request: Request,
    exc: TrustRequestBoundaryException,
) -> JSONResponse:
    """Return the same sanitized shape for declared and streamed overages."""
    _ = request
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "refused", "reason_code": exc.reason_code},
    )


async def _read_bounded_request_body(request: Request, *, limit: int) -> bytes:
    """Retain at most ``limit + 1`` bytes without calling ``request.body()``."""
    content_encoding = request.headers.get("content-encoding", "").strip().lower()
    if content_encoding not in {"", "identity"}:
        raise TrustRequestBoundaryException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            reason_code="unsupported_content_encoding",
        )

    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            parsed_length = int(declared_length)
        except ValueError as exc:
            raise TrustRequestBoundaryException(
                status_code=status.HTTP_400_BAD_REQUEST,
                reason_code="invalid_content_length",
            ) from exc
        if parsed_length < 0:
            raise TrustRequestBoundaryException(
                status_code=status.HTTP_400_BAD_REQUEST,
                reason_code="invalid_content_length",
            )
        if parsed_length > limit:
            request.state.p10_ingress_bytes_consumed = 0
            raise TrustRequestBoundaryException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                reason_code="request_body_too_large",
            )

    payload = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        remaining = limit + 1 - len(payload)
        if remaining <= 0:
            request.state.p10_ingress_bytes_consumed = limit + 1
            raise TrustRequestBoundaryException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                reason_code="request_body_too_large",
            )
        payload.extend(chunk[:remaining])
        if len(chunk) > remaining or len(payload) > limit:
            request.state.p10_ingress_bytes_consumed = limit + 1
            raise TrustRequestBoundaryException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                reason_code="request_body_too_large",
            )
    request.state.p10_ingress_bytes_consumed = len(payload)
    return bytes(payload)


async def validate_trust_query_request(
    request: Request,
) -> TrustQueryRequest:
    """Validate the bounded body before any database dependency is opened."""
    payload = await _read_bounded_request_body(request, limit=MAX_QUERY_BODY_BYTES)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid bounded TrustEnvelope query.",
        )
    try:
        return TrustQueryRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid bounded TrustEnvelope query.",
        ) from exc


async def validate_trust_verify_request(request: Request) -> TrustVerifyRequest:
    """Bound hosted verification input before key lookup or cryptographic work."""
    payload = await _read_bounded_request_body(request, limit=MAX_VERIFY_BODY_BYTES)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid bounded TrustEnvelope verification request.",
        )
    try:
        return TrustVerifyRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid bounded TrustEnvelope verification request.",
        ) from exc


async def get_machine_db_session(
    request: Request,
    x_tenant_id: Annotated[UUID, Header(alias="X-Tenant-ID")],
) -> AsyncGenerator[AsyncSession, None]:
    """Open a tenant-RLS session without invoking human JWT/RBAC semantics."""
    async with db_session.get_session(x_tenant_id) as session:
        request.state.db_session = session
        yield session


async def require_envelope_read_scope(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
    x_trust_nonce: Annotated[
        str,
        Header(
            alias="X-Trust-Nonce",
            min_length=16,
            max_length=256,
        ),
    ],
    _: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(machine_bearer),
    ],
) -> MachineCallerContext:
    _ = x_trust_nonce
    return await authenticate_machine_caller(
        request,
        session,
        required_scope=AgentScope.ENVELOPE_READ,
    )


async def require_envelope_verify_scope(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
    x_trust_nonce: Annotated[
        str,
        Header(
            alias="X-Trust-Nonce",
            min_length=16,
            max_length=256,
        ),
    ],
    _: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(machine_bearer),
    ],
) -> MachineCallerContext:
    _ = x_trust_nonce
    return await authenticate_machine_caller(
        request,
        session,
        required_scope=AgentScope.ENVELOPE_VERIFY,
    )


async def require_envelope_read_tenant_context(
    request: Request,
    caller: Annotated[MachineCallerContext, Depends(require_envelope_read_scope)],
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
) -> MachineCallerContext:
    """Fail closed unless the authenticated tenant is the active RLS tenant."""
    return await assert_authenticated_tenant_context(request, session, caller)


async def require_envelope_verify_tenant_context(
    request: Request,
    caller: Annotated[MachineCallerContext, Depends(require_envelope_verify_scope)],
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
) -> MachineCallerContext:
    """Apply the same RLS identity invariant before hosted verification."""
    return await assert_authenticated_tenant_context(request, session, caller)


async def get_runtime_signing_registry() -> TrustKeyRegistry:
    """FastAPI seam for secret-backed signing authority and test overrides."""
    try:
        return load_runtime_signing_registry()
    except RuntimeTrustKeyConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trust signing authority unavailable.",
        ) from exc


async def get_runtime_verification_registry() -> TrustKeyRegistry:
    """FastAPI seam for active and historical public verification authority."""
    try:
        return load_runtime_verification_registry()
    except RuntimeTrustKeyConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trust verification authority unavailable.",
        ) from exc


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
            if isinstance(value, float) and (
                key.endswith("_minor") or key.endswith("_cents") or "money" in key
            ):
                raise RuntimeError("floating_point_money_response_forbidden")
            _assert_external_payload_safe(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_external_payload_safe(value)


def _json_response(payload: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    _assert_external_payload_safe(payload)
    return JSONResponse(status_code=status_code, content=payload)


def _typed_error_response(reason_code: ReasonCode, *, status_code: int) -> JSONResponse:
    return _json_response(
        {"status": "refused", "reason_code": reason_code.value},
        status_code=status_code,
    )


async def _issue_signed_envelope(
    *,
    session: AsyncSession,
    caller: MachineCallerContext,
    subject_type: str,
    subject_ref: str,
    idempotency_key: str,
    key_registry: TrustKeyRegistry,
    issued_at: datetime,
    source: MatchVerdictSource | None = None,
) -> dict[str, Any] | None:
    build_request = TrustEnvelopeBuildRequest(
        tenant_id=caller.tenant_id,
        subject_type=subject_type,
        subject_ref=subject_ref,
        request_context={
            "audience_id": caller.audience,
            "created_at": issued_at,
            "created_at_source": "request_issuance_context",
        },
    )
    result = await build_unsigned_trust_envelope_with_audit(
        session,
        build_request,
        idempotency_key=idempotency_key,
        access_log_only=True,
        source=source,
        cpu_runner=asyncio.to_thread,
    )
    if result.unsigned_payload is None:
        return None
    signed = await asyncio.to_thread(
        sign_trust_envelope,
        result.unsigned_payload,
        key_registry=key_registry,
    )
    _assert_external_payload_safe(signed)
    if len(JSONResponse(content=signed).body) > MAX_SERIALIZED_ENVELOPE_BYTES:
        raise TrustResponseBudgetExceeded("individual_envelope_budget_exceeded")
    return signed


@router.get("/trust/v1/envelopes/{subject_type}/{subject_ref}")
async def get_trust_envelope(
    subject_type: TrustSubjectType,
    subject_ref: str,
    caller: Annotated[
        MachineCallerContext,
        Depends(require_envelope_read_tenant_context),
    ],
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
    key_registry: Annotated[TrustKeyRegistry, Depends(get_runtime_signing_registry)],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[
        str,
        Header(alias="X-Idempotency-Key", min_length=1, max_length=256),
    ],
) -> JSONResponse:
    _ = x_correlation_id
    if subject_type in RESERVED_TRUST_SUBJECT_TYPES:
        return _typed_error_response(
            ReasonCode.UNSUPPORTED_SUBJECT_TYPE,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        envelope = await _issue_signed_envelope(
            session=session,
            caller=caller,
            subject_type=subject_type.value,
            subject_ref=subject_ref,
            idempotency_key=x_idempotency_key,
            key_registry=key_registry,
            issued_at=_utc_now(),
        )
    except TrustResponseBudgetExceeded:
        return _typed_error_response(
            ReasonCode.RESPONSE_BUDGET_EXCEEDED,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    if envelope is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found."
        )
    return _json_response(envelope)


@router.post(
    "/trust/v1/envelopes/query",
    response_model=TrustQueryResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": TrustQueryRequest.model_json_schema(),
                }
            },
        }
    },
)
async def query_trust_envelopes(
    query: Annotated[TrustQueryRequest, Depends(validate_trust_query_request)],
    caller: Annotated[
        MachineCallerContext,
        Depends(require_envelope_read_tenant_context),
    ],
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
    key_registry: Annotated[TrustKeyRegistry, Depends(get_runtime_signing_registry)],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[
        str,
        Header(alias="X-Idempotency-Key", min_length=1, max_length=256),
    ],
) -> JSONResponse:
    _ = x_correlation_id
    if any(value in RESERVED_TRUST_SUBJECT_TYPES for value in query.subject_types):
        return _typed_error_response(
            ReasonCode.UNSUPPORTED_SUBJECT_TYPE,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    async with _QUERY_CONCURRENCY_LIMIT:
        return await _query_trust_envelopes_with_capacity(
            query=query,
            caller=caller,
            session=session,
            key_registry=key_registry,
            idempotency_key=x_idempotency_key,
        )


async def _query_trust_envelopes_with_capacity(
    *,
    query: TrustQueryRequest,
    caller: MachineCallerContext,
    session: AsyncSession,
    key_registry: TrustKeyRegistry,
    idempotency_key: str,
) -> JSONResponse:
    """Evaluate one exact-reference page and conserve all accepted work."""
    now = _utc_now()
    accepted_count = len(query.subject_refs)
    binding_hash = trust_query_binding_hash(
        tenant_id=caller.tenant_id,
        subject_types=[value.value for value in query.subject_types],
        subject_refs=query.subject_refs,
        updated_at_after=query.created_at_after,
        updated_at_before=query.created_at_before,
    )
    if query.continuation_token is None:
        start_position = 0
        expires_at = continuation_expiry(now)
    else:
        try:
            continuation = verify_trust_query_continuation(
                query.continuation_token,
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
        start_position + MAX_EVALUATED_REFS_PER_PAGE,
        accepted_count,
    )
    page_refs = query.subject_refs[start_position:end_position]
    sources = await query_match_verdict_sources(
        session,
        tenant_id=caller.tenant_id,
        subject_refs=page_refs,
        updated_at_after=query.created_at_after,
        updated_at_before=query.created_at_before,
        row_limit=len(page_refs),
    )
    sources_by_id = {source.id: source for source in sources}
    issued_at = now
    envelopes: list[dict[str, Any]] = []
    try:
        for page_offset, subject_ref in enumerate(page_refs):
            verdict_id = parse_match_verdict_subject_ref(subject_ref)
            source = sources_by_id.get(verdict_id) if verdict_id is not None else None
            if source is None:
                continue
            global_position = start_position + page_offset
            envelope = await _issue_signed_envelope(
                session=session,
                caller=caller,
                subject_type=TrustSubjectType.MATCH_VERDICT.value,
                subject_ref=f"urn:skeldir:match_verdict:{source.id}",
                idempotency_key=(
                    f"{idempotency_key}:query:{binding_hash.removeprefix('sha256:')}:"
                    f"{global_position}"
                ),
                key_registry=key_registry,
                issued_at=issued_at,
                source=source,
            )
            if envelope is not None:
                envelopes.append(envelope)
    except TrustResponseBudgetExceeded:
        return _typed_error_response(
            ReasonCode.RESPONSE_BUDGET_EXCEEDED,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    remaining_count = accepted_count - end_position
    complete = remaining_count == 0
    continuation_token = None
    if not complete:
        continuation_token = issue_trust_query_continuation(
            key_registry=key_registry,
            binding_hash=binding_hash,
            next_position=end_position,
            total_accepted=accepted_count,
            expires_at=expires_at,
        )
    response_model = TrustQueryResponse(
        envelopes=envelopes,
        page=TrustQueryPageState(
            accepted_count=accepted_count,
            evaluated_count=end_position,
            page_evaluated_count=len(page_refs),
            remaining_count=remaining_count,
            complete=complete,
        ),
        continuation_token=continuation_token,
    )
    response = _json_response(response_model.model_dump(mode="json"))
    if len(response.body) > MAX_AGGREGATE_RESPONSE_BYTES:
        return _typed_error_response(
            ReasonCode.RESPONSE_BUDGET_EXCEEDED,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    return response


@router.post("/trust/v1/verify")
async def verify_supplied_trust_envelope(
    payload: Annotated[TrustVerifyRequest, Depends(validate_trust_verify_request)],
    caller: Annotated[
        MachineCallerContext,
        Depends(require_envelope_verify_tenant_context),
    ],
    key_registry: Annotated[
        TrustKeyRegistry,
        Depends(get_runtime_verification_registry),
    ],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
) -> JSONResponse:
    _ = caller, x_correlation_id
    result = verify_trust_envelope(payload.root, key_registry=key_registry)
    projection = result.external_projection()
    return _json_response(projection)

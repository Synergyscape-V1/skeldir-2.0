"""B2.5-P10 authenticated, bounded, read-only Trust API surface."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
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
from app.trust.runtime_keys import (
    RuntimeTrustKeyConfigurationError,
    load_runtime_signing_registry,
    load_runtime_verification_registry,
)
from app.trust.signing import sign_trust_envelope
from app.trust.verification import verify_trust_envelope


router = APIRouter()
MAX_QUERY_RANGE = timedelta(days=30)
MAX_QUERY_BODY_BYTES = 64 * 1024
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


class TrustSubjectType(str, Enum):
    """P1-governed TrustEnvelope subject vocabulary."""

    REVENUE_CLAIM = "revenue_claim"
    MATCH_VERDICT = "match_verdict"
    ATTRIBUTION_RESULT = "attribution_result"
    RECONCILIATION_DISCREPANCY = "reconciliation_discrepancy"
    CONFIDENCE_PROJECTION = "confidence_projection"


class TrustQueryRequest(BaseModel):
    """Strictly bounded exact-match query contract; no generic query AST exists."""

    model_config = ConfigDict(extra="forbid")

    subject_types: list[TrustSubjectType] = Field(min_length=1, max_length=5)
    subject_refs: list[str] = Field(min_length=1, max_length=50)
    created_at_after: datetime | None = None
    created_at_before: datetime | None = None

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


async def validate_trust_query_request(
    request: Request,
) -> TrustQueryRequest:
    """Validate the bounded body before any database dependency is opened."""
    payload = await request.body()
    if not payload or len(payload) > MAX_QUERY_BODY_BYTES:
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
) -> MachineCallerContext:
    return await authenticate_machine_caller(
        request,
        session,
        required_scope=AgentScope.ENVELOPE_READ,
    )


async def require_envelope_verify_scope(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
) -> MachineCallerContext:
    return await authenticate_machine_caller(
        request,
        session,
        required_scope=AgentScope.ENVELOPE_VERIFY,
    )


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
            if isinstance(value, float) and (
                key.endswith("_minor") or key.endswith("_cents") or "money" in key
            ):
                raise RuntimeError("floating_point_money_response_forbidden")
            _assert_external_payload_safe(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_external_payload_safe(value)


async def _issue_signed_envelope(
    *,
    session: AsyncSession,
    caller: MachineCallerContext,
    subject_type: str,
    subject_ref: str,
    idempotency_key: str,
    key_registry: TrustKeyRegistry,
    issued_at: datetime,
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
    )
    if result.unsigned_payload is None:
        return None
    signed = sign_trust_envelope(result.unsigned_payload, key_registry=key_registry)
    _assert_external_payload_safe(signed)
    return signed


def _in_created_at_range(envelope: dict[str, Any], query: TrustQueryRequest) -> bool:
    if query.created_at_after is None or query.created_at_before is None:
        return True
    raw = envelope.get("created_at")
    if not isinstance(raw, str) or not raw.endswith("Z"):
        return False
    created_at = datetime.fromisoformat(raw.removesuffix("Z") + "+00:00").astimezone(
        timezone.utc
    )
    return query.created_at_after <= created_at <= query.created_at_before


@router.get("/trust/v1/envelopes/{subject_type}/{subject_ref}")
async def get_trust_envelope(
    subject_type: TrustSubjectType,
    subject_ref: str,
    caller: Annotated[MachineCallerContext, Depends(require_envelope_read_scope)],
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
    key_registry: Annotated[TrustKeyRegistry, Depends(get_runtime_signing_registry)],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[
        str,
        Header(alias="X-Idempotency-Key", min_length=1, max_length=256),
    ],
) -> dict[str, Any]:
    _ = x_correlation_id
    envelope = await _issue_signed_envelope(
        session=session,
        caller=caller,
        subject_type=subject_type.value,
        subject_ref=subject_ref,
        idempotency_key=x_idempotency_key,
        key_registry=key_registry,
        issued_at=datetime.now(timezone.utc),
    )
    if envelope is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found."
        )
    return envelope


@router.post(
    "/trust/v1/envelopes/query",
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
    caller: Annotated[MachineCallerContext, Depends(require_envelope_read_scope)],
    session: Annotated[AsyncSession, Depends(get_machine_db_session)],
    key_registry: Annotated[TrustKeyRegistry, Depends(get_runtime_signing_registry)],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[
        str,
        Header(alias="X-Idempotency-Key", min_length=1, max_length=256),
    ],
) -> dict[str, list[dict[str, Any]]]:
    _ = x_correlation_id
    issued_at = datetime.now(timezone.utc)
    envelopes: list[dict[str, Any]] = []
    for subject_type in query.subject_types:
        for index, subject_ref in enumerate(query.subject_refs):
            envelope = await _issue_signed_envelope(
                session=session,
                caller=caller,
                subject_type=subject_type.value,
                subject_ref=subject_ref,
                idempotency_key=f"{x_idempotency_key}:{subject_type.value}:{index}",
                key_registry=key_registry,
                issued_at=issued_at,
            )
            if envelope is not None and _in_created_at_range(envelope, query):
                envelopes.append(envelope)
    return {"envelopes": envelopes}


@router.post("/trust/v1/verify")
async def verify_supplied_trust_envelope(
    payload: TrustVerifyRequest,
    caller: Annotated[MachineCallerContext, Depends(require_envelope_verify_scope)],
    key_registry: Annotated[
        TrustKeyRegistry,
        Depends(get_runtime_verification_registry),
    ],
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
) -> dict[str, object | None]:
    _ = caller, x_correlation_id
    result = verify_trust_envelope(payload.root, key_registry=key_registry)
    return result.external_projection()

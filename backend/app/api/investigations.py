from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response, Security, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.problem_details import problem_details_response
from app.db.deps import get_db_session
from app.schemas.llm_payloads import LLMTaskPayload
from app.security.auth import AuthContext, get_auth_context
from app.services.centaur_lifecycle import LifecycleStatus
from app.services.investigation import InvestigationJob, InvestigationService
from app.services.llm_dispatch import enqueue_llm_task
from app.services.review_mutation_ledger import (
    IdempotencyConflictError,
    ReviewMutationLedger,
    digest_sha256,
    scoped_review_idempotency_key,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_INVESTIGATION_SERVICE = InvestigationService()
_MUTATION_LEDGER = ReviewMutationLedger()

_PROBLEM_NOT_FOUND = "https://api.skeldir.com/problems/not-found"
_PROBLEM_VALIDATION = "https://api.skeldir.com/problems/request-validation-failed"
_PROBLEM_CONFLICT = "https://api.skeldir.com/problems/conflict"

InvestigationAction = Literal["approve", "reject", "refine", "rerun", "retry", "cancel"]


class InvestigationDateRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: str | None = None
    end_date: str | None = None


class InvestigationLaunchContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_range: InvestigationDateRange | None = None
    channels: list[str] | None = None
    budget_constraints: dict[str, Any] | None = None


class InvestigationLaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=10, max_length=500)
    context: InvestigationLaunchContext | None = None


class InvestigationMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1000)


class InvestigationFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["failed", "timeout", "cancelled", "rejected"]
    reason: str


class InvestigationLaunchAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    tenant_id: UUID
    status: str
    estimated_duration_seconds: int
    status_url: str
    result_url: str


class InvestigationMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    tenant_id: UUID
    action: InvestigationAction
    status: str
    idempotency_key: UUID
    idempotency_replayed: bool
    mutation_accepted: bool
    message: str | None = None
    status_url: str


class InvestigationStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    tenant_id: UUID
    status: str
    progress_percentage: int
    current_step: str
    review_required: bool
    available_actions: list[InvestigationAction]
    failure: InvestigationFailure | None = None
    result_preview: dict[str, Any] | None = None
    last_updated: datetime
    data_freshness_seconds: int


class InvestigationResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    tenant_id: UUID
    status: str
    last_updated: datetime
    data_freshness_seconds: int
    deterministic_findings: list[dict[str, Any]]
    llm_synthesis: dict[str, Any] | None = None


def _absolute_url(request: Request, path: str) -> str:
    return f"{str(request.base_url).rstrip('/')}{path}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _freshness_seconds(updated_at: datetime) -> int:
    return max(0, int((_now_utc() - _as_utc(updated_at)).total_seconds()))


def _status_progress(status_value: LifecycleStatus) -> tuple[int, str, bool, list[InvestigationAction]]:
    if status_value == LifecycleStatus.SUBMITTED:
        return 5, "Submitted for deterministic investigation", False, ["cancel"]
    if status_value == LifecycleStatus.VALIDATING:
        return 20, "Validating deterministic inputs", False, ["cancel"]
    if status_value == LifecycleStatus.INVESTIGATING:
        return 60, "Deterministic investigation in progress", False, ["cancel"]
    if status_value == LifecycleStatus.READY_FOR_REVIEW:
        return 100, "Awaiting reviewer decision", True, ["approve", "reject", "refine", "cancel"]
    if status_value == LifecycleStatus.APPROVED:
        return 100, "Reviewer approved investigation result", False, ["cancel"]
    if status_value == LifecycleStatus.REJECTED:
        return 100, "Reviewer rejected result", False, ["rerun"]
    if status_value == LifecycleStatus.REFINE_REQUESTED:
        return 100, "Refinement requested", False, ["rerun", "cancel"]
    if status_value == LifecycleStatus.RERUN_REQUESTED:
        return 85, "Rerun requested", False, ["cancel"]
    if status_value == LifecycleStatus.COMPLETED:
        return 100, "Completed", False, []
    if status_value == LifecycleStatus.FAILED:
        return 100, "Failed", False, ["retry"]
    if status_value == LifecycleStatus.TIMEOUT:
        return 100, "Timed out", False, ["retry"]
    return 100, "Cancelled", False, ["retry"]


def _failure_payload(job: InvestigationJob) -> InvestigationFailure | None:
    if job.status in (
        LifecycleStatus.REJECTED,
        LifecycleStatus.FAILED,
        LifecycleStatus.TIMEOUT,
        LifecycleStatus.CANCELLED,
    ):
        code_map = {
            LifecycleStatus.REJECTED: "rejected",
            LifecycleStatus.FAILED: "failed",
            LifecycleStatus.TIMEOUT: "timeout",
            LifecycleStatus.CANCELLED: "cancelled",
        }
        return InvestigationFailure(
            code=code_map[job.status],
            reason=job.failure_reason or f"investigation_{code_map[job.status]}",
        )
    return None


def _coerce_result_payload(job: InvestigationJob) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payload = dict(job.result or {})
    findings = payload.get("deterministic_findings")
    synthesis = payload.get("llm_synthesis")
    if isinstance(findings, list) and findings:
        return findings, synthesis if isinstance(synthesis, dict) else None

    observed_at = _as_utc(job.updated_at).isoformat().replace("+00:00", "Z")
    summary = payload.get("provider_summary") if isinstance(payload.get("provider_summary"), str) else "Summary unavailable"
    fallback_findings = [
        {
            "finding_id": f"investigation-{job.id}",
            "title": "Deterministic investigation artifact captured",
            "severity": "medium",
            "deterministic_confidence_score": 1.0,
            "evidence": [
                {
                    "metric_name": "authority_status",
                    "metric_value": 1,
                    "source_table": "investigation_jobs",
                    "observed_at": observed_at,
                }
            ],
        }
    ]
    fallback_synthesis = {
        "non_authoritative_summary": summary,
        "caveats": [
            "Synthesis is explanatory only and cannot override deterministic findings.",
        ],
        "model": "unknown",
        "generated_at": observed_at,
    }
    return fallback_findings, fallback_synthesis


def _contract_mode_enabled() -> bool:
    return os.getenv("CONTRACT_TESTING") == "1"


def _problem(
    request: Request,
    *,
    status_code: int,
    title: str,
    detail: str,
    correlation_id: UUID,
    type_url: str,
    code: str,
):
    return problem_details_response(
        request,
        status_code=status_code,
        title=title,
        detail=detail,
        correlation_id=correlation_id,
        type_url=type_url,
        code=code,
    )


async def _mutation_response(
    *,
    request: Request,
    response: Response,
    db_session: AsyncSession,
    auth_context: AuthContext,
    x_correlation_id: UUID,
    x_idempotency_key: UUID,
    investigation_id: UUID,
    action: InvestigationAction,
    reason: str | None,
    note: str | None,
):
    if _contract_mode_enabled():
        status_map = {
            "approve": LifecycleStatus.APPROVED.value,
            "reject": LifecycleStatus.REJECTED.value,
            "refine": LifecycleStatus.REFINE_REQUESTED.value,
            "rerun": LifecycleStatus.RERUN_REQUESTED.value,
            "retry": LifecycleStatus.RERUN_REQUESTED.value,
            "cancel": LifecycleStatus.CANCELLED.value,
        }
        response.headers["X-Idempotency-Replayed"] = "false"
        return InvestigationMutationResponse(
            investigation_id=investigation_id,
            tenant_id=auth_context.tenant_id,
            action=action,
            status=status_map[action],
            idempotency_key=x_idempotency_key,
            idempotency_replayed=False,
            mutation_accepted=True,
            message=f"Investigation {action} accepted.",
            status_url=_absolute_url(
                request, f"/api/investigations/{investigation_id}/status"
            ),
        )

    existing = await _INVESTIGATION_SERVICE.get_job(
        db_session,
        tenant_id=auth_context.tenant_id,
        job_id=investigation_id,
    )
    if existing is None:
        return _problem(
            request,
            status_code=404,
            title="Not Found",
            detail="Investigation not found.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_NOT_FOUND,
            code="NOT_FOUND",
        )

    try:
        if action == "approve":
            await _INVESTIGATION_SERVICE.approve_job(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=investigation_id,
            )
        elif action == "reject":
            await _INVESTIGATION_SERVICE.reject_job(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=investigation_id,
                reason=reason,
            )
        elif action == "refine":
            await _INVESTIGATION_SERVICE.request_refine(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=investigation_id,
                reason=reason,
            )
        elif action == "rerun":
            await _INVESTIGATION_SERVICE.request_rerun(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=investigation_id,
                reason=reason,
            )
        elif action == "retry":
            await _INVESTIGATION_SERVICE.request_retry(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=investigation_id,
                reason=reason,
            )
        else:
            await _INVESTIGATION_SERVICE.cancel_job(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=investigation_id,
                reason=reason,
            )
    except ValueError as exc:
        return _problem(
            request,
            status_code=409,
            title="Invalid Transition",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_VALIDATION,
            code="INVALID_STATE_TRANSITION",
        )

    updated = await _INVESTIGATION_SERVICE.get_job(
        db_session,
        tenant_id=auth_context.tenant_id,
        job_id=investigation_id,
    )
    if updated is None:
        return _problem(
            request,
            status_code=404,
            title="Not Found",
            detail="Investigation not found after mutation.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_NOT_FOUND,
            code="NOT_FOUND",
        )

    raw_payload = InvestigationMutationResponse(
        investigation_id=updated.id,
        tenant_id=updated.tenant_id,
        action=action,
        status=updated.status.value,
        idempotency_key=x_idempotency_key,
        idempotency_replayed=False,
        mutation_accepted=True,
        message=f"Investigation {action} accepted.",
        status_url=_absolute_url(
            request, f"/api/investigations/{updated.id}/status"
        ),
    ).model_dump(mode="json")

    scoped_key = scoped_review_idempotency_key(
        domain="investigation",
        entity_id=updated.id,
        action=action,
        idempotency_key=x_idempotency_key,
    )
    selector = {
        "domain": "investigation",
        "investigation_id": str(updated.id),
        "action": action,
        "public_idempotency_key": str(x_idempotency_key),
        "reason_hash": digest_sha256({"reason": reason or ""}),
        "note_hash": digest_sha256({"note": note or ""}),
    }
    effects = {
        "mutation_intent": action,
        "status": updated.status.value,
        "response_payload": raw_payload,
    }

    try:
        ledger_result = await _MUTATION_LEDGER.record_or_replay(
            db_session,
            tenant_id=auth_context.tenant_id,
            correlation_id=x_correlation_id,
            actor=auth_context.user_id,
            scoped_idempotency_key=scoped_key,
            selector=selector,
            effects=effects,
            audit_event_type="b15_investigation_review_mutation",
        )
    except IdempotencyConflictError as exc:
        return _problem(
            request,
            status_code=409,
            title="Idempotency Conflict",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_CONFLICT,
            code="IDEMPOTENCY_KEY_CONFLICT",
        )

    stored_payload = dict(ledger_result.stored_effects.get("response_payload", raw_payload))
    stored_payload["idempotency_replayed"] = ledger_result.replayed
    response.headers["X-Idempotency-Replayed"] = (
        "true" if ledger_result.replayed else "false"
    )
    logger.info(
        "investigation_review_mutation",
        extra={
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "event_type": "investigation.review_mutation",
            "action": action,
            "investigation_id": str(updated.id),
            "idempotency_replayed": ledger_result.replayed,
        },
    )
    return stored_payload


@router.post(
    "/api/investigations",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createInvestigation",
    response_model=InvestigationLaunchAccepted,
)
async def create_investigation(
    request: Request,
    response: Response,
    payload: InvestigationLaunchRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if _contract_mode_enabled():
        synthetic_id = uuid4()
        return InvestigationLaunchAccepted(
            investigation_id=synthetic_id,
            tenant_id=auth_context.tenant_id,
            status=LifecycleStatus.SUBMITTED.value,
            estimated_duration_seconds=45,
            status_url=_absolute_url(
                request, f"/api/investigations/{synthetic_id}/status"
            ),
            result_url=_absolute_url(request, f"/api/investigations/{synthetic_id}"),
        )

    request_id = str(x_correlation_id)
    authority_job = await _INVESTIGATION_SERVICE.get_or_create_job(
        db_session,
        tenant_id=auth_context.tenant_id,
        request_id=request_id,
        correlation_id=str(x_correlation_id),
    )
    task_payload = LLMTaskPayload(
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id,
        jti=auth_context.jti,
        iat=auth_context.issued_at_epoch,
        correlation_id=str(x_correlation_id),
        request_id=request_id,
        prompt={
            "question": payload.question,
            "context": payload.context.model_dump(mode="json") if payload.context else {},
        },
        max_cost_cents=30,
    )
    enqueue_llm_task("investigation", task_payload)

    logger.info(
        "investigation_launch",
        extra={
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "event_type": "investigation.launch",
            "investigation_id": str(authority_job.id),
        },
    )
    return InvestigationLaunchAccepted(
        investigation_id=authority_job.id,
        tenant_id=auth_context.tenant_id,
        status=authority_job.status.value,
        estimated_duration_seconds=45,
        status_url=_absolute_url(
            request, f"/api/investigations/{authority_job.id}/status"
        ),
        result_url=_absolute_url(request, f"/api/investigations/{authority_job.id}"),
    )


@router.get(
    "/api/investigations/{investigation_id}/status",
    operation_id="getInvestigationStatus",
    response_model=InvestigationStatusResponse,
)
async def get_investigation_status(
    request: Request,
    response: Response,
    investigation_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if _contract_mode_enabled():
        return InvestigationStatusResponse(
            investigation_id=investigation_id,
            tenant_id=auth_context.tenant_id,
            status=LifecycleStatus.READY_FOR_REVIEW.value,
            progress_percentage=100,
            current_step="Awaiting reviewer decision",
            review_required=True,
            available_actions=["approve", "reject", "refine", "cancel"],
            last_updated=_now_utc(),
            data_freshness_seconds=0,
        )

    job = await _INVESTIGATION_SERVICE.get_status_projection(
        db_session,
        tenant_id=auth_context.tenant_id,
        job_id=investigation_id,
    )
    if job is None:
        return _problem(
            request,
            status_code=404,
            title="Not Found",
            detail="Investigation not found.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_NOT_FOUND,
            code="NOT_FOUND",
        )
    progress, current_step, review_required, actions = _status_progress(job.status)
    return InvestigationStatusResponse(
        investigation_id=job.id,
        tenant_id=job.tenant_id,
        status=job.status.value,
        progress_percentage=progress,
        current_step=current_step,
        review_required=review_required,
        available_actions=actions,
        failure=_failure_payload(job),
        last_updated=job.updated_at,
        data_freshness_seconds=_freshness_seconds(job.updated_at),
    )


@router.get(
    "/api/investigations/{investigation_id}",
    operation_id="getInvestigationResult",
    response_model=InvestigationResultResponse,
)
async def get_investigation_result(
    request: Request,
    response: Response,
    investigation_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if _contract_mode_enabled():
        now = _now_utc()
        return InvestigationResultResponse(
            investigation_id=investigation_id,
            tenant_id=auth_context.tenant_id,
            status=LifecycleStatus.APPROVED.value,
            last_updated=now,
            data_freshness_seconds=0,
            deterministic_findings=[
                {
                    "finding_id": "contract-mode",
                    "title": "Contract mode deterministic finding",
                    "severity": "medium",
                    "deterministic_confidence_score": 1.0,
                    "evidence": [
                        {
                            "metric_name": "contract_mode",
                            "metric_value": 1,
                            "source_table": "investigation_jobs",
                            "observed_at": now.isoformat().replace("+00:00", "Z"),
                        }
                    ],
                }
            ],
            llm_synthesis={
                "non_authoritative_summary": "Contract testing mode summary.",
                "generated_at": now.isoformat().replace("+00:00", "Z"),
            },
        )

    job = await _INVESTIGATION_SERVICE.get_job(
        db_session,
        tenant_id=auth_context.tenant_id,
        job_id=investigation_id,
    )
    if job is None:
        return _problem(
            request,
            status_code=404,
            title="Not Found",
            detail="Investigation not found.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_NOT_FOUND,
            code="NOT_FOUND",
        )
    if job.status in (
        LifecycleStatus.SUBMITTED,
        LifecycleStatus.VALIDATING,
        LifecycleStatus.INVESTIGATING,
        LifecycleStatus.RERUN_REQUESTED,
    ):
        return _problem(
            request,
            status_code=409,
            title="Result Not Ready",
            detail="Investigation result is not available in current lifecycle state.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_VALIDATION,
            code="RESULT_NOT_READY",
        )

    findings, synthesis = _coerce_result_payload(job)
    return InvestigationResultResponse(
        investigation_id=job.id,
        tenant_id=job.tenant_id,
        status=job.status.value,
        last_updated=job.updated_at,
        data_freshness_seconds=_freshness_seconds(job.updated_at),
        deterministic_findings=findings,
        llm_synthesis=synthesis,
    )


@router.post(
    "/api/investigations/{investigation_id}/approve",
    operation_id="approveInvestigation",
    response_model=InvestigationMutationResponse,
)
async def approve_investigation(
    request: Request,
    response: Response,
    investigation_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: InvestigationMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        investigation_id=investigation_id,
        action="approve",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )


@router.post(
    "/api/investigations/{investigation_id}/reject",
    operation_id="rejectInvestigation",
    response_model=InvestigationMutationResponse,
)
async def reject_investigation(
    request: Request,
    response: Response,
    investigation_id: UUID,
    payload: InvestigationMutationRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        investigation_id=investigation_id,
        action="reject",
        reason=payload.reason,
        note=payload.note,
    )


@router.post(
    "/api/investigations/{investigation_id}/refine",
    operation_id="refineInvestigation",
    response_model=InvestigationMutationResponse,
)
async def refine_investigation(
    request: Request,
    response: Response,
    investigation_id: UUID,
    payload: InvestigationMutationRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        investigation_id=investigation_id,
        action="refine",
        reason=payload.reason,
        note=payload.note,
    )


@router.post(
    "/api/investigations/{investigation_id}/rerun",
    operation_id="rerunInvestigation",
    response_model=InvestigationMutationResponse,
)
async def rerun_investigation(
    request: Request,
    response: Response,
    investigation_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: InvestigationMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        investigation_id=investigation_id,
        action="rerun",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )


@router.post(
    "/api/investigations/{investigation_id}/retry",
    operation_id="retryInvestigation",
    response_model=InvestigationMutationResponse,
)
async def retry_investigation(
    request: Request,
    response: Response,
    investigation_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: InvestigationMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        investigation_id=investigation_id,
        action="retry",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )


@router.post(
    "/api/investigations/{investigation_id}/cancel",
    operation_id="cancelInvestigation",
    response_model=InvestigationMutationResponse,
)
async def cancel_investigation(
    request: Request,
    response: Response,
    investigation_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: InvestigationMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        investigation_id=investigation_id,
        action="cancel",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )

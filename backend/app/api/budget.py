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
from app.services.budget_job import BudgetJobRecord, BudgetJobService
from app.services.centaur_lifecycle import LifecycleStatus
from app.services.llm_dispatch import enqueue_llm_task
from app.services.review_mutation_ledger import (
    IdempotencyConflictError,
    ReviewMutationLedger,
    digest_sha256,
    scoped_review_idempotency_key,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_BUDGET_SERVICE = BudgetJobService()
_MUTATION_LEDGER = ReviewMutationLedger()

_PROBLEM_NOT_FOUND = "https://api.skeldir.com/problems/not-found"
_PROBLEM_VALIDATION = "https://api.skeldir.com/problems/request-validation-failed"
_PROBLEM_CONFLICT = "https://api.skeldir.com/problems/conflict"

BudgetAction = Literal["approve", "reject", "refine", "rerun", "retry", "cancel"]
OptimizationGoal = Literal["maximize_roas", "maximize_revenue", "minimize_cpa"]


class BudgetDateRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: str | None = None
    end_date: str | None = None


class BudgetConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_range: BudgetDateRange | None = None
    channel_minimums: dict[str, float] | None = None
    channel_maximums: dict[str, float] | None = None


class BudgetOptimizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_budget: float = Field(ge=1000)
    constraints: BudgetConstraints | None = None
    optimization_goal: OptimizationGoal


class BudgetMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1000)


class BudgetFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["failed", "timeout", "cancelled", "rejected"]
    reason: str


class BudgetLaunchAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    tenant_id: UUID
    status: str
    estimated_duration_seconds: int
    status_url: str
    result_url: str


class BudgetMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    tenant_id: UUID
    action: BudgetAction
    status: str
    idempotency_key: UUID
    idempotency_replayed: bool
    mutation_accepted: bool
    message: str | None = None
    status_url: str


class BudgetStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    tenant_id: UUID
    status: str
    progress_percentage: int
    current_step: str
    review_required: bool
    available_actions: list[BudgetAction]
    failure: BudgetFailure | None = None
    result_preview: dict[str, Any] | None = None
    last_updated: datetime
    data_freshness_seconds: int


class BudgetRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    tenant_id: UUID
    status: str
    last_updated: datetime
    data_freshness_seconds: int
    deterministic_recommendation: dict[str, Any]
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


def _status_progress(status_value: LifecycleStatus) -> tuple[int, str, bool, list[BudgetAction]]:
    if status_value == LifecycleStatus.SUBMITTED:
        return 5, "Submitted for deterministic budget optimization", False, ["cancel"]
    if status_value == LifecycleStatus.VALIDATING:
        return 20, "Validating deterministic budget inputs", False, ["cancel"]
    if status_value == LifecycleStatus.INVESTIGATING:
        return 60, "Deterministic optimization in progress", False, ["cancel"]
    if status_value == LifecycleStatus.READY_FOR_REVIEW:
        return 100, "Awaiting reviewer decision", True, ["approve", "reject", "refine", "cancel"]
    if status_value == LifecycleStatus.APPROVED:
        return 100, "Reviewer approved recommendation", False, ["cancel"]
    if status_value == LifecycleStatus.REJECTED:
        return 100, "Reviewer rejected recommendation", False, ["rerun"]
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


def _failure_payload(job: BudgetJobRecord) -> BudgetFailure | None:
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
        return BudgetFailure(
            code=code_map[job.status],
            reason=job.failure_reason or f"budget_{code_map[job.status]}",
        )
    return None


def _coerce_result_payload(job: BudgetJobRecord) -> tuple[dict[str, Any], dict[str, Any] | None]:
    payload = dict(job.result or {})
    recommendation = payload.get("deterministic_recommendation")
    synthesis = payload.get("llm_synthesis")
    if isinstance(recommendation, dict):
        return recommendation, synthesis if isinstance(synthesis, dict) else None

    observed_at = _as_utc(job.updated_at).isoformat().replace("+00:00", "Z")
    summary = payload.get("provider_summary") if isinstance(payload.get("provider_summary"), str) else "Summary unavailable"
    fallback_recommendation = {
        "optimization_goal": "maximize_roas",
        "allocations": [],
        "evidence": [
            {
                "metric_name": "authority_status",
                "channel": "aggregate",
                "metric_value": 1,
                "source_table": "budget_jobs",
                "observed_at": observed_at,
            }
        ],
        "generated_at": observed_at,
    }
    fallback_synthesis = {
        "non_authoritative_summary": summary,
        "caveats": [
            "Synthesis is explanatory only and cannot override deterministic recommendation fields.",
        ],
        "model": "unknown",
        "generated_at": observed_at,
    }
    return fallback_recommendation, fallback_synthesis


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
    job_id: UUID,
    action: BudgetAction,
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
        return BudgetMutationResponse(
            job_id=job_id,
            tenant_id=auth_context.tenant_id,
            action=action,
            status=status_map[action],
            idempotency_key=x_idempotency_key,
            idempotency_replayed=False,
            mutation_accepted=True,
            message=f"Budget recommendation {action} accepted.",
            status_url=_absolute_url(
                request, f"/api/budget/recommendations/{job_id}/status"
            ),
        )

    try:
        await _BUDGET_SERVICE.get_by_id(
            db_session,
            tenant_id=auth_context.tenant_id,
            job_id=job_id,
        )
    except ValueError:
        return _problem(
            request,
            status_code=404,
            title="Not Found",
            detail="Budget recommendation job not found.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_NOT_FOUND,
            code="NOT_FOUND",
        )

    try:
        if action == "approve":
            await _BUDGET_SERVICE.approve_job(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=job_id,
            )
        elif action == "reject":
            await _BUDGET_SERVICE.reject_job(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=job_id,
                reason=reason,
            )
        elif action == "refine":
            await _BUDGET_SERVICE.request_refine(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=job_id,
                reason=reason,
            )
        elif action == "rerun":
            await _BUDGET_SERVICE.request_rerun(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=job_id,
                reason=reason,
            )
        elif action == "retry":
            await _BUDGET_SERVICE.request_retry(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=job_id,
                reason=reason,
            )
        else:
            await _BUDGET_SERVICE.cancel_job(
                db_session,
                tenant_id=auth_context.tenant_id,
                job_id=job_id,
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

    updated = await _BUDGET_SERVICE.get_by_id(
        db_session,
        tenant_id=auth_context.tenant_id,
        job_id=job_id,
    )
    raw_payload = BudgetMutationResponse(
        job_id=updated.id,
        tenant_id=updated.tenant_id,
        action=action,
        status=updated.status.value,
        idempotency_key=x_idempotency_key,
        idempotency_replayed=False,
        mutation_accepted=True,
        message=f"Budget recommendation {action} accepted.",
        status_url=_absolute_url(
            request, f"/api/budget/recommendations/{updated.id}/status"
        ),
    ).model_dump(mode="json")

    scoped_key = scoped_review_idempotency_key(
        domain="budget",
        entity_id=updated.id,
        action=action,
        idempotency_key=x_idempotency_key,
    )
    selector = {
        "domain": "budget",
        "job_id": str(updated.id),
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
            audit_event_type="b15_budget_review_mutation",
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
        "budget_review_mutation",
        extra={
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "event_type": "budget.review_mutation",
            "action": action,
            "job_id": str(updated.id),
            "idempotency_replayed": ledger_result.replayed,
        },
    )
    return stored_payload


@router.post(
    "/api/budget/optimize",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createBudgetOptimization",
    response_model=BudgetLaunchAccepted,
)
async def create_budget_optimization(
    request: Request,
    response: Response,
    payload: BudgetOptimizationRequest,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if _contract_mode_enabled():
        synthetic_id = uuid4()
        return BudgetLaunchAccepted(
            job_id=synthetic_id,
            tenant_id=auth_context.tenant_id,
            status=LifecycleStatus.SUBMITTED.value,
            estimated_duration_seconds=15,
            status_url=_absolute_url(
                request, f"/api/budget/recommendations/{synthetic_id}/status"
            ),
            result_url=_absolute_url(request, f"/api/budget/recommendations/{synthetic_id}"),
        )

    request_id = str(x_correlation_id)
    authority_job = await _BUDGET_SERVICE.get_or_create_job(
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
            "total_budget": payload.total_budget,
            "constraints": payload.constraints.model_dump(mode="json") if payload.constraints else {},
            "optimization_goal": payload.optimization_goal,
        },
        max_cost_cents=30,
    )
    enqueue_llm_task("budget_optimization", task_payload)

    logger.info(
        "budget_launch",
        extra={
            "tenant_id": str(auth_context.tenant_id),
            "correlation_id": str(x_correlation_id),
            "event_type": "budget.launch",
            "job_id": str(authority_job.id),
        },
    )
    return BudgetLaunchAccepted(
        job_id=authority_job.id,
        tenant_id=auth_context.tenant_id,
        status=authority_job.status.value,
        estimated_duration_seconds=15,
        status_url=_absolute_url(
            request, f"/api/budget/recommendations/{authority_job.id}/status"
        ),
        result_url=_absolute_url(request, f"/api/budget/recommendations/{authority_job.id}"),
    )


@router.get(
    "/api/budget/recommendations/{job_id}/status",
    operation_id="getBudgetRecommendationStatus",
    response_model=BudgetStatusResponse,
)
async def get_budget_recommendation_status(
    request: Request,
    response: Response,
    job_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if _contract_mode_enabled():
        return BudgetStatusResponse(
            job_id=job_id,
            tenant_id=auth_context.tenant_id,
            status=LifecycleStatus.READY_FOR_REVIEW.value,
            progress_percentage=100,
            current_step="Awaiting reviewer decision",
            review_required=True,
            available_actions=["approve", "reject", "refine", "cancel"],
            last_updated=_now_utc(),
            data_freshness_seconds=0,
        )

    record = await _BUDGET_SERVICE.get_status_projection(
        db_session,
        tenant_id=auth_context.tenant_id,
        job_id=job_id,
    )
    if record is None:
        return _problem(
            request,
            status_code=404,
            title="Not Found",
            detail="Budget recommendation job not found.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_NOT_FOUND,
            code="NOT_FOUND",
        )

    progress, current_step, review_required, actions = _status_progress(record.status)
    return BudgetStatusResponse(
        job_id=record.id,
        tenant_id=record.tenant_id,
        status=record.status.value,
        progress_percentage=progress,
        current_step=current_step,
        review_required=review_required,
        available_actions=actions,
        failure=_failure_payload(record),
        last_updated=record.updated_at,
        data_freshness_seconds=_freshness_seconds(record.updated_at),
    )


@router.get(
    "/api/budget/recommendations/{job_id}",
    operation_id="getBudgetRecommendation",
    response_model=BudgetRecommendationResponse,
)
async def get_budget_recommendation(
    request: Request,
    response: Response,
    job_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if _contract_mode_enabled():
        now = _now_utc()
        return BudgetRecommendationResponse(
            job_id=job_id,
            tenant_id=auth_context.tenant_id,
            status=LifecycleStatus.APPROVED.value,
            last_updated=now,
            data_freshness_seconds=0,
            deterministic_recommendation={
                "optimization_goal": "maximize_roas",
                "allocations": [],
                "evidence": [],
                "generated_at": now.isoformat().replace("+00:00", "Z"),
            },
            llm_synthesis={
                "non_authoritative_summary": "Contract testing mode summary.",
                "generated_at": now.isoformat().replace("+00:00", "Z"),
            },
        )

    try:
        record = await _BUDGET_SERVICE.get_by_id(
            db_session,
            tenant_id=auth_context.tenant_id,
            job_id=job_id,
        )
    except ValueError:
        return _problem(
            request,
            status_code=404,
            title="Not Found",
            detail="Budget recommendation job not found.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_NOT_FOUND,
            code="NOT_FOUND",
        )
    if record.status in (
        LifecycleStatus.SUBMITTED,
        LifecycleStatus.VALIDATING,
        LifecycleStatus.INVESTIGATING,
        LifecycleStatus.RERUN_REQUESTED,
    ):
        return _problem(
            request,
            status_code=409,
            title="Result Not Ready",
            detail="Budget recommendation result is not available in current lifecycle state.",
            correlation_id=x_correlation_id,
            type_url=_PROBLEM_VALIDATION,
            code="RESULT_NOT_READY",
        )

    recommendation, synthesis = _coerce_result_payload(record)
    return BudgetRecommendationResponse(
        job_id=record.id,
        tenant_id=record.tenant_id,
        status=record.status.value,
        last_updated=record.updated_at,
        data_freshness_seconds=_freshness_seconds(record.updated_at),
        deterministic_recommendation=recommendation,
        llm_synthesis=synthesis,
    )


@router.post(
    "/api/budget/recommendations/{job_id}/approve",
    operation_id="approveBudgetRecommendation",
    response_model=BudgetMutationResponse,
)
async def approve_budget_recommendation(
    request: Request,
    response: Response,
    job_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: BudgetMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        job_id=job_id,
        action="approve",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )


@router.post(
    "/api/budget/recommendations/{job_id}/reject",
    operation_id="rejectBudgetRecommendation",
    response_model=BudgetMutationResponse,
)
async def reject_budget_recommendation(
    request: Request,
    response: Response,
    job_id: UUID,
    payload: BudgetMutationRequest,
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
        job_id=job_id,
        action="reject",
        reason=payload.reason,
        note=payload.note,
    )


@router.post(
    "/api/budget/recommendations/{job_id}/refine",
    operation_id="refineBudgetRecommendation",
    response_model=BudgetMutationResponse,
)
async def refine_budget_recommendation(
    request: Request,
    response: Response,
    job_id: UUID,
    payload: BudgetMutationRequest,
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
        job_id=job_id,
        action="refine",
        reason=payload.reason,
        note=payload.note,
    )


@router.post(
    "/api/budget/recommendations/{job_id}/rerun",
    operation_id="rerunBudgetRecommendation",
    response_model=BudgetMutationResponse,
)
async def rerun_budget_recommendation(
    request: Request,
    response: Response,
    job_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: BudgetMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        job_id=job_id,
        action="rerun",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )


@router.post(
    "/api/budget/recommendations/{job_id}/retry",
    operation_id="retryBudgetRecommendation",
    response_model=BudgetMutationResponse,
)
async def retry_budget_recommendation(
    request: Request,
    response: Response,
    job_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: BudgetMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        job_id=job_id,
        action="retry",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )


@router.post(
    "/api/budget/recommendations/{job_id}/cancel",
    operation_id="cancelBudgetRecommendation",
    response_model=BudgetMutationResponse,
)
async def cancel_budget_recommendation(
    request: Request,
    response: Response,
    job_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    x_idempotency_key: Annotated[UUID, Header(alias="X-Idempotency-Key")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    payload: BudgetMutationRequest | None = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    return await _mutation_response(
        request=request,
        response=response,
        db_session=db_session,
        auth_context=auth_context,
        x_correlation_id=x_correlation_id,
        x_idempotency_key=x_idempotency_key,
        job_id=job_id,
        action="cancel",
        reason=payload.reason if payload else None,
        note=payload.note if payload else None,
    )

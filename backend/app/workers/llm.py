"""
LLM workers routed through the provider choke point.

All provider execution, budget controls, breaker/timeout/cache, and llm_api_calls
persistence happen in app.llm.provider_boundary.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.provider_boundary import get_llm_provider_boundary
from app.models.llm import BudgetOptimizationJob, Investigation
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.llm_authority_contract import (
    build_budget_authority_payload,
    build_investigation_authority_payload,
)
from app.services.budget_job import BudgetJobService
from app.services.investigation import InvestigationService
from app.services.llm_validation_failures import LLMValidationFailureService

logger = logging.getLogger(__name__)

_PROVIDER_BOUNDARY = get_llm_provider_boundary()
_INVESTIGATION_SERVICE = InvestigationService()
_BUDGET_JOB_SERVICE = BudgetJobService()
_VALIDATION_FAILURE_SERVICE = LLMValidationFailureService()


def _stable_fallback_id(model: LLMTaskPayload, endpoint: str, label: str) -> str:
    payload = {
        "tenant_id": str(model.tenant_id),
        "user_id": str(model.user_id),
        "endpoint": endpoint,
        "correlation_id": model.correlation_id,
        "request_id": model.request_id,
    }
    seed = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{label}:{seed}".encode("utf-8")).hexdigest()
    return digest


def _resolve_request_id(model: LLMTaskPayload, endpoint: str) -> str:
    if model.request_id:
        return model.request_id
    if model.correlation_id:
        return model.correlation_id
    return _stable_fallback_id(model, endpoint, "request_id")


def _resolve_correlation_id(model: LLMTaskPayload, endpoint: str) -> str:
    if model.correlation_id:
        return model.correlation_id
    if model.request_id:
        return model.request_id
    return _stable_fallback_id(model, endpoint, "correlation_id")


def _normalize_payload_context(model: LLMTaskPayload, endpoint: str) -> LLMTaskPayload:
    return LLMTaskPayload.model_validate(
        {
            "tenant_id": model.tenant_id,
            "user_id": model.user_id,
            "correlation_id": _resolve_correlation_id(model, endpoint),
            "request_id": _resolve_request_id(model, endpoint),
            "prompt": model.prompt,
            "max_cost_cents": model.max_cost_cents,
        }
    )


def _trace_status_for_result(result_status: str) -> str:
    if result_status == "success":
        return "compute_succeeded"
    if result_status == "timeout":
        return "compute_timeout"
    if result_status == "cancelled":
        return "compute_cancelled"
    if result_status == "running":
        return "compute_running"
    if result_status == "pending":
        return "compute_pending"
    return "compute_failed"


async def route_request(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    endpoint = "app.tasks.llm.route"
    payload = _normalize_payload_context(model, endpoint)
    result = await _PROVIDER_BOUNDARY.complete(
        model=payload,
        session=session,
        endpoint=endpoint,
        force_failure=force_failure,
    )
    logger.info(
        "llm_route_boundary",
        extra={
            "tenant_id": str(payload.tenant_id),
            "correlation_id": payload.correlation_id,
            "event_type": "llm.route",
            "request_id": payload.request_id,
            "status": result.status,
        },
    )
    return {
        "status": "accepted" if result.status == "success" else result.status,
        "route": "noop",
        "request_id": payload.request_id,
        "correlation_id": payload.correlation_id,
        "api_call_id": str(result.api_call_id),
        "blocked_reason": result.block_reason,
        "failure_reason": result.failure_reason,
        "was_cached": result.was_cached,
    }


async def generate_explanation(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    endpoint = "app.tasks.llm.explanation"
    payload = _normalize_payload_context(model, endpoint)
    result = await _PROVIDER_BOUNDARY.complete(
        model=payload,
        session=session,
        endpoint=endpoint,
        force_failure=force_failure,
    )
    logger.info(
        "llm_explanation_boundary",
        extra={
            "tenant_id": str(payload.tenant_id),
            "correlation_id": payload.correlation_id,
            "event_type": "llm.explanation",
            "request_id": payload.request_id,
            "status": result.status,
        },
    )
    explanation = result.output_text if result.status == "success" else "not-available"
    return {
        "status": "accepted" if result.status == "success" else result.status,
        "explanation": explanation,
        "request_id": payload.request_id,
        "correlation_id": payload.correlation_id,
        "api_call_id": str(result.api_call_id),
        "blocked_reason": result.block_reason,
        "failure_reason": result.failure_reason,
        "was_cached": result.was_cached,
    }


async def run_investigation(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    endpoint = "app.tasks.llm.investigation"
    payload = _normalize_payload_context(model, endpoint)
    authority_job = await _INVESTIGATION_SERVICE.get_or_create_job(
        session,
        tenant_id=payload.tenant_id,
        request_id=payload.request_id,
        correlation_id=payload.correlation_id,
    )
    await _INVESTIGATION_SERVICE.mark_investigating(
        session,
        tenant_id=payload.tenant_id,
        job_id=authority_job.id,
    )
    result = await _PROVIDER_BOUNDARY.complete(
        model=payload,
        session=session,
        endpoint=endpoint,
        force_failure=force_failure,
    )
    query = f"provider:{payload.request_id}"
    trace_status = _trace_status_for_result(result.status)
    existing = (
        await session.execute(
            select(Investigation.id).where(
                Investigation.tenant_id == payload.tenant_id,
                Investigation.request_id == payload.request_id,
            )
        )
    ).scalar_one_or_none()
    internal_trace_id = existing
    if existing is None:
        investigation = Investigation(
            tenant_id=payload.tenant_id,
            query=query,
            request_id=payload.request_id,
            authority_job_id=authority_job.id,
            lifecycle_role="internal_trace",
            status=trace_status,
            result={
                "status": trace_status,
                "request_id": payload.request_id,
                "summary": result.output_text,
            },
            cost_cents=int(result.usage.get("cost_cents", 0)),
        )
        session.add(investigation)
        await session.flush()
        internal_trace_id = investigation.id
    else:
        trace_row = await session.get(Investigation, existing)
        if trace_row is not None:
            trace_row.query = query
            trace_row.request_id = payload.request_id
            trace_row.authority_job_id = authority_job.id
            trace_row.lifecycle_role = "internal_trace"
            trace_row.status = trace_status
            trace_row.result = {
                "status": trace_status,
                "request_id": payload.request_id,
                "summary": result.output_text,
            }
            trace_row.cost_cents = int(result.usage.get("cost_cents", 0))

    effective_status = result.status
    effective_failure_reason = result.failure_reason
    if result.status == "success":
        try:
            authority_payload = build_investigation_authority_payload(
                request_id=payload.request_id,
                correlation_id=payload.correlation_id,
                authority_job_id=authority_job.id,
                provider_summary=result.output_text,
                model_name=result.model,
            )
            await _INVESTIGATION_SERVICE.mark_ready_for_review(
                session,
                tenant_id=payload.tenant_id,
                job_id=authority_job.id,
                result_payload=authority_payload.model_dump(mode="json"),
            )
        except Exception as exc:  # pragma: no cover - defensive fail-closed path
            validation_error = f"authority_contract_build_failed:{type(exc).__name__}"
            await _VALIDATION_FAILURE_SERVICE.record_failure(
                session,
                tenant_id=payload.tenant_id,
                endpoint=endpoint,
                validation_error=validation_error,
                request_payload={
                    "request_id": payload.request_id,
                    "correlation_id": payload.correlation_id,
                    "prompt": payload.prompt,
                },
                response_payload={
                    "provider": result.provider,
                    "model": result.model,
                    "output_text": result.output_text,
                },
            )
            await _INVESTIGATION_SERVICE.fail_job(
                session,
                tenant_id=payload.tenant_id,
                job_id=authority_job.id,
                failure_code="validation_failed",
                failure_reason=validation_error,
            )
            trace_row = (
                await session.get(Investigation, internal_trace_id)
                if internal_trace_id is not None
                else None
            )
            if trace_row is not None:
                trace_row.status = "compute_failed"
                trace_row.result = {
                    "status": "compute_failed",
                    "request_id": payload.request_id,
                    "summary": result.output_text,
                    "failure_reason": validation_error,
                }
            effective_status = "failed"
            effective_failure_reason = validation_error
    elif result.status == "timeout":
        await _INVESTIGATION_SERVICE.timeout_job(
            session,
            tenant_id=payload.tenant_id,
            job_id=authority_job.id,
            failure_reason=result.failure_reason or "provider_timeout",
        )
    else:
        await _INVESTIGATION_SERVICE.fail_job(
            session,
            tenant_id=payload.tenant_id,
            job_id=authority_job.id,
            failure_code=result.status,
            failure_reason=result.failure_reason or result.block_reason or "provider_failed",
        )

    logger.info(
        "llm_investigation_boundary",
        extra={
            "tenant_id": str(payload.tenant_id),
            "correlation_id": payload.correlation_id,
            "event_type": "llm.investigation",
            "request_id": payload.request_id,
            "status": effective_status,
        },
    )
    return {
        "status": "accepted" if effective_status == "success" else effective_status,
        "investigation": "queued" if effective_status == "success" else "blocked",
        "request_id": payload.request_id,
        "correlation_id": payload.correlation_id,
        "api_call_id": str(result.api_call_id),
        "investigation_id": str(authority_job.id),
        "investigation_trace_id": str(internal_trace_id) if internal_trace_id else None,
        "blocked_reason": result.block_reason,
        "failure_reason": effective_failure_reason,
        "was_cached": result.was_cached,
    }


async def optimize_budget(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    endpoint = "app.tasks.llm.budget_optimization"
    payload = _normalize_payload_context(model, endpoint)
    authority_job = await _BUDGET_JOB_SERVICE.get_or_create_job(
        session,
        tenant_id=payload.tenant_id,
        request_id=payload.request_id,
        correlation_id=payload.correlation_id,
    )
    await _BUDGET_JOB_SERVICE.mark_investigating(
        session,
        tenant_id=payload.tenant_id,
        job_id=authority_job.id,
    )
    result = await _PROVIDER_BOUNDARY.complete(
        model=payload,
        session=session,
        endpoint=endpoint,
        force_failure=force_failure,
    )
    trace_status = _trace_status_for_result(result.status)
    existing = (
        await session.execute(
            select(BudgetOptimizationJob.id).where(
                BudgetOptimizationJob.tenant_id == payload.tenant_id,
                BudgetOptimizationJob.request_id == payload.request_id,
            )
        )
    ).scalar_one_or_none()
    internal_trace_id = existing
    if existing is None:
        job = BudgetOptimizationJob(
            tenant_id=payload.tenant_id,
            request_id=payload.request_id,
            authority_job_id=authority_job.id,
            lifecycle_role="internal_trace",
            status=trace_status,
            recommendations={
                "request_id": payload.request_id,
                "provider_summary": result.output_text,
                "status": trace_status,
            },
            cost_cents=int(result.usage.get("cost_cents", 0)),
        )
        session.add(job)
        await session.flush()
        internal_trace_id = job.id
    else:
        trace_row = await session.get(BudgetOptimizationJob, existing)
        if trace_row is not None:
            trace_row.request_id = payload.request_id
            trace_row.authority_job_id = authority_job.id
            trace_row.lifecycle_role = "internal_trace"
            trace_row.status = trace_status
            trace_row.recommendations = {
                "request_id": payload.request_id,
                "provider_summary": result.output_text,
                "status": trace_status,
            }
            trace_row.cost_cents = int(result.usage.get("cost_cents", 0))

    effective_status = result.status
    effective_failure_reason = result.failure_reason
    if result.status == "success":
        try:
            optimization_goal = str(
                payload.prompt.get("optimization_goal", "maximize_roas")
            )
            authority_payload = build_budget_authority_payload(
                request_id=payload.request_id,
                correlation_id=payload.correlation_id,
                authority_job_id=authority_job.id,
                provider_summary=result.output_text,
                model_name=result.model,
                optimization_goal=optimization_goal,
            )
            await _BUDGET_JOB_SERVICE.mark_ready_for_review(
                session,
                tenant_id=payload.tenant_id,
                job_id=authority_job.id,
                result_payload=authority_payload.model_dump(mode="json"),
            )
        except Exception as exc:  # pragma: no cover - defensive fail-closed path
            validation_error = f"authority_contract_build_failed:{type(exc).__name__}"
            await _VALIDATION_FAILURE_SERVICE.record_failure(
                session,
                tenant_id=payload.tenant_id,
                endpoint=endpoint,
                validation_error=validation_error,
                request_payload={
                    "request_id": payload.request_id,
                    "correlation_id": payload.correlation_id,
                    "prompt": payload.prompt,
                },
                response_payload={
                    "provider": result.provider,
                    "model": result.model,
                    "output_text": result.output_text,
                },
            )
            await _BUDGET_JOB_SERVICE.fail_job(
                session,
                tenant_id=payload.tenant_id,
                job_id=authority_job.id,
                failure_code="validation_failed",
                failure_reason=validation_error,
            )
            trace_row = (
                await session.get(BudgetOptimizationJob, internal_trace_id)
                if internal_trace_id is not None
                else None
            )
            if trace_row is not None:
                trace_row.status = "compute_failed"
                trace_row.recommendations = {
                    "status": "compute_failed",
                    "request_id": payload.request_id,
                    "provider_summary": result.output_text,
                    "failure_reason": validation_error,
                }
            effective_status = "failed"
            effective_failure_reason = validation_error
    elif result.status == "timeout":
        await _BUDGET_JOB_SERVICE.timeout_job(
            session,
            tenant_id=payload.tenant_id,
            job_id=authority_job.id,
            failure_reason=result.failure_reason or "provider_timeout",
        )
    else:
        await _BUDGET_JOB_SERVICE.fail_job(
            session,
            tenant_id=payload.tenant_id,
            job_id=authority_job.id,
            failure_code=result.status,
            failure_reason=result.failure_reason or result.block_reason or "provider_failed",
        )

    logger.info(
        "llm_budget_boundary",
        extra={
            "tenant_id": str(payload.tenant_id),
            "correlation_id": payload.correlation_id,
            "event_type": "llm.budget_optimization",
            "request_id": payload.request_id,
            "status": effective_status,
        },
    )
    return {
        "status": "accepted" if effective_status == "success" else effective_status,
        "budget_action": "noop" if effective_status == "success" else "blocked",
        "request_id": payload.request_id,
        "correlation_id": payload.correlation_id,
        "api_call_id": str(result.api_call_id),
        "budget_job_id": str(authority_job.id),
        "budget_trace_id": str(internal_trace_id) if internal_trace_id else None,
        "blocked_reason": result.block_reason,
        "failure_reason": effective_failure_reason,
        "was_cached": result.was_cached,
    }

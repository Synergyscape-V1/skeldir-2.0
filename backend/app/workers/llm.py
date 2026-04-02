"""
LLM workers routed through the provider choke point.

All provider execution, budget controls, breaker/timeout/cache, and llm_api_calls
persistence happen in app.llm.provider_boundary.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.authority_contract import ValidationContext
from app.llm.output_validation import validation_spec_for_endpoint
from app.llm.provider_boundary import get_llm_provider_boundary
from app.models.llm import BudgetOptimizationJob, Investigation
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.llm_authority_contract import (
    build_budget_authority_payload,
    build_investigation_authority_payload,
    build_validation_context,
)
from app.services.budget_job import BudgetJobService
from app.services.investigation import InvestigationService
from app.services.llm_validation_failures import LLMValidationFailureService

logger = logging.getLogger(__name__)

_PROVIDER_BOUNDARY = get_llm_provider_boundary()
_INVESTIGATION_SERVICE = InvestigationService()
_BUDGET_JOB_SERVICE = BudgetJobService()
_VALIDATION_FAILURE_SERVICE = LLMValidationFailureService()
_ENDPOINT_VALIDATION_SPECS = {
    endpoint: validation_spec_for_endpoint(endpoint)
    for endpoint in (
        "app.tasks.llm.route",
        "app.tasks.llm.explanation",
        "app.tasks.llm.investigation",
        "app.tasks.llm.budget_optimization",
    )
}


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


def _validation_spec(endpoint: str):
    spec = _ENDPOINT_VALIDATION_SPECS.get(endpoint)
    if spec is None:
        raise RuntimeError(f"missing_validation_spec:{endpoint}")
    return spec


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


def _coerce_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip().replace(",", "")
        if not candidate:
            return None
        try:
            return float(candidate)
        except ValueError:
            return None
    return None


def _numeric_claim_bindings_from_prompt(
    prompt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw = prompt.get("numeric_claim_bindings")
    if not isinstance(raw, list):
        return []
    bindings: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        claim_path = entry.get("claim_path")
        truth_path = entry.get("truth_path")
        if not isinstance(claim_path, str) or not claim_path.strip():
            continue
        if not isinstance(truth_path, str) or not truth_path.strip():
            continue
        binding: dict[str, Any] = {
            "claim_path": claim_path.strip(),
            "truth_path": truth_path.strip(),
        }
        tolerance = _coerce_numeric(entry.get("tolerance_ratio"))
        if tolerance is not None:
            binding["tolerance_ratio"] = max(0.0, min(1.0, tolerance))
        bindings.append(binding)
    return bindings


def _build_numeric_validation_context(
    *,
    payload: LLMTaskPayload,
    feature_surface: str,
    deterministic_truth: dict[str, Any],
    deterministic_truth_sources: list[str],
) -> ValidationContext:
    prompt = payload.prompt if isinstance(payload.prompt, Mapping) else {}
    merged_truth = dict(deterministic_truth)
    prompt_truth = prompt.get("deterministic_truth")
    if isinstance(prompt_truth, Mapping):
        for key, value in prompt_truth.items():
            if isinstance(key, str) and key:
                merged_truth[key] = value
    numeric_claim_bindings = _numeric_claim_bindings_from_prompt(prompt)
    tolerance = _coerce_numeric(prompt.get("numeric_tolerance_ratio"))
    tolerance_ratio = 0.05 if tolerance is None else max(0.0, min(1.0, tolerance))
    return build_validation_context(
        feature_surface=feature_surface,
        request_id=payload.request_id,
        correlation_id=payload.correlation_id,
        deterministic_truth=merged_truth,
        deterministic_truth_sources=deterministic_truth_sources,
        numeric_claim_bindings=numeric_claim_bindings,
        numeric_tolerance_ratio=tolerance_ratio,
    )


def _audit_provider_summary(result: Any) -> str:
    metadata = (
        result.response_metadata
        if isinstance(result.response_metadata, Mapping)
        else {}
    )
    raw_output_text = metadata.get("raw_output_text")
    if isinstance(raw_output_text, str) and raw_output_text.strip():
        return raw_output_text.strip()
    if isinstance(result.output_text, str):
        return result.output_text
    return ""


def _validated_summary_or_empty(result: Any) -> str:
    if getattr(result, "status", None) != "success":
        return ""
    if str(getattr(result, "validation_code", "success") or "success") != "success":
        return ""
    output_text = getattr(result, "output_text", "")
    return str(output_text or "")


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
        validation_spec=_validation_spec(endpoint),
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
        "validation_code": result.validation_code,
        "validation_stage": result.validation_stage,
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
        validation_spec=_validation_spec(endpoint),
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
        "validation_code": result.validation_code,
        "validation_stage": result.validation_stage,
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
    validation_context = _build_numeric_validation_context(
        payload=payload,
        feature_surface="investigation",
        deterministic_truth={
            "authority_status": 1,
            "authority_job_id": str(authority_job.id),
        },
        deterministic_truth_sources=["investigation_jobs"],
    )
    result = await _PROVIDER_BOUNDARY.complete(
        model=payload,
        session=session,
        endpoint=endpoint,
        force_failure=force_failure,
        validation_spec=_validation_spec(endpoint),
        validation_context=validation_context.model_dump(mode="json"),
    )
    validated_summary = _validated_summary_or_empty(result)
    query = f"provider:{payload.request_id}"
    numeric_authority_rejected = result.failure_reason == "validation_numeric_mismatch"
    trace_status = (
        "compute_succeeded"
        if numeric_authority_rejected
        else _trace_status_for_result(result.status)
    )
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
                "summary": validated_summary,
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
                "summary": validated_summary,
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
                observed_at=authority_job.updated_at,
                provider_summary=validated_summary,
                model_name=result.model,
                validation_context=validation_context,
                synthesis_validation_state="validated",
            )
            await _INVESTIGATION_SERVICE.mark_ready_for_review(
                session,
                tenant_id=payload.tenant_id,
                job_id=authority_job.id,
                result_payload=authority_payload.model_dump(mode="json"),
            )
        except Exception as exc:  # pragma: no cover - defensive fail-closed path
            validation_error = f"authority_contract_build_failed:{type(exc).__name__}"
            sink_outcome = await _VALIDATION_FAILURE_SERVICE.record_failure_best_effort(
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
            if sink_outcome.is_degraded:
                logger.warning(
                    "llm_validation_failure_sink_write_degraded",
                    extra={
                        "tenant_id": str(payload.tenant_id),
                        "correlation_id": payload.correlation_id,
                        "event_type": "llm.validation_failure_sink_degraded",
                        "endpoint": endpoint,
                        "request_id": payload.request_id,
                        "degraded_reason": sink_outcome.degraded_reason,
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
                    "summary": validated_summary,
                    "failure_reason": validation_error,
                }
            effective_status = "failed"
            effective_failure_reason = validation_error
    elif numeric_authority_rejected:
        authority_payload = build_investigation_authority_payload(
            request_id=payload.request_id,
            correlation_id=payload.correlation_id,
            authority_job_id=authority_job.id,
            observed_at=authority_job.updated_at,
            provider_summary="Synthesis rejected: numeric claims did not match deterministic authority.",
            model_name=result.model,
            validation_context=validation_context,
            synthesis_validation_state="rejected",
            synthesis_caveats=[
                "Synthesis is explanatory only and cannot override deterministic findings.",
                "Synthesis was rejected because numeric claims failed deterministic authority validation.",
            ],
            rejection_reason="validation_numeric_mismatch",
            audit_provider_summary_raw=_audit_provider_summary(result),
        )
        await _INVESTIGATION_SERVICE.mark_ready_for_review(
            session,
            tenant_id=payload.tenant_id,
            job_id=authority_job.id,
            result_payload=authority_payload.model_dump(mode="json"),
        )
        effective_status = "success"
        effective_failure_reason = None
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
            failure_reason=result.failure_reason
            or result.block_reason
            or "provider_failed",
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
        "validation_code": result.validation_code,
        "validation_stage": result.validation_stage,
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
    optimization_goal = str(payload.prompt.get("optimization_goal", "maximize_roas"))
    validation_context = _build_numeric_validation_context(
        payload=payload,
        feature_surface="budget",
        deterministic_truth={
            "authority_status": 1,
            "authority_job_id": str(authority_job.id),
            "optimization_goal": optimization_goal,
        },
        deterministic_truth_sources=["budget_jobs"],
    )
    result = await _PROVIDER_BOUNDARY.complete(
        model=payload,
        session=session,
        endpoint=endpoint,
        force_failure=force_failure,
        validation_spec=_validation_spec(endpoint),
        validation_context=validation_context.model_dump(mode="json"),
    )
    validated_summary = _validated_summary_or_empty(result)
    numeric_authority_rejected = result.failure_reason == "validation_numeric_mismatch"
    trace_status = (
        "compute_succeeded"
        if numeric_authority_rejected
        else _trace_status_for_result(result.status)
    )
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
                "provider_summary": validated_summary,
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
                "provider_summary": validated_summary,
                "status": trace_status,
            }
            trace_row.cost_cents = int(result.usage.get("cost_cents", 0))

    effective_status = result.status
    effective_failure_reason = result.failure_reason
    if result.status == "success":
        try:
            authority_payload = build_budget_authority_payload(
                request_id=payload.request_id,
                correlation_id=payload.correlation_id,
                authority_job_id=authority_job.id,
                observed_at=authority_job.updated_at,
                provider_summary=validated_summary,
                model_name=result.model,
                optimization_goal=optimization_goal,
                validation_context=validation_context,
                synthesis_validation_state="validated",
            )
            await _BUDGET_JOB_SERVICE.mark_ready_for_review(
                session,
                tenant_id=payload.tenant_id,
                job_id=authority_job.id,
                result_payload=authority_payload.model_dump(mode="json"),
            )
        except Exception as exc:  # pragma: no cover - defensive fail-closed path
            validation_error = f"authority_contract_build_failed:{type(exc).__name__}"
            sink_outcome = await _VALIDATION_FAILURE_SERVICE.record_failure_best_effort(
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
            if sink_outcome.is_degraded:
                logger.warning(
                    "llm_validation_failure_sink_write_degraded",
                    extra={
                        "tenant_id": str(payload.tenant_id),
                        "correlation_id": payload.correlation_id,
                        "event_type": "llm.validation_failure_sink_degraded",
                        "endpoint": endpoint,
                        "request_id": payload.request_id,
                        "degraded_reason": sink_outcome.degraded_reason,
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
                    "provider_summary": validated_summary,
                    "failure_reason": validation_error,
                }
            effective_status = "failed"
            effective_failure_reason = validation_error
    elif numeric_authority_rejected:
        authority_payload = build_budget_authority_payload(
            request_id=payload.request_id,
            correlation_id=payload.correlation_id,
            authority_job_id=authority_job.id,
            observed_at=authority_job.updated_at,
            provider_summary="Synthesis rejected: numeric claims did not match deterministic authority.",
            model_name=result.model,
            optimization_goal=optimization_goal,
            validation_context=validation_context,
            synthesis_validation_state="rejected",
            synthesis_caveats=[
                "Synthesis is explanatory only and cannot override deterministic recommendation fields.",
                "Synthesis was rejected because numeric claims failed deterministic authority validation.",
            ],
            rejection_reason="validation_numeric_mismatch",
            audit_provider_summary_raw=_audit_provider_summary(result),
        )
        await _BUDGET_JOB_SERVICE.mark_ready_for_review(
            session,
            tenant_id=payload.tenant_id,
            job_id=authority_job.id,
            result_payload=authority_payload.model_dump(mode="json"),
        )
        effective_status = "success"
        effective_failure_reason = None
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
            failure_reason=result.failure_reason
            or result.block_reason
            or "provider_failed",
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
        "validation_code": result.validation_code,
        "validation_stage": result.validation_stage,
    }

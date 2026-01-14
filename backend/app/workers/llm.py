"""
Deterministic LLM worker stubs with audit writes.

These workers write tenant-scoped records with cost=0 and never call providers.
"""

from __future__ import annotations

import logging
from datetime import date
import hashlib
import json
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import Integer, Text, cast, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import (
    BudgetOptimizationJob,
    Investigation,
    LLMApiCall,
    LLMMonthlyCost,
)
from app.schemas.llm_payloads import LLMTaskPayload

logger = logging.getLogger(__name__)

_STUB_MODEL = "llm_stub"


def _stable_fallback_id(model: LLMTaskPayload, endpoint: str, label: str) -> str:
    payload = {
        "tenant_id": str(model.tenant_id),
        "endpoint": endpoint,
        "correlation_id": model.correlation_id,
        "request_id": model.request_id,
        "prompt": model.prompt,
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


def _month_start_utc() -> date:
    return date(1970, 1, 1)


async def _claim_api_call(
    session: AsyncSession,
    *,
    model: LLMTaskPayload,
    endpoint: str,
    request_id: str,
    correlation_id: str,
) -> tuple[UUID, bool]:
    insert_stmt = (
        insert(LLMApiCall)
        .values(
            tenant_id=model.tenant_id,
            endpoint=endpoint,
            request_id=request_id,
            model=_STUB_MODEL,
            input_tokens=0,
            output_tokens=0,
            cost_cents=0,
            latency_ms=0,
            was_cached=False,
            request_metadata={
                "stubbed": True,
                "request_id": request_id,
                "correlation_id": correlation_id,
            },
        )
        .on_conflict_do_nothing(
            index_elements=["tenant_id", "request_id", "endpoint"]
        )
        .returning(LLMApiCall.id)
    )
    result = await session.execute(insert_stmt)
    inserted_id = result.scalar_one_or_none()
    if inserted_id is not None:
        return inserted_id, True

    existing_id = (
        await session.execute(
            select(LLMApiCall.id).where(
                LLMApiCall.tenant_id == model.tenant_id,
                LLMApiCall.request_id == request_id,
                LLMApiCall.endpoint == endpoint,
            )
        )
    ).scalar_one_or_none()
    if existing_id is None:
        raise RuntimeError("idempotency guard failed to locate existing llm_api_calls row")
    return existing_id, False


def _build_model_breakdown_update(
    *,
    model_label: str,
    cost_cents: int,
    calls: int,
):
    base_breakdown = func.coalesce(LLMMonthlyCost.model_breakdown, cast("{}", JSONB))
    existing_calls = func.coalesce(
        cast(func.jsonb_extract_path_text(base_breakdown, model_label, "calls"), Integer),
        0,
    )
    existing_cost = func.coalesce(
        cast(func.jsonb_extract_path_text(base_breakdown, model_label, "cost_cents"), Integer),
        0,
    )
    new_entry = func.jsonb_build_object(
        "calls",
        existing_calls + literal(calls),
        "cost_cents",
        existing_cost + literal(cost_cents),
    )
    path = cast([model_label], ARRAY(Text))
    return func.jsonb_set(base_breakdown, path, new_entry, True)


async def record_monthly_costs(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_label: str,
    cost_cents: int,
    calls: int,
) -> None:
    month = _month_start_utc()
    insert_stmt = (
        insert(LLMMonthlyCost)
        .values(
            tenant_id=tenant_id,
            month=month,
            total_cost_cents=cost_cents,
            total_calls=calls,
            model_breakdown={model_label: {"calls": calls, "cost_cents": cost_cents}},
        )
    )
    excluded = insert_stmt.excluded
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["tenant_id", "month"],
        set_={
            "total_cost_cents": LLMMonthlyCost.total_cost_cents + excluded.total_cost_cents,
            "total_calls": LLMMonthlyCost.total_calls + excluded.total_calls,
            "model_breakdown": _build_model_breakdown_update(
                model_label=model_label,
                cost_cents=cost_cents,
                calls=calls,
            ),
        },
    )
    await session.execute(stmt)


async def route_request(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model, "app.tasks.llm.route")
    correlation_id = _resolve_correlation_id(model, "app.tasks.llm.route")
    async with session.begin_nested():
        api_call_id, claimed = await _claim_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.route",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        if not claimed:
            return {
                "status": "accepted",
                "route": "noop",
                "request_id": request_id,
                "correlation_id": correlation_id,
                "api_call_id": str(api_call_id),
            }
        if force_failure:
            raise RuntimeError("forced failure after api call")
        await record_monthly_costs(
            session,
            tenant_id=model.tenant_id,
            model_label=_STUB_MODEL,
            cost_cents=0,
            calls=1,
        )

    logger.info(
        "llm_route_stubbed",
        extra={
            "tenant_id": str(model.tenant_id),
            "correlation_id": correlation_id,
            "event_type": "llm.route",
            "request_id": request_id,
        },
    )

    return {
        "status": "accepted",
        "route": "noop",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "api_call_id": str(api_call_id),
    }


async def generate_explanation(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model, "app.tasks.llm.explanation")
    correlation_id = _resolve_correlation_id(model, "app.tasks.llm.explanation")
    async with session.begin_nested():
        api_call_id, claimed = await _claim_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.explanation",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        if not claimed:
            return {
                "status": "accepted",
                "explanation": "not-implemented",
                "request_id": request_id,
                "correlation_id": correlation_id,
                "api_call_id": str(api_call_id),
            }
        if force_failure:
            raise RuntimeError("forced failure after api call")
        await record_monthly_costs(
            session,
            tenant_id=model.tenant_id,
            model_label=_STUB_MODEL,
            cost_cents=0,
            calls=1,
        )

    logger.info(
        "llm_explanation_stubbed",
        extra={
            "tenant_id": str(model.tenant_id),
            "correlation_id": correlation_id,
            "event_type": "llm.explanation",
            "request_id": request_id,
        },
    )

    return {
        "status": "accepted",
        "explanation": "not-implemented",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "api_call_id": str(api_call_id),
    }


async def run_investigation(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model, "app.tasks.llm.investigation")
    correlation_id = _resolve_correlation_id(model, "app.tasks.llm.investigation")
    async with session.begin_nested():
        api_call_id, claimed = await _claim_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.investigation",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        if not claimed:
            existing_id = (
                await session.execute(
                    select(Investigation.id).where(
                        Investigation.tenant_id == model.tenant_id,
                        Investigation.query == f"stubbed:{request_id}",
                    )
                )
            ).scalar_one_or_none()
            return {
                "status": "accepted",
                "investigation": "queued",
                "request_id": request_id,
                "correlation_id": correlation_id,
                "api_call_id": str(api_call_id),
                "investigation_id": str(existing_id) if existing_id else None,
            }
        if force_failure:
            raise RuntimeError("forced failure after api call")
        investigation = Investigation(
            tenant_id=model.tenant_id,
            query=f"stubbed:{request_id}",
            status="completed",
            result={"status": "stubbed", "request_id": request_id},
            cost_cents=0,
        )
        session.add(investigation)
        await session.flush()
        await record_monthly_costs(
            session,
            tenant_id=model.tenant_id,
            model_label=_STUB_MODEL,
            cost_cents=0,
            calls=1,
        )

    logger.info(
        "llm_investigation_stubbed",
        extra={
            "tenant_id": str(model.tenant_id),
            "correlation_id": correlation_id,
            "event_type": "llm.investigation",
            "request_id": request_id,
        },
    )

    return {
        "status": "accepted",
        "investigation": "queued",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "api_call_id": str(api_call_id),
        "investigation_id": str(investigation.id),
    }


async def optimize_budget(
    model: LLMTaskPayload,
    session: AsyncSession,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model, "app.tasks.llm.budget_optimization")
    correlation_id = _resolve_correlation_id(model, "app.tasks.llm.budget_optimization")
    async with session.begin_nested():
        api_call_id, claimed = await _claim_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.budget_optimization",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        if not claimed:
            existing_id = (
                await session.execute(
                    select(BudgetOptimizationJob.id).where(
                        BudgetOptimizationJob.tenant_id == model.tenant_id,
                        BudgetOptimizationJob.recommendations["request_id"].astext == request_id,
                    )
                )
            ).scalar_one_or_none()
            return {
                "status": "accepted",
                "budget_action": "noop",
                "request_id": request_id,
                "correlation_id": correlation_id,
                "api_call_id": str(api_call_id),
                "budget_job_id": str(existing_id) if existing_id else None,
            }
        if force_failure:
            raise RuntimeError("forced failure after api call")
        job = BudgetOptimizationJob(
            tenant_id=model.tenant_id,
            status="completed",
            recommendations={"status": "stubbed", "request_id": request_id},
            cost_cents=0,
        )
        session.add(job)
        await session.flush()
        await record_monthly_costs(
            session,
            tenant_id=model.tenant_id,
            model_label=_STUB_MODEL,
            cost_cents=0,
            calls=1,
        )

    logger.info(
        "llm_budget_stubbed",
        extra={
            "tenant_id": str(model.tenant_id),
            "correlation_id": correlation_id,
            "event_type": "llm.budget_optimization",
            "request_id": request_id,
        },
    )

    return {
        "status": "accepted",
        "budget_action": "noop",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "api_call_id": str(api_call_id),
        "budget_job_id": str(job.id),
    }

"""
Deterministic LLM worker stubs with audit writes.

These workers write tenant-scoped records with cost=0 and never call providers.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

from sqlalchemy import Integer, Text, cast, func, literal
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.llm import (
    BudgetOptimizationJob,
    Investigation,
    LLMApiCall,
    LLMMonthlyCost,
)
from app.schemas.llm_payloads import LLMTaskPayload

logger = logging.getLogger(__name__)

_STUB_MODEL = "llm_stub"


def _resolve_request_id(model: LLMTaskPayload) -> str:
    return model.request_id or str(uuid4())


def _resolve_correlation_id(model: LLMTaskPayload) -> str:
    return model.correlation_id or str(uuid4())


def _month_start_utc() -> date:
    now = datetime.now(timezone.utc)
    return date(now.year, now.month, 1)


async def _record_api_call(
    session: AsyncSession,
    *,
    model: LLMTaskPayload,
    endpoint: str,
    request_id: str,
    correlation_id: str,
) -> LLMApiCall:
    api_call = LLMApiCall(
        tenant_id=model.tenant_id,
        endpoint=endpoint,
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
    session.add(api_call)
    await session.flush()
    return api_call


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
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        async with session.begin_nested():
            api_call = await _record_api_call(
                session,
                model=model,
                endpoint="app.tasks.llm.route",
                request_id=request_id,
                correlation_id=correlation_id,
            )
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
        "api_call_id": str(api_call.id),
    }


async def generate_explanation(
    model: LLMTaskPayload,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        async with session.begin_nested():
            api_call = await _record_api_call(
                session,
                model=model,
                endpoint="app.tasks.llm.explanation",
                request_id=request_id,
                correlation_id=correlation_id,
            )
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
        "api_call_id": str(api_call.id),
    }


async def run_investigation(
    model: LLMTaskPayload,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        async with session.begin_nested():
            api_call = await _record_api_call(
                session,
                model=model,
                endpoint="app.tasks.llm.investigation",
                request_id=request_id,
                correlation_id=correlation_id,
            )
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
        "api_call_id": str(api_call.id),
        "investigation_id": str(investigation.id),
    }


async def optimize_budget(
    model: LLMTaskPayload,
    *,
    force_failure: bool = False,
) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        async with session.begin_nested():
            api_call = await _record_api_call(
                session,
                model=model,
                endpoint="app.tasks.llm.budget_optimization",
                request_id=request_id,
                correlation_id=correlation_id,
            )
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
        "api_call_id": str(api_call.id),
        "budget_job_id": str(job.id),
    }

"""
Deterministic LLM worker stubs with audit writes.

These workers write tenant-scoped records with cost=0 and never call providers.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert
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


async def _ensure_monthly_costs(
    session: AsyncSession,
    *,
    tenant_id: UUID,
) -> None:
    month = _month_start_utc()
    stmt = (
        insert(LLMMonthlyCost)
        .values(
            tenant_id=tenant_id,
            month=month,
            total_cost_cents=0,
            total_calls=1,
            model_breakdown={"stubbed": {"calls": 1, "cost_cents": 0}},
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "month"])
    )
    await session.execute(stmt)


async def route_request(model: LLMTaskPayload) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        api_call = await _record_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.route",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        await _ensure_monthly_costs(session, tenant_id=model.tenant_id)

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


async def generate_explanation(model: LLMTaskPayload) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        api_call = await _record_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.explanation",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        await _ensure_monthly_costs(session, tenant_id=model.tenant_id)

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


async def run_investigation(model: LLMTaskPayload) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        api_call = await _record_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.investigation",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        investigation = Investigation(
            tenant_id=model.tenant_id,
            query=f"stubbed:{request_id}",
            status="completed",
            result={"status": "stubbed", "request_id": request_id},
            cost_cents=0,
        )
        session.add(investigation)
        await session.flush()
        await _ensure_monthly_costs(session, tenant_id=model.tenant_id)

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


async def optimize_budget(model: LLMTaskPayload) -> Dict[str, Any]:
    request_id = _resolve_request_id(model)
    correlation_id = _resolve_correlation_id(model)
    async with get_session(tenant_id=model.tenant_id) as session:
        api_call = await _record_api_call(
            session,
            model=model,
            endpoint="app.tasks.llm.budget_optimization",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        job = BudgetOptimizationJob(
            tenant_id=model.tenant_id,
            status="completed",
            recommendations={"status": "stubbed", "request_id": request_id},
            cost_cents=0,
        )
        session.add(job)
        await session.flush()
        await _ensure_monthly_costs(session, tenant_id=model.tenant_id)

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

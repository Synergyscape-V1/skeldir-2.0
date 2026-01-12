from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db.session import get_session
from app.models.llm import BudgetOptimizationJob, Investigation, LLMApiCall, LLMMonthlyCost
from app.schemas.llm_payloads import LLMTaskPayload
from app.workers.llm import generate_explanation, optimize_budget, route_request, run_investigation


def _build_payload(tenant_id: UUID) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        correlation_id=str(uuid4()),
        prompt={"stub": True},
        max_cost_cents=0,
    )


@pytest.mark.asyncio
async def test_llm_route_stub_writes_audit_rows(test_tenant):
    payload = _build_payload(test_tenant)
    result = await route_request(payload)

    async with get_session(tenant_id=test_tenant) as session:
        api_call = await session.get(LLMApiCall, UUID(result["api_call_id"]))
        assert api_call is not None
        assert api_call.tenant_id == test_tenant
        assert api_call.cost_cents == 0

        monthly = (
            await session.execute(
                select(LLMMonthlyCost).where(LLMMonthlyCost.tenant_id == test_tenant)
            )
        ).scalars().all()
        assert monthly, "Expected llm_monthly_costs row for tenant"
        assert monthly[0].total_cost_cents == 0


@pytest.mark.asyncio
async def test_llm_investigation_stub_writes_job(test_tenant):
    payload = _build_payload(test_tenant)
    result = await run_investigation(payload)

    async with get_session(tenant_id=test_tenant) as session:
        investigation = await session.get(Investigation, UUID(result["investigation_id"]))
        assert investigation is not None
        assert investigation.status == "completed"
        assert investigation.cost_cents == 0


@pytest.mark.asyncio
async def test_llm_budget_stub_writes_job(test_tenant):
    payload = _build_payload(test_tenant)
    result = await optimize_budget(payload)

    async with get_session(tenant_id=test_tenant) as session:
        job = await session.get(BudgetOptimizationJob, UUID(result["budget_job_id"]))
        assert job is not None
        assert job.status == "completed"
        assert job.cost_cents == 0


@pytest.mark.asyncio
async def test_llm_stub_rls_blocks_cross_tenant_reads(test_tenant_pair):
    tenant_a, tenant_b = test_tenant_pair
    payload = _build_payload(tenant_a)
    result = await run_investigation(payload)
    investigation_id = UUID(result["investigation_id"])

    async with get_session(tenant_id=tenant_b) as session:
        blocked = await session.get(Investigation, investigation_id)
        assert blocked is None, "RLS failed: tenant B read tenant A investigation"

    async with get_session(tenant_id=tenant_a) as session:
        allowed = await session.get(Investigation, investigation_id)
        assert allowed is not None


@pytest.mark.asyncio
async def test_llm_explanation_stub_writes_api_call(test_tenant):
    payload = _build_payload(test_tenant)
    result = await generate_explanation(payload)

    async with get_session(tenant_id=test_tenant) as session:
        api_call = await session.get(LLMApiCall, UUID(result["api_call_id"]))
        assert api_call is not None
        assert api_call.tenant_id == test_tenant

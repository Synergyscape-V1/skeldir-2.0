from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.db.session import engine, get_session
from app.llm.budget_policy import BudgetPolicyEngine
from app.models.llm import (
    LLMBudgetReservation,
    LLMBreakerState,
    LLMHourlyShutoffState,
    LLMApiCall,
    LLMMonthlyBudgetState,
    LLMMonthlyCost,
    LLMSemanticCache,
)
from app.schemas.llm_payloads import LLMTaskPayload
from app.workers.llm import route_request


@pytest.mark.asyncio
async def test_llm_user_rls_blocks_cross_user_reads(test_tenant):
    tenant_id = test_tenant
    user_a = uuid4()
    user_b = uuid4()

    payload = LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=user_a,
        correlation_id=str(uuid4()),
        request_id=str(uuid4()),
        prompt={"stub": True},
        max_cost_cents=5,
    )

    async with get_session(tenant_id=tenant_id, user_id=user_a) as session:
        await route_request(payload, session=session)
        session.add(
            LLMBreakerState(
                tenant_id=tenant_id,
                user_id=user_a,
                breaker_key="llm-budget",
                state="open",
                failure_count=1,
                opened_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            LLMHourlyShutoffState(
                tenant_id=tenant_id,
                user_id=user_a,
                hour_start=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0),
                is_shutoff=True,
                reason="test",
            )
        )

    engine_instance = BudgetPolicyEngine()
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )
        await conn.execute(
            text("SELECT set_config('app.current_user_id', :uid, false)"),
            {"uid": str(user_a)},
        )
        await engine_instance.evaluate_and_audit(
            conn=conn,
            tenant_id=tenant_id,
            user_id=user_a,
            requested_model="gpt-4",
            input_tokens=100,
            output_tokens=100,
            correlation_id=f"rls-{uuid4().hex[:8]}",
        )

    async with get_session(tenant_id=tenant_id, user_id=user_a) as session:
        api_calls = await session.execute(select(func.count()).select_from(LLMApiCall))
        monthly = await session.execute(select(func.count()).select_from(LLMMonthlyCost))
        monthly_budget = await session.execute(select(func.count()).select_from(LLMMonthlyBudgetState))
        reservations = await session.execute(select(func.count()).select_from(LLMBudgetReservation))
        semantic_cache = await session.execute(select(func.count()).select_from(LLMSemanticCache))
        breaker = await session.execute(select(func.count()).select_from(LLMBreakerState))
        shutoff = await session.execute(select(func.count()).select_from(LLMHourlyShutoffState))
        audit = await session.execute(text("SELECT COUNT(*) FROM llm_call_audit"))

    assert api_calls.scalar_one() == 1
    assert monthly.scalar_one() >= 1
    assert monthly_budget.scalar_one() >= 1
    assert reservations.scalar_one() >= 1
    assert semantic_cache.scalar_one() >= 1
    assert breaker.scalar_one() == 1
    assert shutoff.scalar_one() == 1
    assert audit.scalar_one() >= 1

    async with get_session(tenant_id=tenant_id, user_id=user_b) as session:
        api_calls = await session.execute(select(func.count()).select_from(LLMApiCall))
        monthly = await session.execute(select(func.count()).select_from(LLMMonthlyCost))
        monthly_budget = await session.execute(select(func.count()).select_from(LLMMonthlyBudgetState))
        reservations = await session.execute(select(func.count()).select_from(LLMBudgetReservation))
        semantic_cache = await session.execute(select(func.count()).select_from(LLMSemanticCache))
        breaker = await session.execute(select(func.count()).select_from(LLMBreakerState))
        shutoff = await session.execute(select(func.count()).select_from(LLMHourlyShutoffState))
        audit = await session.execute(text("SELECT COUNT(*) FROM llm_call_audit"))

    assert api_calls.scalar_one() == 0, "RLS failed: user B can see user A llm_api_calls"
    assert monthly.scalar_one() == 0, "RLS failed: user B can see user A llm_monthly_costs"
    assert monthly_budget.scalar_one() == 0, "RLS failed: user B can see user A monthly budget"
    assert reservations.scalar_one() == 0, "RLS failed: user B can see user A reservations"
    assert semantic_cache.scalar_one() == 0, "RLS failed: user B can see user A semantic cache"
    assert breaker.scalar_one() == 0, "RLS failed: user B can see user A breaker state"
    assert shutoff.scalar_one() == 0, "RLS failed: user B can see user A shutoff state"
    assert audit.scalar_one() == 0, "RLS failed: user B can see user A llm_call_audit"

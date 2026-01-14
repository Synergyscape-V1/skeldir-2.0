from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.db.session import engine, get_session
from app.models.llm import BudgetOptimizationJob, Investigation, LLMApiCall, LLMMonthlyCost
from app.schemas.llm_payloads import LLMTaskPayload
from app.tasks.llm import llm_explanation_worker
from app.workers.llm import (
    generate_explanation,
    optimize_budget,
    record_monthly_costs,
    route_request,
    run_investigation,
)


def _build_payload(tenant_id: UUID) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        correlation_id=str(uuid4()),
        prompt={"stub": True},
        max_cost_cents=0,
    )


def _assert_postgres_engine() -> None:
    assert engine.dialect.name == "postgresql", "RLS tests must run on Postgres"


class RetryCapture(RuntimeError):
    pass


@pytest.mark.asyncio
async def test_llm_api_calls_unique_constraint_present():
    _assert_postgres_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT
                    con.conname AS name,
                    array_agg(att.attname ORDER BY att.attname) AS columns
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                JOIN unnest(con.conkey) WITH ORDINALITY AS cols(attnum, ord) ON true
                JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = cols.attnum
                WHERE con.contype = 'u'
                  AND con.conname = 'uq_llm_api_calls_tenant_request_endpoint'
                  AND rel.relname = 'llm_api_calls'
                  AND nsp.nspname = 'public'
                GROUP BY con.conname
                """
            )
        )
        row = result.mappings().first()
        assert row is not None, "Missing unique constraint uq_llm_api_calls_tenant_request_endpoint"
        assert set(row["columns"]) == {"tenant_id", "request_id", "endpoint"}


@pytest.mark.asyncio
async def test_llm_stub_atomic_writes_roll_back_on_failure(test_tenant):
    _assert_postgres_engine()
    request_id = str(uuid4())
    payload = LLMTaskPayload(
        tenant_id=test_tenant,
        correlation_id=str(uuid4()),
        request_id=request_id,
        prompt={"stub": True},
        max_cost_cents=0,
    )

    with pytest.raises(RuntimeError, match="forced failure"):
        async with get_session(tenant_id=test_tenant) as session:
            await route_request(payload, session=session, force_failure=True)

    async with get_session(tenant_id=test_tenant) as session:
        api_calls = (
            await session.execute(
                select(LLMApiCall).where(LLMApiCall.request_id == request_id)
            )
        ).scalars().all()
        assert not api_calls, "Atomicity failed: api call persisted after failure"

        monthly = (
            await session.execute(
                select(LLMMonthlyCost).where(LLMMonthlyCost.tenant_id == test_tenant)
            )
        ).scalars().all()
        assert not monthly, "Atomicity failed: monthly costs persisted after failure"


@pytest.mark.asyncio
async def test_llm_route_stub_writes_audit_rows(test_tenant):
    payload = _build_payload(test_tenant)
    async with get_session(tenant_id=test_tenant) as session:
        result = await route_request(payload, session=session)

    async with get_session(tenant_id=test_tenant) as session:
        api_call = await session.get(LLMApiCall, UUID(result["api_call_id"]))
        assert api_call is not None
        assert api_call.tenant_id == test_tenant
        assert api_call.endpoint == "app.tasks.llm.route"
        assert api_call.model == "llm_stub"
        assert api_call.cost_cents == 0
        assert api_call.request_metadata is not None
        assert api_call.request_metadata.get("stubbed") is True

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
    async with get_session(tenant_id=test_tenant) as session:
        result = await run_investigation(payload, session=session)

    async with get_session(tenant_id=test_tenant) as session:
        investigation = await session.get(Investigation, UUID(result["investigation_id"]))
        assert investigation is not None
        assert investigation.status == "completed"
        assert investigation.cost_cents == 0


@pytest.mark.asyncio
async def test_llm_budget_stub_writes_job(test_tenant):
    payload = _build_payload(test_tenant)
    async with get_session(tenant_id=test_tenant) as session:
        result = await optimize_budget(payload, session=session)

    async with get_session(tenant_id=test_tenant) as session:
        job = await session.get(BudgetOptimizationJob, UUID(result["budget_job_id"]))
        assert job is not None
        assert job.status == "completed"
        assert job.cost_cents == 0


@pytest.mark.asyncio
async def test_llm_stub_rls_blocks_cross_tenant_reads(test_tenant_pair):
    _assert_postgres_engine()
    tenant_a, tenant_b = test_tenant_pair
    payload = _build_payload(tenant_a)
    async with get_session(tenant_id=tenant_a) as session:
        result = await run_investigation(payload, session=session)
    investigation_id = UUID(result["investigation_id"])

    async with engine.begin() as conn:
        policies = await conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename IN (
                    'llm_api_calls',
                    'llm_monthly_costs',
                    'investigations',
                    'budget_optimization_jobs'
                  )
                """
            )
        )
        policy_tables = {row[0] for row in policies.fetchall()}
        assert policy_tables == {
            "llm_api_calls",
            "llm_monthly_costs",
            "investigations",
            "budget_optimization_jobs",
        }, f"Missing RLS policies: {policy_tables}"

    async with get_session(tenant_id=tenant_b) as session:
        blocked = await session.get(Investigation, investigation_id)
        assert blocked is None, "RLS failed: tenant B read tenant A investigation"

    async with get_session(tenant_id=tenant_a) as session:
        allowed = await session.get(Investigation, investigation_id)
        assert allowed is not None


@pytest.mark.asyncio
async def test_llm_explanation_stub_writes_api_call(test_tenant):
    payload = _build_payload(test_tenant)
    async with get_session(tenant_id=test_tenant) as session:
        result = await generate_explanation(payload, session=session)

    async with get_session(tenant_id=test_tenant) as session:
        api_call = await session.get(LLMApiCall, UUID(result["api_call_id"]))
        assert api_call is not None
        assert api_call.tenant_id == test_tenant
        assert api_call.endpoint == "app.tasks.llm.explanation"
        assert api_call.model == "llm_stub"
        assert api_call.request_metadata is not None
        assert api_call.request_metadata.get("stubbed") is True



@pytest.mark.asyncio
async def test_llm_explanation_idempotency_prevents_duplicate_audit_rows(test_tenant):
    _assert_postgres_engine()
    request_id = str(uuid4())
    payload = LLMTaskPayload(
        tenant_id=test_tenant,
        correlation_id=str(uuid4()),
        request_id=request_id,
        prompt={"stub": True},
        max_cost_cents=0,
    )

    async with get_session(tenant_id=test_tenant) as session:
        await generate_explanation(payload, session=session)
    async with get_session(tenant_id=test_tenant) as session:
        await generate_explanation(payload, session=session)

    async with get_session(tenant_id=test_tenant) as session:
        api_calls = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.request_id == request_id,
                    LLMApiCall.endpoint == "app.tasks.llm.explanation",
                )
            )
        ).scalars().all()
        assert len(api_calls) == 1, "Idempotency failed: duplicate llm_api_calls rows"

        monthly = (
            await session.execute(
                select(LLMMonthlyCost).where(LLMMonthlyCost.tenant_id == test_tenant)
            )
        ).scalars().one()
        assert monthly.total_calls == 1, "Idempotency failed: monthly costs double-counted"


@pytest.mark.asyncio
async def test_llm_explanation_retry_preserves_request_id_when_omitted(test_tenant, monkeypatch):
    _assert_postgres_engine()
    payload = {"stub": True}
    captured = {}

    def _fake_retry(*, kwargs=None, **_):
        captured["kwargs"] = kwargs or {}
        raise RetryCapture("retry")

    monkeypatch.setattr(llm_explanation_worker, "retry", _fake_retry, raising=True)

    with pytest.raises(RetryCapture, match="retry"):
        llm_explanation_worker.run(
            payload,
            tenant_id=test_tenant,
            max_cost_cents=0,
            force_failure=True,
        )

    retry_kwargs = captured["kwargs"]
    assert retry_kwargs.get("request_id"), "Retry kwargs missing request_id"
    assert retry_kwargs.get("correlation_id"), "Retry kwargs missing correlation_id"

    llm_explanation_worker.run(**retry_kwargs)
    llm_explanation_worker.run(**retry_kwargs)

    async with get_session(tenant_id=test_tenant) as session:
        api_calls = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.request_id == retry_kwargs["request_id"],
                    LLMApiCall.endpoint == "app.tasks.llm.explanation",
                )
            )
        ).scalars().all()
        assert len(api_calls) == 1, "Retry idempotency failed: duplicate llm_api_calls rows"

        monthly = (
            await session.execute(
                select(LLMMonthlyCost).where(LLMMonthlyCost.tenant_id == test_tenant)
            )
        ).scalars().one()
        assert monthly.total_calls == 1, "Retry idempotency failed: monthly costs double-counted"


@pytest.mark.asyncio
async def test_llm_monthly_costs_concurrent_updates_are_atomic(test_tenant):
    _assert_postgres_engine()
    increment = 7
    calls = 8

    async def _apply_increment():
        async with get_session(tenant_id=test_tenant) as session:
            async with session.begin_nested():
                await record_monthly_costs(
                    session,
                    tenant_id=test_tenant,
                    model_label="concurrency",
                    cost_cents=increment,
                    calls=1,
                )

    await asyncio.gather(*[_apply_increment() for _ in range(calls)])

    async with get_session(tenant_id=test_tenant) as session:
        row = (
            await session.execute(
                select(LLMMonthlyCost).where(LLMMonthlyCost.tenant_id == test_tenant)
            )
        ).scalars().one()
        assert row.total_cost_cents == increment * calls
        assert row.total_calls == calls


@pytest.mark.asyncio
async def test_llm_route_idempotency_prevents_duplicate_audit_rows(test_tenant):
    _assert_postgres_engine()
    request_id = str(uuid4())
    payload = LLMTaskPayload(
        tenant_id=test_tenant,
        correlation_id=str(uuid4()),
        request_id=request_id,
        prompt={"stub": True},
        max_cost_cents=0,
    )

    async with get_session(tenant_id=test_tenant) as session:
        await route_request(payload, session=session)
    async with get_session(tenant_id=test_tenant) as session:
        await route_request(payload, session=session)

    async with get_session(tenant_id=test_tenant) as session:
        api_calls = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.request_id == request_id,
                    LLMApiCall.endpoint == "app.tasks.llm.route",
                )
            )
        ).scalars().all()
        assert len(api_calls) == 1, "Idempotency failed: duplicate llm_api_calls rows"

        monthly = (
            await session.execute(
                select(LLMMonthlyCost).where(LLMMonthlyCost.tenant_id == test_tenant)
            )
        ).scalars().one()
        assert monthly.total_calls == 1, "Idempotency failed: monthly costs double-counted"

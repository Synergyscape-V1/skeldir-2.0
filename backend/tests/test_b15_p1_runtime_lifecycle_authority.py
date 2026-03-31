from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.llm.provider_boundary import ProviderBoundaryResult
from app.models.llm import BudgetJob, BudgetOptimizationJob, Investigation
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.budget_job import BudgetJobService
from app.workers import llm as llm_workers


def _payload(tenant_id, request_id: str) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=SYSTEM_USER_ID,
        correlation_id=request_id,
        request_id=request_id,
        prompt={"input": "b15-p1"},
        max_cost_cents=20,
    )


def _provider_result(*, status: str, request_id: str) -> ProviderBoundaryResult:
    return ProviderBoundaryResult(
        provider="stub",
        model="stub:model",
        output_text="provider-summary",
        reasoning_trace={"trace": "ok"},
        usage={
            "input_tokens": 1,
            "output_tokens": 1,
            "cost_cents": 1,
            "latency_ms": 1,
        },
        status=status,
        was_cached=False,
        request_id=request_id,
        correlation_id=request_id,
        api_call_id=uuid4(),
        failure_reason="forced-failure" if status != "success" else None,
    )


@pytest.mark.asyncio
async def test_b15_p1_investigation_worker_success_stops_at_ready_for_review(
    monkeypatch, test_tenant
) -> None:
    request_id = f"b15-p1-investigation-{uuid4().hex[:8]}"

    async def _fake_complete(*, model, session, endpoint, force_failure=False, **_kwargs):
        return _provider_result(status="success", request_id=model.request_id)

    monkeypatch.setattr(
        llm_workers._PROVIDER_BOUNDARY, "complete", _fake_complete, raising=True
    )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await llm_workers.run_investigation(
            _payload(test_tenant, request_id=request_id),
            session=session,
        )
        assert result["status"] == "accepted"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        authority_row = (
            (
                await session.execute(
                    text(
                        """
                        SELECT id, status, ready_for_review_at, completed_at
                        FROM investigation_jobs
                        WHERE tenant_id = :tenant_id
                          AND request_id = :request_id
                        """
                    ),
                    {"tenant_id": str(test_tenant), "request_id": request_id},
                )
            )
            .mappings()
            .first()
        )
        assert authority_row is not None
        assert authority_row["status"] == "ready_for_review"
        assert authority_row["ready_for_review_at"] is not None
        assert authority_row["completed_at"] is None

        trace_row = (
            (
                await session.execute(
                    select(Investigation).where(
                        Investigation.tenant_id == test_tenant,
                        Investigation.request_id == request_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        assert trace_row is not None
        assert trace_row.lifecycle_role == "internal_trace"
        assert trace_row.status == "compute_succeeded"
        assert str(trace_row.authority_job_id) == str(authority_row["id"])


@pytest.mark.asyncio
async def test_b15_p1_budget_worker_success_stops_at_ready_for_review(
    monkeypatch, test_tenant
) -> None:
    request_id = f"b15-p1-budget-{uuid4().hex[:8]}"

    async def _fake_complete(*, model, session, endpoint, force_failure=False, **_kwargs):
        return _provider_result(status="success", request_id=model.request_id)

    monkeypatch.setattr(
        llm_workers._PROVIDER_BOUNDARY, "complete", _fake_complete, raising=True
    )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await llm_workers.optimize_budget(
            _payload(test_tenant, request_id=request_id),
            session=session,
        )
        assert result["status"] == "accepted"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        authority_row = (
            (
                await session.execute(
                    select(BudgetJob).where(
                        BudgetJob.tenant_id == test_tenant,
                        BudgetJob.request_id == request_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        assert authority_row is not None
        assert authority_row.status == "ready_for_review"
        assert authority_row.ready_for_review_at is not None
        assert authority_row.completed_at is None

        trace_row = (
            (
                await session.execute(
                    select(BudgetOptimizationJob).where(
                        BudgetOptimizationJob.tenant_id == test_tenant,
                        BudgetOptimizationJob.request_id == request_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        assert trace_row is not None
        assert trace_row.lifecycle_role == "internal_trace"
        assert trace_row.status == "compute_succeeded"
        assert str(trace_row.authority_job_id) == str(authority_row.id)


@pytest.mark.asyncio
async def test_b15_p1_budget_complete_requires_approved_state(test_tenant) -> None:
    service = BudgetJobService()
    request_id = f"b15-p1-gate-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        job = await service.get_or_create_job(
            session,
            tenant_id=test_tenant,
            request_id=request_id,
            correlation_id=request_id,
        )
        await service.mark_ready_for_review(
            session,
            tenant_id=test_tenant,
            job_id=job.id,
            result_payload={"request_id": request_id},
        )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        with pytest.raises(ValueError, match="Illegal budget job transition"):
            await service.complete_job(
                session,
                tenant_id=test_tenant,
                job_id=job.id,
            )

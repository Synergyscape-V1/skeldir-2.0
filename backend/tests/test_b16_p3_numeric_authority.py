from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.api.budget import _coerce_result_payload as coerce_budget_payload
from app.api.investigations import _coerce_result_payload as coerce_investigation_payload
from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.llm.authority_contract import (
    BudgetResultAuthorityPayload,
    InvestigationResultAuthorityPayload,
)
from app.llm.output_validation import NUMERIC_AUTHORITY_DEFAULT_TOLERANCE_RATIO
from app.models.llm import LLMApiCall, LLMSemanticCache
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.budget_job import BudgetJobService
from app.services.investigation import InvestigationService
from app.workers.llm import _PROVIDER_BOUNDARY, optimize_budget, run_investigation


def _payload(
    tenant_id: UUID,
    *,
    request_id: str,
    prompt: dict,
    max_cost_cents: int = 30,
) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=SYSTEM_USER_ID,
        correlation_id=request_id,
        request_id=request_id,
        prompt=prompt,
        max_cost_cents=max_cost_cents,
    )


def _numeric_prompt(*, output_text: str, cache_enabled: bool = False) -> dict:
    return {
        "simulated_output_text": output_text,
        "cache_enabled": cache_enabled,
        "deterministic_truth": {
            "roas": 3.2,
            "revenue": 12000.0,
        },
        "numeric_claim_bindings": [
            {"claim_path": "summary.roas", "truth_path": "roas"},
            {"claim_path": "summary.revenue", "truth_path": "revenue"},
        ],
    }


def test_b16_p3_canonical_numeric_tolerance_policy_is_5_percent() -> None:
    assert NUMERIC_AUTHORITY_DEFAULT_TOLERANCE_RATIO == 0.05


@pytest.mark.asyncio
async def test_b16_p3_worker_supplied_validation_context_contains_numeric_authority_contract(
    test_tenant: UUID,
) -> None:
    request_id = f"b16-p3-context-{uuid4().hex[:8]}"
    prompt = _numeric_prompt(output_text="Projected ROAS is 3.2 and revenue is 12000.")

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await run_investigation(
            _payload(test_tenant, request_id=request_id, prompt=prompt),
            session=session,
        )
        assert result["status"] == "accepted"

        job = await InvestigationService(min_hold_seconds=0).get_job(
            session,
            tenant_id=test_tenant,
            job_id=UUID(result["investigation_id"]),
        )
        assert job is not None
        contract = InvestigationResultAuthorityPayload.model_validate(job.result or {})

    assert contract.authority_contract_version == "b1.6-p3"
    assert contract.validation_context.numeric_tolerance_ratio == 0.05
    assert contract.validation_context.deterministic_truth["roas"] == 3.2
    assert len(contract.validation_context.numeric_claim_bindings) == 2
    assert contract.llm_synthesis.validation_state == "validated"


@pytest.mark.asyncio
async def test_b16_p3_numeric_mismatch_is_rejected_before_investigation_success_sinks(
    test_tenant: UUID,
) -> None:
    request_id = f"b16-p3-investigation-mismatch-{uuid4().hex[:8]}"
    prompt = _numeric_prompt(output_text="Projected ROAS is 10.5 and revenue is 12000.")

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await run_investigation(
            _payload(test_tenant, request_id=request_id, prompt=prompt),
            session=session,
        )
        assert result["status"] == "accepted"
        assert result["validation_code"] == "numeric_mismatch"

        job = await InvestigationService(min_hold_seconds=0).get_job(
            session,
            tenant_id=test_tenant,
            job_id=UUID(result["investigation_id"]),
        )
        assert job is not None
        contract = InvestigationResultAuthorityPayload.model_validate(job.result or {})
        findings, synthesis = coerce_investigation_payload(job)

        mismatch_count = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_validation_failures
                        WHERE tenant_id = :tenant_id
                          AND endpoint = 'app.tasks.llm.investigation'
                          AND validation_error = 'numeric_mismatch'
                          AND request_payload ->> 'request_id' = :request_id
                        """
                    ),
                    {"tenant_id": str(test_tenant), "request_id": request_id},
                )
            ).scalar_one()
        )

    assert contract.llm_synthesis.validation_state == "rejected"
    assert "10.5" in contract.llm_audit.provider_summary_raw
    assert findings
    assert synthesis is None
    assert mismatch_count >= 1


@pytest.mark.asyncio
async def test_b16_p3_numeric_mismatch_is_rejected_before_budget_success_sinks(
    test_tenant: UUID,
) -> None:
    request_id = f"b16-p3-budget-mismatch-{uuid4().hex[:8]}"
    prompt = _numeric_prompt(output_text="Projected ROAS is 10.5 and revenue is 12000.")
    prompt["optimization_goal"] = "maximize_revenue"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await optimize_budget(
            _payload(test_tenant, request_id=request_id, prompt=prompt),
            session=session,
        )
        assert result["status"] == "accepted"
        assert result["validation_code"] == "numeric_mismatch"

        record = await BudgetJobService().get_by_id(
            session,
            tenant_id=test_tenant,
            job_id=UUID(result["budget_job_id"]),
        )
        contract = BudgetResultAuthorityPayload.model_validate(record.result or {})
        recommendation, synthesis = coerce_budget_payload(record)

        mismatch_count = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_validation_failures
                        WHERE tenant_id = :tenant_id
                          AND endpoint = 'app.tasks.llm.budget_optimization'
                          AND validation_error = 'numeric_mismatch'
                          AND request_payload ->> 'request_id' = :request_id
                        """
                    ),
                    {"tenant_id": str(test_tenant), "request_id": request_id},
                )
            ).scalar_one()
        )

    assert contract.llm_synthesis.validation_state == "rejected"
    assert "10.5" in contract.llm_audit.provider_summary_raw
    assert recommendation
    assert synthesis is None
    assert mismatch_count >= 1


@pytest.mark.asyncio
async def test_b16_p3_cache_replay_numeric_mismatch_is_invalidated_then_fresh_path_runs(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_request = f"b16-p3-cache-seed-{uuid4().hex[:8]}"
    replay_request = f"b16-p3-cache-replay-{uuid4().hex[:8]}"
    prompt = _numeric_prompt(
        output_text="Projected ROAS is 3.2 and revenue is 12000.",
        cache_enabled=True,
    )
    prompt["cache_watermark"] = 44

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        seeded = await run_investigation(
            _payload(test_tenant, request_id=seed_request, prompt=prompt),
            session=session,
        )
        assert seeded["status"] == "accepted"
        assert seeded["was_cached"] is False

        seed_call = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.user_id == SYSTEM_USER_ID,
                    LLMApiCall.endpoint == "app.tasks.llm.investigation",
                    LLMApiCall.request_id == seed_request,
                )
            )
        ).scalars().one()
        cache_row = (
            await session.execute(
                select(LLMSemanticCache).where(
                    LLMSemanticCache.tenant_id == test_tenant,
                    LLMSemanticCache.user_id == SYSTEM_USER_ID,
                    LLMSemanticCache.endpoint == "app.tasks.llm.investigation",
                    LLMSemanticCache.cache_key == seed_call.cache_key,
                )
            )
        ).scalars().one()
        cache_row.response_text = "Projected ROAS is 10.5 and revenue is 12000."
        await session.commit()

    provider_calls = {"count": 0}

    async def _provider_spy(*, requested_model, prompt, reservation):
        provider_calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "Projected ROAS is 3.2 and revenue is 12000.",
            "reasoning_trace": {"trace_type": "b16-p3-cache"},
            "response_metadata": {"source": "b16-p3-cache"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_spy, raising=True)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        replay = await run_investigation(
            _payload(test_tenant, request_id=replay_request, prompt=prompt),
            session=session,
        )
        assert replay["status"] == "accepted"
        assert replay["was_cached"] is False
        assert replay["validation_code"] == "success"

        mismatch_count = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_validation_failures
                        WHERE tenant_id = :tenant_id
                          AND endpoint = 'app.tasks.llm.investigation'
                          AND validation_error = 'cache_numeric_mismatch'
                          AND request_payload ->> 'request_id' = :request_id
                        """
                    ),
                    {"tenant_id": str(test_tenant), "request_id": replay_request},
                )
            ).scalar_one()
        )

    assert provider_calls["count"] == 1
    assert mismatch_count >= 1

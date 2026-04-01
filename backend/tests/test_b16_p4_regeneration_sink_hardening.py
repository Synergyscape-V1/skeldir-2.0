from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
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
from app.models.llm import (
    BudgetOptimizationJob,
    Investigation,
    LLMBreakerState,
)
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.budget_job import BudgetJobRecord, BudgetJobService
from app.services.centaur_lifecycle import LifecycleStatus
from app.services.investigation import InvestigationJob, InvestigationService
from app.services.llm_dispatch import _payload_to_kwargs
from app.workers.llm import _PROVIDER_BOUNDARY, generate_explanation, optimize_budget, run_investigation


def _payload(
    tenant_id: UUID,
    *,
    request_id: str,
    prompt: dict[str, Any],
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


def _investigation_job(result_payload: dict[str, Any], *, status: LifecycleStatus) -> InvestigationJob:
    now = datetime.now(timezone.utc)
    return InvestigationJob(
        id=uuid4(),
        tenant_id=uuid4(),
        request_id=f"req-{uuid4().hex[:8]}",
        correlation_id=f"corr-{uuid4().hex[:8]}",
        status=status,
        created_at=now,
        updated_at=now,
        min_hold_until=now,
        ready_for_review_at=now,
        approved_at=now,
        rejected_at=None,
        refine_requested_at=None,
        rerun_requested_at=None,
        completed_at=now,
        failed_at=None,
        timeout_at=None,
        cancelled_at=None,
        result=result_payload,
        failure_code=None,
        failure_reason=None,
        remaining_hold_seconds=0,
    )


def _budget_job(result_payload: dict[str, Any], *, status: LifecycleStatus) -> BudgetJobRecord:
    now = datetime.now(timezone.utc)
    return BudgetJobRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        request_id=f"req-{uuid4().hex[:8]}",
        correlation_id=f"corr-{uuid4().hex[:8]}",
        status=status,
        created_at=now,
        updated_at=now,
        ready_for_review_at=now,
        approved_at=now,
        rejected_at=None,
        refine_requested_at=None,
        rerun_requested_at=None,
        completed_at=now,
        failed_at=None,
        timeout_at=None,
        cancelled_at=None,
        result=result_payload,
        failure_code=None,
        failure_reason=None,
    )


@pytest.mark.asyncio
async def test_b16_p4_regeneration_uses_structured_correction_payload(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_id = f"b16-p4-regeneration-{uuid4().hex[:8]}"
    call_prompts: list[dict[str, Any]] = []

    async def _provider_spy(*, requested_model, prompt, reservation):
        call_prompts.append(dict(prompt))
        if len(call_prompts) == 1:
            return {
                "provider": "stub",
                "model": requested_model,
                "output_text": '{"summary":"wrong field"}',
                "reasoning_trace": {"trace_type": "b16-p4-regeneration"},
                "response_metadata": {"source": "b16-p4-regeneration"},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
            }
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": '{"explanation":"corrected payload"}',
            "reasoning_trace": {"trace_type": "b16-p4-regeneration"},
            "response_metadata": {"source": "b16-p4-regeneration"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_spy, raising=True)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await generate_explanation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={"cache_enabled": False, "input": "Explain deterministic output validation."},
            ),
            session=session,
        )

    assert result["status"] == "accepted"
    assert result["validation_code"] == "success"
    assert len(call_prompts) == 2
    assert "validation_correction_payload" not in call_prompts[0]
    second_prompt = call_prompts[1]
    assert int(second_prompt["request_local_attempt"]) == 2
    assert int(second_prompt["request_local_attempt_budget"]) == 3
    correction_payload = second_prompt.get("validation_correction_payload")
    assert isinstance(correction_payload, dict)
    assert correction_payload["correction_type"] == "validation_regeneration"
    assert correction_payload["validation_code"] == "schema_failed"
    assert int(correction_payload["attempt"]) == 1
    assert int(correction_payload["next_attempt"]) == 2
    assert int(correction_payload["max_attempts"]) == 3
    messages = second_prompt.get("messages")
    assert isinstance(messages, list)
    assert any(
        str(message.get("role")) == "system"
        and "Validation regeneration payload (JSON)" in str(message.get("content", ""))
        for message in messages
        if isinstance(message, dict)
    )


@pytest.mark.asyncio
async def test_b16_p4_request_local_attempt_budget_is_capped_at_three(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_id = f"b16-p4-attempt-budget-{uuid4().hex[:8]}"
    provider_calls = {"count": 0}

    async def _provider_spy(*, requested_model, prompt, reservation):
        provider_calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": '{"summary":"always wrong for explanation schema"}',
            "reasoning_trace": {"trace_type": "b16-p4-attempt-budget"},
            "response_metadata": {"source": "b16-p4-attempt-budget"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_spy, raising=True)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={"cache_enabled": False, "input": "This should fail three times."},
            ),
            session=session,
        )
        failure_count = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_validation_failures
                        WHERE tenant_id = :tenant_id
                          AND endpoint = 'app.tasks.llm.explanation'
                          AND request_payload ->> 'request_id' = :request_id
                        """
                    ),
                    {"tenant_id": str(test_tenant), "request_id": request_id},
                )
            ).scalar_one()
        )

    assert failed["status"] == "failed"
    assert failed["failure_reason"] == "validation_schema_failed"
    assert provider_calls["count"] == 3
    assert failure_count == 3


@pytest.mark.asyncio
async def test_b16_p4_validation_failures_remain_request_local_and_do_not_trip_breaker(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed_request_id = f"b16-p4-breaker-separation-fail-{uuid4().hex[:8]}"
    success_request_id = f"b16-p4-breaker-separation-success-{uuid4().hex[:8]}"
    call_counter = {"count": 0}

    async def _provider_spy(*, requested_model, prompt, reservation):
        call_counter["count"] += 1
        if call_counter["count"] <= 3:
            output = '{"summary":"schema mismatch"}'
        else:
            output = '{"explanation":"provider still reachable"}'
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": output,
            "reasoning_trace": {"trace_type": "b16-p4-breaker-separation"},
            "response_metadata": {"source": "b16-p4-breaker-separation"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_spy, raising=True)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=failed_request_id,
                prompt={"cache_enabled": False, "input": "fail validation"},
            ),
            session=session,
        )
        success = await generate_explanation(
            _payload(
                test_tenant,
                request_id=success_request_id,
                prompt={"cache_enabled": False, "input": "should remain unblocked"},
            ),
            session=session,
        )
        breaker_rows = (
            await session.execute(
                select(LLMBreakerState).where(
                    LLMBreakerState.tenant_id == test_tenant,
                    LLMBreakerState.user_id == SYSTEM_USER_ID,
                    LLMBreakerState.breaker_key == _PROVIDER_BOUNDARY.breaker_key,
                )
            )
        ).scalars().all()

    assert failed["status"] == "failed"
    assert failed["failure_reason"] == "validation_schema_failed"
    assert success["status"] == "accepted"
    assert success["blocked_reason"] is None
    assert all(int(row.failure_count) == 0 for row in breaker_rows)


@pytest.mark.asyncio
async def test_b16_p4_provider_transport_failures_still_hit_breaker_accounting(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_id = f"b16-p4-breaker-provider-{uuid4().hex[:8]}"

    async def _provider_fail(*, requested_model, prompt, reservation):
        raise RuntimeError("provider_down")

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_fail, raising=True)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={"cache_enabled": False, "input": "provider error path"},
            ),
            session=session,
        )
        breaker_row = (
            await session.execute(
                select(LLMBreakerState).where(
                    LLMBreakerState.tenant_id == test_tenant,
                    LLMBreakerState.user_id == SYSTEM_USER_ID,
                    LLMBreakerState.breaker_key == _PROVIDER_BOUNDARY.breaker_key,
                )
            )
        ).scalars().first()

    assert failed["status"] == "failed"
    assert failed["failure_reason"] == "provider_error:RuntimeError"
    assert breaker_row is not None
    assert int(breaker_row.failure_count) >= 1


@pytest.mark.asyncio
async def test_b16_p4_invalid_synthesis_isolation_preserves_only_audit_raw_artifact(
    test_tenant: UUID,
) -> None:
    investigation_request_id = f"b16-p4-investigation-isolation-{uuid4().hex[:8]}"
    budget_request_id = f"b16-p4-budget-isolation-{uuid4().hex[:8]}"
    hallucinated_output = "Projected ROAS is 10.5 and revenue is 12000."
    investigation_prompt = {
        "simulated_output_text": hallucinated_output,
        "cache_enabled": False,
        "deterministic_truth": {"roas": 3.2, "revenue": 12000.0},
        "numeric_claim_bindings": [
            {"claim_path": "summary.roas", "truth_path": "roas"},
            {"claim_path": "summary.revenue", "truth_path": "revenue"},
        ],
    }
    budget_prompt = dict(investigation_prompt)
    budget_prompt["optimization_goal"] = "maximize_roas"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        investigation_result = await run_investigation(
            _payload(
                test_tenant,
                request_id=investigation_request_id,
                prompt=investigation_prompt,
            ),
            session=session,
        )
        budget_result = await optimize_budget(
            _payload(
                test_tenant,
                request_id=budget_request_id,
                prompt=budget_prompt,
            ),
            session=session,
        )

        investigation_job = await InvestigationService(min_hold_seconds=0).get_job(
            session,
            tenant_id=test_tenant,
            job_id=UUID(investigation_result["investigation_id"]),
        )
        budget_job = await BudgetJobService().get_by_id(
            session,
            tenant_id=test_tenant,
            job_id=UUID(budget_result["budget_job_id"]),
        )
        investigation_trace = (
            await session.execute(
                select(Investigation).where(
                    Investigation.tenant_id == test_tenant,
                    Investigation.request_id == investigation_request_id,
                )
            )
        ).scalars().one()
        budget_trace = (
            await session.execute(
                select(BudgetOptimizationJob).where(
                    BudgetOptimizationJob.tenant_id == test_tenant,
                    BudgetOptimizationJob.request_id == budget_request_id,
                )
            )
        ).scalars().one()

    assert investigation_job is not None
    assert budget_job is not None
    investigation_contract = InvestigationResultAuthorityPayload.model_validate(
        investigation_job.result or {}
    )
    budget_contract = BudgetResultAuthorityPayload.model_validate(budget_job.result or {})

    assert investigation_contract.llm_synthesis.validation_state == "rejected"
    assert budget_contract.llm_synthesis.validation_state == "rejected"
    assert hallucinated_output in investigation_contract.llm_audit.provider_summary_raw
    assert hallucinated_output in budget_contract.llm_audit.provider_summary_raw
    assert hallucinated_output not in investigation_contract.llm_synthesis.non_authoritative_summary
    assert hallucinated_output not in budget_contract.llm_synthesis.non_authoritative_summary
    assert (investigation_trace.result or {}).get("summary") == ""
    assert (budget_trace.recommendations or {}).get("provider_summary") == ""


def test_b16_p4_api_fallback_fail_closed_for_mixed_legacy_payloads() -> None:
    legacy_investigation_payload = {
        "deterministic_findings": [{"finding_id": "det-1"}],
        "llm_synthesis": {
            "validation_state": "validated",
            "non_authoritative_summary": "legacy synthesis that should not surface",
            "model": "stub",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }
    legacy_budget_payload = {
        "deterministic_recommendation": {"optimization_goal": "maximize_roas"},
        "llm_synthesis": {
            "validation_state": "validated",
            "non_authoritative_summary": "legacy synthesis that should not surface",
            "model": "stub",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    }

    findings, investigation_synthesis = coerce_investigation_payload(
        _investigation_job(legacy_investigation_payload, status=LifecycleStatus.COMPLETED)
    )
    recommendation, budget_synthesis = coerce_budget_payload(
        _budget_job(legacy_budget_payload, status=LifecycleStatus.COMPLETED)
    )

    assert findings == [{"finding_id": "det-1"}]
    assert recommendation == {"optimization_goal": "maximize_roas"}
    assert investigation_synthesis is None
    assert budget_synthesis is None


def test_b16_p4_api_suppresses_validated_synthesis_when_job_status_is_failed() -> None:
    now = datetime.now(timezone.utc)
    investigation_contract = InvestigationResultAuthorityPayload.model_validate(
        {
            "authority_contract_version": "b1.6-p3",
            "request_id": f"req-{uuid4().hex[:8]}",
            "deterministic_authority": {
                "authority_class": "deterministic_authority",
                "deterministic_findings": [{"finding_id": "f-1"}],
            },
            "llm_synthesis": {
                "authority_class": "validated_synthesis",
                "validation_state": "validated",
                "non_authoritative_summary": "validated summary should be hidden on failed lifecycle",
                "caveats": [],
                "model": "stub",
                "generated_at": now.isoformat().replace("+00:00", "Z"),
            },
            "llm_audit": {
                "authority_class": "audit_only_raw_provider_artifact",
                "provider_summary_raw": "raw",
            },
            "validation_context": {
                "contract_version": "b1.6-p3",
                "feature_surface": "investigation",
                "request_id": "req",
                "correlation_id": "corr",
                "deterministic_truth": {},
                "deterministic_truth_sources": [],
                "numeric_claim_paths": [],
                "numeric_claim_bindings": [],
                "numeric_tolerance_ratio": 0.05,
            },
        }
    ).model_dump(mode="json")
    budget_contract = BudgetResultAuthorityPayload.model_validate(
        {
            "authority_contract_version": "b1.6-p3",
            "request_id": f"req-{uuid4().hex[:8]}",
            "deterministic_authority": {
                "authority_class": "deterministic_authority",
                "deterministic_recommendation": {"optimization_goal": "maximize_roas"},
            },
            "llm_synthesis": {
                "authority_class": "validated_synthesis",
                "validation_state": "validated",
                "non_authoritative_summary": "validated summary should be hidden on failed lifecycle",
                "caveats": [],
                "model": "stub",
                "generated_at": now.isoformat().replace("+00:00", "Z"),
            },
            "llm_audit": {
                "authority_class": "audit_only_raw_provider_artifact",
                "provider_summary_raw": "raw",
            },
            "validation_context": {
                "contract_version": "b1.6-p3",
                "feature_surface": "budget",
                "request_id": "req",
                "correlation_id": "corr",
                "deterministic_truth": {},
                "deterministic_truth_sources": [],
                "numeric_claim_paths": [],
                "numeric_claim_bindings": [],
                "numeric_tolerance_ratio": 0.05,
            },
        }
    ).model_dump(mode="json")

    findings, investigation_synthesis = coerce_investigation_payload(
        _investigation_job(investigation_contract, status=LifecycleStatus.FAILED)
    )
    recommendation, budget_synthesis = coerce_budget_payload(
        _budget_job(budget_contract, status=LifecycleStatus.FAILED)
    )

    assert findings == [{"finding_id": "f-1"}]
    assert recommendation == {"optimization_goal": "maximize_roas"}
    assert investigation_synthesis is None
    assert budget_synthesis is None


def test_b16_p4_dispatch_disables_task_retry_matrix_by_default() -> None:
    kwargs = _payload_to_kwargs(
        LLMTaskPayload(
            tenant_id=uuid4(),
            user_id=uuid4(),
            correlation_id="corr",
            request_id="req",
            prompt={"input": "hi"},
            max_cost_cents=2,
        )
    )
    assert kwargs["retry_on_failure"] is False

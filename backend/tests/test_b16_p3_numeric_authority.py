from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text

import app.workers.llm as llm_worker_module
from app.api.budget import _coerce_result_payload as coerce_budget_payload
from app.api.investigations import _coerce_result_payload as coerce_investigation_payload
from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.llm.authority_contract import (
    BudgetResultAuthorityPayload,
    InvestigationResultAuthorityPayload,
    ValidationContext,
)
from app.llm.output_validation import (
    INVESTIGATION_VALIDATION_SPEC,
    NUMERIC_AUTHORITY_DEFAULT_TOLERANCE_RATIO,
    validate_provider_output_text,
)
from app.models.llm import LLMApiCall, LLMSemanticCache
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.budget_job import BudgetJobRecord, BudgetJobService
from app.services.centaur_lifecycle import LifecycleStatus
from app.services.investigation import InvestigationJob, InvestigationService
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


def test_b16_p3_schema_composed_numeric_validation_uses_pydantic_context() -> None:
    with pytest.raises(ValidationError) as exc_info:
        INVESTIGATION_VALIDATION_SPEC.schema_model.model_validate(
            {"summary": "Projected ROAS is 10.5 and revenue is 12000."},
            context={
                "deterministic_truth": {"roas": 3.2, "revenue": 12000.0},
                "numeric_claim_bindings": [
                    {"claim_path": "summary.roas", "truth_path": "roas"},
                    {"claim_path": "summary.revenue", "truth_path": "revenue"},
                ],
            },
        )

    assert any(
        str(error.get("type")) == "numeric_mismatch"
        for error in exc_info.value.errors()
    )


def test_b16_p3_missing_truth_path_fails_closed_in_kernel() -> None:
    result = validate_provider_output_text(
        raw_output_text='{"summary":"Projected ROAS is 3.2 and revenue is 12000."}',
        validation_spec=INVESTIGATION_VALIDATION_SPEC,
        stage="provider",
        validation_context={
            "deterministic_truth": {"revenue": 12000.0},
            "numeric_claim_bindings": [
                {"claim_path": "summary.roas", "truth_path": "roas"},
            ],
        },
    )
    assert result.ok is False
    assert result.code == "numeric_mismatch"
    assert "reason=truth_path_missing" in str(result.error_detail)


def test_b16_p3_missing_claim_path_fails_closed_in_kernel() -> None:
    result = validate_provider_output_text(
        raw_output_text='{"summary":"Projected revenue is 12000."}',
        validation_spec=INVESTIGATION_VALIDATION_SPEC,
        stage="provider",
        validation_context={
            "deterministic_truth": {"roas": 3.2},
            "numeric_claim_bindings": [
                {"claim_path": "summary.roas", "truth_path": "roas"},
            ],
        },
    )
    assert result.ok is False
    assert result.code == "numeric_mismatch"
    assert "reason=claim_labeled_text_number_missing" in str(result.error_detail)


def test_b16_p3_invalid_binding_config_fails_closed_in_kernel() -> None:
    result = validate_provider_output_text(
        raw_output_text='{"summary":"Projected ROAS is 3.2."}',
        validation_spec=INVESTIGATION_VALIDATION_SPEC,
        stage="provider",
        validation_context={
            "deterministic_truth": {"roas": 3.2},
            "numeric_claim_bindings": [
                {"claim_path": "summary.roas"},
            ],
        },
    )
    assert result.ok is False
    assert result.code == "numeric_mismatch"
    assert "reason=binding_0_truth_path_invalid" in str(result.error_detail)


def test_b16_p3_non_numeric_truth_value_fails_closed_in_kernel() -> None:
    result = validate_provider_output_text(
        raw_output_text='{"summary":"Projected ROAS is 3.2."}',
        validation_spec=INVESTIGATION_VALIDATION_SPEC,
        stage="provider",
        validation_context={
            "deterministic_truth": {"roas": "not-a-number"},
            "numeric_claim_bindings": [
                {"claim_path": "summary.roas", "truth_path": "roas"},
            ],
        },
    )
    assert result.ok is False
    assert result.code == "numeric_mismatch"
    assert "reason=truth_value_not_numeric" in str(result.error_detail)


def test_b16_p3_binding_driven_tolerance_override_is_enforced() -> None:
    default_tolerance_pass = validate_provider_output_text(
        raw_output_text='{"summary":"Projected ROAS is 3.3."}',
        validation_spec=INVESTIGATION_VALIDATION_SPEC,
        stage="provider",
        validation_context={
            "deterministic_truth": {"roas": 3.2},
            "numeric_tolerance_ratio": 0.05,
            "numeric_claim_bindings": [
                {"claim_path": "summary.roas", "truth_path": "roas"},
            ],
        },
    )
    override_tolerance_fail = validate_provider_output_text(
        raw_output_text='{"summary":"Projected ROAS is 3.3."}',
        validation_spec=INVESTIGATION_VALIDATION_SPEC,
        stage="provider",
        validation_context={
            "deterministic_truth": {"roas": 3.2},
            "numeric_tolerance_ratio": 0.05,
            "numeric_claim_bindings": [
                {
                    "claim_path": "summary.roas",
                    "truth_path": "roas",
                    "tolerance_ratio": 0.01,
                },
            ],
        },
    )

    assert default_tolerance_pass.ok is True
    assert override_tolerance_fail.ok is False
    assert override_tolerance_fail.code == "numeric_mismatch"
    assert "tolerance_ratio=0.01" in str(override_tolerance_fail.error_detail)


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
async def test_b16_p3_cache_replay_numeric_mismatch_degrades_without_fresh_provider_call(
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
        assert replay["was_cached"] is True
        assert replay["validation_code"] == "numeric_mismatch"

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
        replay_call = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.user_id == SYSTEM_USER_ID,
                    LLMApiCall.endpoint == "app.tasks.llm.investigation",
                    LLMApiCall.request_id == replay_request,
                )
            )
        ).scalars().one()

    assert provider_calls["count"] == 0
    assert int(replay_call.cost_cents) == 0
    assert mismatch_count >= 1


@pytest.mark.asyncio
async def test_b16_p3_numeric_rejection_cache_marker_bounds_repeat_spend(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_request = f"b16-p3-marker-1-{uuid4().hex[:8]}"
    second_request = f"b16-p3-marker-2-{uuid4().hex[:8]}"
    prompt = _numeric_prompt(
        output_text="Projected ROAS is 10.5 and revenue is 12000.",
        cache_enabled=True,
    )
    prompt["cache_watermark"] = 912

    provider_calls = {"count": 0}

    async def _provider_spy(*, requested_model, prompt, reservation):
        provider_calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "Projected ROAS is 10.5 and revenue is 12000.",
            "reasoning_trace": {"trace_type": "b16-p3-marker"},
            "response_metadata": {"source": "b16-p3-marker"},
            "usage": {"input_tokens": 2, "output_tokens": 2, "cost_cents": 2},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_spy, raising=True)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        first = await run_investigation(
            _payload(test_tenant, request_id=first_request, prompt=prompt),
            session=session,
        )
        first_provider_calls = provider_calls["count"]
        second = await run_investigation(
            _payload(test_tenant, request_id=second_request, prompt=prompt),
            session=session,
        )

        second_call = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.user_id == SYSTEM_USER_ID,
                    LLMApiCall.endpoint == "app.tasks.llm.investigation",
                    LLMApiCall.request_id == second_request,
                )
            )
        ).scalars().one()

    assert first["status"] == "accepted"
    assert first["validation_code"] == "numeric_mismatch"
    assert first_provider_calls >= 1
    assert second["status"] == "accepted"
    assert second["validation_code"] == "numeric_mismatch"
    assert second["was_cached"] is True
    assert provider_calls["count"] == first_provider_calls
    assert int(second_call.cost_cents) == 0


@pytest.mark.asyncio
async def test_b16_p3_invalid_binding_config_rejects_before_investigation_success_sinks(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    request_id = f"b16-p3-invalid-binding-{uuid4().hex[:8]}"
    prompt = _numeric_prompt(output_text="Projected ROAS is 3.2 and revenue is 12000.")

    class _MalformedBindingValidationContext(ValidationContext):
        def model_dump(self, *args, **kwargs):  # type: ignore[override]
            payload = super().model_dump(*args, **kwargs)
            payload["numeric_claim_bindings"] = [{"claim_path": "summary.roas"}]
            return payload

    original_builder = llm_worker_module._build_numeric_validation_context

    def _malformed_builder(**kwargs) -> ValidationContext:
        base_context = original_builder(**kwargs)
        return _MalformedBindingValidationContext.model_validate(
            base_context.model_dump(mode="json")
        )

    monkeypatch.setattr(
        llm_worker_module,
        "_build_numeric_validation_context",
        _malformed_builder,
        raising=True,
    )

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await run_investigation(
            _payload(test_tenant, request_id=request_id, prompt=prompt),
            session=session,
        )
        assert result["status"] == "accepted"
        assert result["validation_code"] == "numeric_mismatch"

        failure_details = (
            await session.execute(
                text(
                    """
                    SELECT response_payload ->> 'validation_error'
                    FROM llm_validation_failures
                    WHERE tenant_id = :tenant_id
                      AND endpoint = 'app.tasks.llm.investigation'
                      AND validation_error = 'numeric_mismatch'
                      AND request_payload ->> 'request_id' = :request_id
                    """
                ),
                {"tenant_id": str(test_tenant), "request_id": request_id},
            )
        ).scalars().all()

        job = await InvestigationService(min_hold_seconds=0).get_job(
            session,
            tenant_id=test_tenant,
            job_id=UUID(result["investigation_id"]),
        )
        assert job is not None
        findings, synthesis = coerce_investigation_payload(job)
        contract = InvestigationResultAuthorityPayload.model_validate(job.result or {})

    assert findings
    assert synthesis is None
    assert contract.llm_synthesis.validation_state == "rejected"
    assert any(
        "reason=binding_0_truth_path_invalid" in str(detail or "")
        for detail in failure_details
    )


@pytest.mark.asyncio
async def test_b16_p3_non_numeric_truth_value_rejects_before_investigation_success_sinks(
    test_tenant: UUID,
) -> None:
    request_id = f"b16-p3-truth-nonnumeric-{uuid4().hex[:8]}"
    prompt = _numeric_prompt(output_text="Projected ROAS is 3.2 and revenue is 12000.")
    prompt["deterministic_truth"] = {"roas": "not-a-number", "revenue": 12000.0}

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await run_investigation(
            _payload(test_tenant, request_id=request_id, prompt=prompt),
            session=session,
        )
        assert result["status"] == "accepted"
        assert result["validation_code"] == "numeric_mismatch"

        failure_details = (
            await session.execute(
                text(
                    """
                    SELECT response_payload ->> 'validation_error'
                    FROM llm_validation_failures
                    WHERE tenant_id = :tenant_id
                      AND endpoint = 'app.tasks.llm.investigation'
                      AND validation_error = 'numeric_mismatch'
                      AND request_payload ->> 'request_id' = :request_id
                    """
                ),
                {"tenant_id": str(test_tenant), "request_id": request_id},
            )
        ).scalars().all()

        job = await InvestigationService(min_hold_seconds=0).get_job(
            session,
            tenant_id=test_tenant,
            job_id=UUID(result["investigation_id"]),
        )
        assert job is not None
        findings, synthesis = coerce_investigation_payload(job)
        contract = InvestigationResultAuthorityPayload.model_validate(job.result or {})

    assert findings
    assert synthesis is None
    assert contract.llm_synthesis.validation_state == "rejected"
    assert any(
        "reason=truth_value_not_numeric" in str(detail or "")
        for detail in failure_details
    )


def _investigation_job(result_payload: dict) -> InvestigationJob:
    now = datetime.now(timezone.utc)
    return InvestigationJob(
        id=uuid4(),
        tenant_id=uuid4(),
        request_id=f"req-{uuid4().hex[:8]}",
        correlation_id=f"corr-{uuid4().hex[:8]}",
        status=LifecycleStatus.COMPLETED,
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


def _budget_job(result_payload: dict) -> BudgetJobRecord:
    now = datetime.now(timezone.utc)
    return BudgetJobRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        request_id=f"req-{uuid4().hex[:8]}",
        correlation_id=f"corr-{uuid4().hex[:8]}",
        status=LifecycleStatus.COMPLETED,
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


def test_b16_p3_investigation_router_coercion_suppresses_rejected_synthesis() -> None:
    findings, synthesis = coerce_investigation_payload(
        _investigation_job(
            {
                "deterministic_findings": [{"finding_id": "f-1"}],
                "llm_synthesis": {
                    "validation_state": "rejected",
                    "non_authoritative_summary": "bad output",
                },
            }
        )
    )
    assert findings == [{"finding_id": "f-1"}]
    assert synthesis is None


def test_b16_p3_budget_router_coercion_suppresses_rejected_synthesis() -> None:
    recommendation, synthesis = coerce_budget_payload(
        _budget_job(
            {
                "deterministic_recommendation": {"optimization_goal": "maximize_roas"},
                "llm_synthesis": {
                    "validation_state": "rejected",
                    "non_authoritative_summary": "bad output",
                },
            }
        )
    )
    assert recommendation == {"optimization_goal": "maximize_roas"}
    assert synthesis is None

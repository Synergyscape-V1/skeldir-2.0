from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.api.budget import _coerce_result_payload as coerce_budget_payload
from app.api.investigations import _coerce_result_payload as coerce_investigation_payload
from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.llm.authority_contract import (
    BudgetResultAuthorityPayload,
    InvestigationResultAuthorityPayload,
)
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.budget_job import BudgetJobService
from app.services.investigation import InvestigationService
from app.workers.llm import optimize_budget, run_investigation


def _payload(
    tenant_id: UUID,
    *,
    request_id: str,
    prompt: dict,
    max_cost_cents: int = 20,
) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=SYSTEM_USER_ID,
        correlation_id=request_id,
        request_id=request_id,
        prompt=prompt,
        max_cost_cents=max_cost_cents,
    )


@pytest.mark.asyncio
async def test_b16_p1_investigation_persists_authority_contract(test_tenant: UUID) -> None:
    request_id = f"b16-p1-investigation-{uuid4().hex[:8]}"
    expected_summary = "investigation-authority-summary"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await run_investigation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={"simulated_output_text": expected_summary, "cache_enabled": False},
            ),
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

    assert contract.authority_contract_version == "b1.6-p1"
    assert contract.deterministic_authority.authority_class == "deterministic_authority"
    assert contract.llm_synthesis.authority_class == "validated_synthesis"
    assert contract.llm_synthesis.validation_state == "pending_validation"
    assert contract.llm_audit.authority_class == "audit_only_raw_provider_artifact"
    assert contract.llm_audit.provider_summary_raw == expected_summary
    assert contract.validation_context.feature_surface == "investigation"

    findings, synthesis = coerce_investigation_payload(job)
    assert isinstance(findings, list)
    assert synthesis is not None
    assert synthesis["authority_class"] == "validated_synthesis"
    assert synthesis["non_authoritative_summary"] == expected_summary


@pytest.mark.asyncio
async def test_b16_p1_budget_persists_authority_contract(test_tenant: UUID) -> None:
    request_id = f"b16-p1-budget-{uuid4().hex[:8]}"
    expected_summary = "budget-authority-summary"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await optimize_budget(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={
                    "simulated_output_text": expected_summary,
                    "optimization_goal": "maximize_revenue",
                    "cache_enabled": False,
                },
            ),
            session=session,
        )
        assert result["status"] == "accepted"

        record = await BudgetJobService().get_by_id(
            session,
            tenant_id=test_tenant,
            job_id=UUID(result["budget_job_id"]),
        )
        contract = BudgetResultAuthorityPayload.model_validate(record.result or {})

    assert contract.authority_contract_version == "b1.6-p1"
    assert contract.deterministic_authority.authority_class == "deterministic_authority"
    assert contract.llm_synthesis.authority_class == "validated_synthesis"
    assert contract.llm_synthesis.validation_state == "pending_validation"
    assert contract.llm_audit.authority_class == "audit_only_raw_provider_artifact"
    assert contract.llm_audit.provider_summary_raw == expected_summary
    assert contract.validation_context.feature_surface == "budget"

    recommendation, synthesis = coerce_budget_payload(record)
    assert isinstance(recommendation, dict)
    assert synthesis is not None
    assert synthesis["authority_class"] == "validated_synthesis"
    assert synthesis["non_authoritative_summary"] == expected_summary

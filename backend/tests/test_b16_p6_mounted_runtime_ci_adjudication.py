from __future__ import annotations

from uuid import UUID, uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api.budget import BudgetRecommendationResponse
from app.api.investigations import InvestigationResultResponse
from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.llm.authority_contract import (
    BudgetResultAuthorityPayload,
    InvestigationResultAuthorityPayload,
)
from app.main import app
from app.models.llm import LLMApiCall, LLMSemanticCache
from app.schemas.llm_payloads import LLMTaskPayload
from app.security.auth import mint_internal_jwt
from app.services.budget_job import BudgetJobService
from app.services.llm_dispatch import _payload_to_envelope, _payload_to_kwargs
from app.services.investigation import InvestigationService
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER
from app.tasks.llm import llm_budget_optimization_worker, llm_investigation_worker
from app.workers.llm import _PROVIDER_BOUNDARY


HALLUCINATED_SUMMARY = "Projected ROAS is 10.5 and revenue is 12000."
VALIDATED_SUMMARY = "Projected ROAS is 3.2 and revenue is 12000."
NUMERIC_BINDINGS = [
    {"claim_path": "summary.roas", "truth_path": "roas"},
    {"claim_path": "summary.revenue", "truth_path": "revenue"},
]
DETERMINISTIC_TRUTH = {"roas": 3.2, "revenue": 12000.0}


def _token_for(tenant_id: UUID, user_id: UUID) -> str:
    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=user_id,
        expires_in_seconds=3600,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )


def _headers(token: str, *, correlation_id: UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Correlation-ID": str(correlation_id),
    }


def _with_numeric_validation_context(
    payload: LLMTaskPayload,
    *,
    cache_enabled: bool,
    cache_watermark: int | None = None,
) -> LLMTaskPayload:
    prompt = dict(payload.prompt or {})
    prompt["cache_enabled"] = cache_enabled
    prompt["deterministic_truth"] = dict(DETERMINISTIC_TRUTH)
    prompt["numeric_claim_bindings"] = list(NUMERIC_BINDINGS)
    if cache_watermark is not None:
        prompt["cache_watermark"] = int(cache_watermark)
    return payload.model_copy(update={"prompt": prompt})


def _execute_captured_task(task_name: str, payload: LLMTaskPayload) -> dict:
    if task_name == "investigation":
        task = llm_investigation_worker
    elif task_name == "budget_optimization":
        task = llm_budget_optimization_worker
    else:  # pragma: no cover - defensive guard for harness integrity
        raise AssertionError(f"unsupported task_name={task_name}")

    headers = {
        AUTHORITY_ENVELOPE_HEADER: _payload_to_envelope(payload).model_dump(mode="json")
    }
    result = task.apply(kwargs=_payload_to_kwargs(payload), headers=headers)
    return result.get(propagate=True)


async def _load_api_call_with_visible_rls_user(
    *,
    tenant_id: UUID,
    api_call_id: UUID,
    request_user_id: UUID,
) -> tuple[UUID, LLMApiCall]:
    for candidate_user_id in (request_user_id, SYSTEM_USER_ID):
        async with get_session(tenant_id=tenant_id, user_id=candidate_user_id) as session:
            row = (
                await session.execute(
                    select(LLMApiCall).where(LLMApiCall.id == api_call_id)
                )
            ).scalars().first()
            if row is not None:
                return candidate_user_id, row
    raise AssertionError(
        f"llm_api_call not visible under request/system RLS scope: {api_call_id}"
    )


@pytest.fixture(autouse=True)
def _b16_p6_runtime_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")

    async def _no_revocation(_token_claims):
        return None

    def _decode_without_verification(token: str):
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )

    monkeypatch.setattr("app.security.auth._decode_token", _decode_without_verification)
    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation)


@pytest.mark.asyncio
async def test_b16_p6_mounted_investigation_hallucination_blocked_before_persistence_and_response(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    request_correlation_id = uuid4()
    request_id = str(request_correlation_id)
    captured_tasks: list[tuple[str, LLMTaskPayload]] = []

    async def _provider_hallucination(*, requested_model, prompt, reservation):
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": HALLUCINATED_SUMMARY,
            "reasoning_trace": {"trace_type": "b16-p6-mounted-investigation"},
            "response_metadata": {"source": "b16-p6-mounted-investigation"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    def _capture_enqueue(task_name: str, payload: LLMTaskPayload) -> None:
        captured_tasks.append((task_name, _with_numeric_validation_context(payload, cache_enabled=False)))

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_hallucination, raising=True)
    monkeypatch.setattr("app.api.investigations.enqueue_llm_task", _capture_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch = await client.post(
            "/api/investigations",
            json={"question": "Why did deterministic ROAS decline this week?"},
            headers=_headers(token, correlation_id=request_correlation_id),
        )
        assert launch.status_code == 202, launch.text
        investigation_id = UUID(launch.json()["investigation_id"])

    assert len(captured_tasks) == 1
    _execute_captured_task(*captured_tasks[0])

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        result_response = await client.get(
            f"/api/investigations/{investigation_id}",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert result_response.status_code == 200, result_response.text
        result_body = InvestigationResultResponse.model_validate(result_response.json())
        assert result_body.llm_synthesis is None
        assert result_body.deterministic_findings

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        authority_job = await InvestigationService(min_hold_seconds=0).get_job(
            session,
            tenant_id=test_tenant,
            job_id=investigation_id,
        )
        assert authority_job is not None
        authority_payload = InvestigationResultAuthorityPayload.model_validate(authority_job.result or {})

        trace_summary = (
            await session.execute(
                text(
                    """
                    SELECT COALESCE(result ->> 'summary', '')
                    FROM investigations
                    WHERE tenant_id = :tenant_id
                      AND request_id = :request_id
                      AND lifecycle_role = 'internal_trace'
                    """
                ),
                {"tenant_id": str(test_tenant), "request_id": request_id},
            )
        ).scalar_one()

        failure_count = int(
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

    assert authority_payload.llm_synthesis.validation_state == "rejected"
    assert HALLUCINATED_SUMMARY in authority_payload.llm_audit.provider_summary_raw
    assert HALLUCINATED_SUMMARY not in authority_payload.llm_synthesis.non_authoritative_summary
    assert trace_summary == ""
    assert failure_count >= 1


@pytest.mark.asyncio
async def test_b16_p6_mounted_budget_hallucination_blocked_before_persistence_and_response(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    request_correlation_id = uuid4()
    request_id = str(request_correlation_id)
    captured_tasks: list[tuple[str, LLMTaskPayload]] = []

    async def _provider_hallucination(*, requested_model, prompt, reservation):
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": HALLUCINATED_SUMMARY,
            "reasoning_trace": {"trace_type": "b16-p6-mounted-budget"},
            "response_metadata": {"source": "b16-p6-mounted-budget"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    def _capture_enqueue(task_name: str, payload: LLMTaskPayload) -> None:
        captured_tasks.append((task_name, _with_numeric_validation_context(payload, cache_enabled=False)))

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_hallucination, raising=True)
    monkeypatch.setattr("app.api.budget.enqueue_llm_task", _capture_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch = await client.post(
            "/api/budget/optimize",
            json={"total_budget": 10000, "optimization_goal": "maximize_roas"},
            headers=_headers(token, correlation_id=request_correlation_id),
        )
        assert launch.status_code == 202, launch.text
        budget_job_id = UUID(launch.json()["job_id"])

    assert len(captured_tasks) == 1
    _execute_captured_task(*captured_tasks[0])

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        result_response = await client.get(
            f"/api/budget/recommendations/{budget_job_id}",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert result_response.status_code == 200, result_response.text
        result_body = BudgetRecommendationResponse.model_validate(result_response.json())
        assert result_body.llm_synthesis is None
        assert result_body.deterministic_recommendation

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        authority_job = await BudgetJobService().get_by_id(
            session,
            tenant_id=test_tenant,
            job_id=budget_job_id,
        )
        authority_payload = BudgetResultAuthorityPayload.model_validate(authority_job.result or {})

        trace_summary = (
            await session.execute(
                text(
                    """
                    SELECT COALESCE(recommendations ->> 'provider_summary', '')
                    FROM budget_optimization_jobs
                    WHERE tenant_id = :tenant_id
                      AND request_id = :request_id
                      AND lifecycle_role = 'internal_trace'
                    """
                ),
                {"tenant_id": str(test_tenant), "request_id": request_id},
            )
        ).scalar_one()

        failure_count = int(
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

    assert authority_payload.llm_synthesis.validation_state == "rejected"
    assert HALLUCINATED_SUMMARY in authority_payload.llm_audit.provider_summary_raw
    assert HALLUCINATED_SUMMARY not in authority_payload.llm_synthesis.non_authoritative_summary
    assert trace_summary == ""
    assert failure_count >= 1


@pytest.mark.asyncio
async def test_b16_p6_mounted_cache_replay_hallucination_rejected_without_provider_reentry(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    request_one = uuid4()
    request_two = uuid4()
    cache_watermark = 916
    provider_calls = {"count": 0}
    captured_tasks: list[tuple[str, LLMTaskPayload]] = []

    async def _provider_valid(*, requested_model, prompt, reservation):
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": VALIDATED_SUMMARY,
            "reasoning_trace": {"trace_type": "b16-p6-mounted-cache-seed"},
            "response_metadata": {"source": "b16-p6-mounted-cache-seed"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    def _capture_enqueue(task_name: str, payload: LLMTaskPayload) -> None:
        captured_tasks.append(
            (
                task_name,
                _with_numeric_validation_context(
                    payload,
                    cache_enabled=True,
                    cache_watermark=cache_watermark,
                ),
            )
        )

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_valid, raising=True)
    monkeypatch.setattr("app.api.investigations.enqueue_llm_task", _capture_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch_one = await client.post(
            "/api/investigations",
            json={"question": "Why did blended CAC drift over the last 30 days?"},
            headers=_headers(token, correlation_id=request_one),
        )
        assert launch_one.status_code == 202, launch_one.text

    assert len(captured_tasks) == 1
    first_task_result = _execute_captured_task(*captured_tasks.pop(0))
    first_api_call_id = first_task_result.get("api_call_id")
    assert first_api_call_id is not None

    cache_scope_user_id, _ = await _load_api_call_with_visible_rls_user(
        tenant_id=test_tenant,
        api_call_id=UUID(str(first_api_call_id)),
        request_user_id=user_id,
    )

    async with get_session(tenant_id=test_tenant, user_id=cache_scope_user_id) as session:
        call_one = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.id == UUID(str(first_api_call_id)),
                )
            )
        ).scalars().one()
        cache_row = (
            await session.execute(
                select(LLMSemanticCache).where(
                    LLMSemanticCache.tenant_id == test_tenant,
                    LLMSemanticCache.user_id == call_one.user_id,
                    LLMSemanticCache.endpoint == "app.tasks.llm.investigation",
                    LLMSemanticCache.cache_key == call_one.cache_key,
                )
            )
        ).scalars().one()
        cache_row.response_text = HALLUCINATED_SUMMARY
        await session.commit()

    async def _provider_spy(*, requested_model, prompt, reservation):
        provider_calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": VALIDATED_SUMMARY,
            "reasoning_trace": {"trace_type": "b16-p6-mounted-cache-replay"},
            "response_metadata": {"source": "b16-p6-mounted-cache-replay"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_spy, raising=True)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch_two = await client.post(
            "/api/investigations",
            json={"question": "Why did blended CAC drift over the last 30 days?"},
            headers=_headers(token, correlation_id=request_two),
        )
        assert launch_two.status_code == 202, launch_two.text
        investigation_id = UUID(launch_two.json()["investigation_id"])

    assert len(captured_tasks) == 1
    second_task_result = _execute_captured_task(*captured_tasks.pop(0))
    second_api_call_id = second_task_result.get("api_call_id")
    assert second_api_call_id is not None

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        result_response = await client.get(
            f"/api/investigations/{investigation_id}",
            headers=_headers(token, correlation_id=uuid4()),
        )
        assert result_response.status_code == 200, result_response.text
        result_body = InvestigationResultResponse.model_validate(result_response.json())
        assert result_body.llm_synthesis is None
        assert result_body.deterministic_findings

    call_scope_user_id, _ = await _load_api_call_with_visible_rls_user(
        tenant_id=test_tenant,
        api_call_id=UUID(str(second_api_call_id)),
        request_user_id=user_id,
    )

    async with get_session(tenant_id=test_tenant, user_id=call_scope_user_id) as session:
        call_two = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.id == UUID(str(second_api_call_id)),
                )
            )
        ).scalars().one()
        failure_count = int(
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
                    {"tenant_id": str(test_tenant), "request_id": str(request_two)},
                )
            ).scalar_one()
        )

    assert provider_calls["count"] == 0
    assert second_task_result.get("was_cached") is True
    assert second_task_result.get("validation_code") == "numeric_mismatch"
    assert second_task_result.get("validation_stage") == "cache"
    assert failure_count >= 1


@pytest.mark.asyncio
async def test_b16_p6_mounted_validation_failure_log_insert_is_required(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    user_id = uuid4()
    token = _token_for(test_tenant, user_id)
    request_correlation_id = uuid4()
    request_id = str(request_correlation_id)
    captured_tasks: list[tuple[str, LLMTaskPayload]] = []

    async def _provider_hallucination(*, requested_model, prompt, reservation):
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": HALLUCINATED_SUMMARY,
            "reasoning_trace": {"trace_type": "b16-p6-mounted-failure-log"},
            "response_metadata": {"source": "b16-p6-mounted-failure-log"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    def _capture_enqueue(task_name: str, payload: LLMTaskPayload) -> None:
        captured_tasks.append((task_name, _with_numeric_validation_context(payload, cache_enabled=False)))

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_hallucination, raising=True)
    monkeypatch.setattr("app.api.investigations.enqueue_llm_task", _capture_enqueue)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        launch = await client.post(
            "/api/investigations",
            json={"question": "Which channels had deterministic ROAS inversion?"},
            headers=_headers(token, correlation_id=request_correlation_id),
        )
        assert launch.status_code == 202, launch.text

    assert len(captured_tasks) == 1
    _execute_captured_task(*captured_tasks[0])

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failure_count = int(
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

    assert failure_count >= 1

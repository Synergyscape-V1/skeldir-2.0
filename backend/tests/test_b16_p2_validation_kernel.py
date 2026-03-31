from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.core.identity import SYSTEM_USER_ID
from app.db.session import get_session
from app.models.llm import Investigation, LLMApiCall, LLMSemanticCache
from app.schemas.llm_payloads import LLMTaskPayload
from app.services.investigation import InvestigationService
from app.workers.llm import (
    _ENDPOINT_VALIDATION_SPECS,
    _PROVIDER_BOUNDARY,
    generate_explanation,
    run_investigation,
)


def _payload(
    tenant_id: UUID,
    *,
    request_id: str,
    prompt: dict,
    max_cost_cents: int = 25,
) -> LLMTaskPayload:
    return LLMTaskPayload(
        tenant_id=tenant_id,
        user_id=SYSTEM_USER_ID,
        correlation_id=request_id,
        request_id=request_id,
        prompt=prompt,
        max_cost_cents=max_cost_cents,
    )


def test_b16_p2_schema_binding_covers_all_active_surfaces() -> None:
    expected_endpoints = {
        "app.tasks.llm.route",
        "app.tasks.llm.explanation",
        "app.tasks.llm.investigation",
        "app.tasks.llm.budget_optimization",
    }
    assert set(_ENDPOINT_VALIDATION_SPECS.keys()) == expected_endpoints
    for endpoint, spec in _ENDPOINT_VALIDATION_SPECS.items():
        assert spec is not None, endpoint
        assert spec.schema_key
        assert spec.surface
        assert spec.max_attempts >= 1


@pytest.mark.asyncio
async def test_b16_p2_normalization_and_schema_fail_closed(test_tenant: UUID) -> None:
    ok_request = f"b16-p2-ok-{uuid4().hex[:8]}"
    malformed_request = f"b16-p2-malformed-{uuid4().hex[:8]}"
    invalid_request = f"b16-p2-structural-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        ok = await generate_explanation(
            _payload(
                test_tenant,
                request_id=ok_request,
                prompt={
                    "simulated_output_text": "```json\n{\"explanation\":\"normalized fenced\"}\n```",
                    "cache_enabled": False,
                },
            ),
            session=session,
        )
        malformed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=malformed_request,
                prompt={
                    "simulated_output_text": "{\"explanation\":\"unterminated\"",
                    "cache_enabled": False,
                },
            ),
            session=session,
        )
        structural = await generate_explanation(
            _payload(
                test_tenant,
                request_id=invalid_request,
                prompt={
                    "simulated_output_text": "{\"summary\":\"wrong field\"}",
                    "cache_enabled": False,
                },
            ),
            session=session,
        )

    assert ok["status"] == "accepted"
    assert ok["explanation"] == "normalized fenced"
    assert ok["validation_code"] == "success"

    assert malformed["status"] == "failed"
    assert malformed["failure_reason"] == "validation_normalization_failed"
    assert malformed["validation_code"] == "normalization_failed"

    assert structural["status"] == "failed"
    assert structural["failure_reason"] == "validation_schema_failed"
    assert structural["validation_code"] == "schema_failed"


@pytest.mark.asyncio
async def test_b16_p2_cache_invalid_payload_is_evicted_then_fresh_path_runs(
    test_tenant: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_request = f"b16-p2-cache-seed-{uuid4().hex[:8]}"
    replay_request = f"b16-p2-cache-replay-{uuid4().hex[:8]}"
    prompt = {
        "simulated_output_text": "{\"explanation\":\"seed value\"}",
        "cache_enabled": True,
        "cache_watermark": 13,
    }

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        seeded = await generate_explanation(
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
                    LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    LLMApiCall.request_id == seed_request,
                )
            )
        ).scalars().one()
        assert seed_call.cache_key
        cache_row = (
            await session.execute(
                select(LLMSemanticCache).where(
                    LLMSemanticCache.tenant_id == test_tenant,
                    LLMSemanticCache.user_id == SYSTEM_USER_ID,
                    LLMSemanticCache.endpoint == "app.tasks.llm.explanation",
                    LLMSemanticCache.cache_key == seed_call.cache_key,
                )
            )
        ).scalars().one()
        cache_row.response_text = "{\"explanation\":\"broken\""
        await session.commit()

    provider_calls = {"count": 0}

    async def _provider_spy(*, requested_model, prompt, reservation):
        provider_calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "{\"explanation\":\"fresh after invalid cache\"}",
            "reasoning_trace": {"trace_type": "b16-p2-cache"},
            "response_metadata": {"source": "b16-p2-cache"},
            "usage": {"input_tokens": 1, "output_tokens": 1, "cost_cents": 1},
        }

    monkeypatch.setattr(_PROVIDER_BOUNDARY, "_provider_call", _provider_spy, raising=True)

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        replay = await generate_explanation(
            _payload(test_tenant, request_id=replay_request, prompt=prompt),
            session=session,
        )

        replay_call = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.user_id == SYSTEM_USER_ID,
                    LLMApiCall.endpoint == "app.tasks.llm.explanation",
                    LLMApiCall.request_id == replay_request,
                )
            )
        ).scalars().one()
        cache_row = (
            await session.execute(
                select(LLMSemanticCache).where(
                    LLMSemanticCache.tenant_id == test_tenant,
                    LLMSemanticCache.user_id == SYSTEM_USER_ID,
                    LLMSemanticCache.endpoint == "app.tasks.llm.explanation",
                    LLMSemanticCache.cache_key == replay_call.cache_key,
                )
            )
        ).scalars().one()

    assert replay["status"] == "accepted"
    assert replay["was_cached"] is False
    assert replay["explanation"] == "fresh after invalid cache"
    assert replay["validation_code"] == "success"
    assert provider_calls["count"] == 1
    assert cache_row.response_text == "fresh after invalid cache"


@pytest.mark.asyncio
async def test_b16_p2_invalid_output_blocked_before_investigation_success_sinks(
    test_tenant: UUID,
) -> None:
    request_id = f"b16-p2-investigation-invalid-{uuid4().hex[:8]}"
    malformed = "{\"summary\":\"not closed\""

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        result = await run_investigation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={"simulated_output_text": malformed, "cache_enabled": False},
            ),
            session=session,
        )

        api_call = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == test_tenant,
                    LLMApiCall.user_id == SYSTEM_USER_ID,
                    LLMApiCall.endpoint == "app.tasks.llm.investigation",
                    LLMApiCall.request_id == request_id,
                )
            )
        ).scalars().one()
        trace_row = (
            await session.execute(
                select(Investigation).where(
                    Investigation.tenant_id == test_tenant,
                    Investigation.request_id == request_id,
                )
            )
        ).scalars().one()
        job = await InvestigationService(min_hold_seconds=0).get_job(
            session,
            tenant_id=test_tenant,
            job_id=UUID(result["investigation_id"]),
        )

    assert result["status"] == "failed"
    assert result["failure_reason"] == "validation_normalization_failed"
    assert result["validation_code"] == "normalization_failed"
    assert (api_call.response_metadata_ref or {}).get("output_text", "") == ""
    assert (trace_row.result or {}).get("summary", "") == ""
    assert job is not None
    assert job.failure_reason == "validation_normalization_failed"


@pytest.mark.asyncio
async def test_b16_p2_records_validation_failure_rows(test_tenant: UUID) -> None:
    request_id = f"b16-p2-sink-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        failed = await generate_explanation(
            _payload(
                test_tenant,
                request_id=request_id,
                prompt={
                    "simulated_output_text": "{\"summary\":\"schema wrong\"}",
                    "cache_enabled": False,
                },
            ),
            session=session,
        )
        assert failed["status"] == "failed"

        count = int(
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
    assert count >= 1

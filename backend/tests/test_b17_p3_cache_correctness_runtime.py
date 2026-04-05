"""B1.7-P3 runtime and seam proofs for cache correctness and truth coherence."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api import attribution as attribution_api
from app.db.session import AsyncSessionLocal, get_session, set_tenant_guc_async
from app.llm.provider_boundary import _cache_key
from app.main import app
from app.models.llm import LLMApiCall, LLMSemanticCache
from app.security.auth import mint_internal_jwt
from tests.builders.core_builders import build_attribution_allocation


def _token_for(*, tenant_id: UUID, user_id: UUID | None = None) -> str:
    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=user_id or uuid4(),
        expires_in_seconds=3600,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )


async def _seed_revenue_cache_entry(
    *, tenant_id: UUID, total_revenue_cents: int
) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        await set_tenant_guc_async(session, tenant_id, local=False)
        await session.execute(
            text(
                """
                INSERT INTO revenue_cache_entries (
                    tenant_id,
                    cache_key,
                    payload,
                    data_as_of,
                    expires_at,
                    error_cooldown_until,
                    last_error_at,
                    last_error_message,
                    etag,
                    created_at,
                    updated_at
                ) VALUES (
                    :tenant_id,
                    :cache_key,
                    CAST(:payload AS jsonb),
                    :data_as_of,
                    :expires_at,
                    NULL,
                    NULL,
                    NULL,
                    :etag,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (tenant_id, cache_key) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    data_as_of = EXCLUDED.data_as_of,
                    expires_at = EXCLUDED.expires_at,
                    etag = EXCLUDED.etag,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "cache_key": "realtime_revenue:shared:v1",
                "payload": json.dumps(
                    {
                        "tenant_id": str(tenant_id),
                        "revenue_total_cents": int(total_revenue_cents),
                        "data_as_of": now.isoformat(),
                        "verified": False,
                    }
                ),
                "data_as_of": now,
                "expires_at": now + timedelta(minutes=5),
                "etag": f'"seed-{tenant_id.hex[:8]}"',
                "created_at": now,
                "updated_at": now,
            },
        )
        await session.commit()


async def _set_allocation_revenue(
    *, tenant_id: UUID, allocation_id: UUID, amount_cents: int
) -> None:
    async with AsyncSessionLocal() as session:
        await set_tenant_guc_async(session, tenant_id, local=False)
        await session.execute(
            text(
                """
                UPDATE attribution_allocations
                SET allocated_revenue_cents = :amount_cents,
                    confidence_score = 0.91,
                    model_type = 'deterministic',
                    model_version = '1.0.0',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :allocation_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "allocation_id": str(allocation_id),
                "amount_cents": int(amount_cents),
            },
        )
        await session.commit()


async def _call_explain(
    *,
    tenant_id: UUID,
    allocation_id: UUID,
    correlation_id: UUID,
    user_id: UUID,
) -> tuple[int, dict]:
    token = _token_for(tenant_id=tenant_id, user_id=user_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/attribution/explain/channel_performance/{allocation_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Correlation-ID": str(correlation_id),
            },
        )
    return response.status_code, response.json()


async def _fetch_api_call(
    *, tenant_id: UUID, request_id: str, user_id: UUID
) -> LLMApiCall:
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        row = (
            (
                await session.execute(
                    select(LLMApiCall).where(
                        LLMApiCall.tenant_id == tenant_id,
                        LLMApiCall.endpoint
                        == "app.api.attribution.explanation_fastpath",
                        LLMApiCall.request_id == request_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if row is None:  # pragma: no cover - explicit assertion guard
            raise AssertionError(f"missing llm_api_call for request_id={request_id}")
        return row


@pytest.fixture(autouse=True)
def _force_runtime_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")

    async def _no_revocation(_token_claims):
        return None

    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation)


def test_b17_p3_cache_identity_uses_determinants_and_not_prompt_text() -> None:
    base_identity = {
        "metric_identity": {
            "entity_type": "channel_performance",
            "entity_id": "11111111-1111-1111-1111-111111111111",
            "metric_key": "channel_performance_revenue",
        },
        "filter_window": {
            "filter_profile": "entity_scope_default",
            "time_range": "latest_truth_snapshot",
        },
        "tenant_user_scope": {
            "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "user_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        },
        "explanation_contract_version": "b1.7-p3",
        "model_tier_profile": "cheap",
    }
    endpoint = "app.api.attribution.explanation_fastpath"
    model_name = "stub:model"
    base_prompt = {
        "messages": [{"role": "user", "content": "original prompt"}],
        "simulated_output_text": "original-output",
        "cache_enabled": True,
        "cache_watermark": 101,
        "cache_identity": base_identity,
    }
    base_key = _cache_key(base_prompt, endpoint, model_name)

    prompt_text_mutation = copy.deepcopy(base_prompt)
    prompt_text_mutation["messages"][0][
        "content"
    ] = "different text should not change key"
    prompt_text_mutation["simulated_output_text"] = "different-output"
    assert _cache_key(prompt_text_mutation, endpoint, model_name) == base_key

    for field, value in (
        ("metric_identity", {"entity_type": "attribution_score"}),
        ("filter_window", {"time_range": "30d"}),
        ("tenant_user_scope", {"user_id": "cccccccc-cccc-cccc-cccc-cccccccccccc"}),
        ("explanation_contract_version", "b1.7-p3-hotfix"),
        ("model_tier_profile", "standard"),
    ):
        mutated = copy.deepcopy(base_prompt)
        if isinstance(value, dict):
            mutated["cache_identity"][field].update(value)
        else:
            mutated["cache_identity"][field] = value
        assert _cache_key(mutated, endpoint, model_name) != base_key, field


@pytest.mark.asyncio
async def test_b17_p3_structured_truth_snapshot_is_coherent_on_cold_and_cache_hit(
    test_tenant: UUID,
) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    request_user_id = uuid4()
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=45275,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=12543050)

    corr_one = uuid4()
    status_one, body_one = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=corr_one,
        user_id=request_user_id,
    )
    assert status_one == 200
    truth_one = body_one["authoritative_metric"]["truth_snapshot"]
    assert truth_one == body_one["non_authoritative_explanation"]["truth_snapshot"]
    assert body_one["non_authoritative_explanation"]["cache_replay_state"] == (
        "cold_miss_provider_allowed"
    )

    corr_two = uuid4()
    status_two, body_two = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=corr_two,
        user_id=request_user_id,
    )
    assert status_two == 200
    truth_two = body_two["authoritative_metric"]["truth_snapshot"]
    assert truth_two == body_two["non_authoritative_explanation"]["truth_snapshot"]
    assert body_two["non_authoritative_explanation"]["cache_replay_state"] == (
        "cache_hit_truth_match"
    )

    api_call_two = await _fetch_api_call(
        tenant_id=test_tenant,
        request_id=str(corr_two),
        user_id=request_user_id,
    )
    assert api_call_two.was_cached is True
    async with get_session(tenant_id=test_tenant, user_id=request_user_id) as session:
        cache_row = (
            (
                await session.execute(
                    select(LLMSemanticCache).where(
                        LLMSemanticCache.tenant_id == test_tenant,
                        LLMSemanticCache.user_id == request_user_id,
                        LLMSemanticCache.endpoint
                        == "app.api.attribution.explanation_fastpath",
                        LLMSemanticCache.cache_key == api_call_two.cache_key,
                    )
                )
            )
            .scalars()
            .one()
        )
    metadata = dict(cache_row.response_metadata_ref or {})
    assert metadata.get("truth_snapshot") == truth_two


@pytest.mark.asyncio
async def test_b17_p3_stale_replay_is_rejected_without_provider_reentry(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    async def _no_prewarm_targets(**_kwargs):
        return 0

    monkeypatch.setattr(
        attribution_api,
        "_execute_b17_prewarm_targets",
        _no_prewarm_targets,
        raising=True,
    )

    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    request_user_id = uuid4()
    provider_calls = {"count": 0}

    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=31888,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=6000000)

    corr_seed = uuid4()
    seed_status, _ = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=corr_seed,
        user_id=request_user_id,
    )
    assert seed_status == 200

    async def _provider_spy(*, requested_model, prompt, reservation):
        provider_calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "metric_value_cents 31888 revenue_total_cents 6000000",
            "reasoning_trace": {"trace_type": "b17-p3-provider-spy"},
            "response_metadata": {"source": "b17-p3-provider-spy"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    monkeypatch.setattr(
        attribution_api._PROVIDER_BOUNDARY,
        "_provider_call",
        _provider_spy,
        raising=True,
    )

    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=45001,
    )

    provider_calls_before_stale = provider_calls["count"]
    corr_stale = uuid4()
    stale_status, stale_body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=corr_stale,
        user_id=request_user_id,
    )
    assert stale_status == 200
    explanation = stale_body["non_authoritative_explanation"]
    assert explanation["synthesis_state"] == "stale_replay_rejected"
    assert explanation["degraded"] is True
    assert explanation["cache_replay_state"] == "stale_replay_rejected_provider_blocked"
    assert explanation["provider_reentry_blocked"] is True
    assert (
        stale_body["authoritative_metric"]["truth_snapshot"]
        == explanation["truth_snapshot"]
    )
    assert explanation["prewarm_state"]["trigger_reason"] == "stale_replay_path_suppressed"
    assert explanation["prewarm_state"]["triggered"] is False

    assert provider_calls["count"] == provider_calls_before_stale
    stale_call = await _fetch_api_call(
        tenant_id=test_tenant,
        request_id=str(corr_stale),
        user_id=request_user_id,
    )
    assert stale_call.status == "blocked"
    assert stale_call.block_reason == "stale_replay_rejected"
    assert stale_call.provider_attempted is False
    stale_metadata = dict(stale_call.response_metadata_ref or {})
    assert (
        stale_metadata.get("cache_replay_state")
        == "stale_replay_rejected_provider_blocked"
    )

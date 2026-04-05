"""B1.7-P4 runtime strategy-closure proofs."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.api import attribution as attribution_api
from app.db.session import AsyncSessionLocal, get_session, set_tenant_guc_async
from app.main import app
from app.models.llm import LLMApiCall
from app.security.auth import mint_internal_jwt
from app.services.attribution_explanation_authority import (
    fetch_attribution_explanation_authority,
)
from app.services.b17_p4_prewarm_policy import plan_b17_p4_event_driven_prewarm
from tests.builders.core_builders import build_attribution_allocation

pytestmark = pytest.mark.asyncio


def _token_for(*, tenant_id: UUID, user_id: UUID | None = None) -> str:
    return mint_internal_jwt(
        tenant_id=tenant_id,
        user_id=user_id or uuid4(),
        expires_in_seconds=3600,
        additional_claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )


async def _seed_revenue_cache_entry(*, tenant_id: UUID, total_revenue_cents: int) -> None:
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
                "etag": f"\"seed-{tenant_id.hex[:8]}\"",
                "created_at": now,
                "updated_at": now,
            },
        )
        await session.commit()


async def _set_allocation_revenue(*, tenant_id: UUID, allocation_id: UUID, amount_cents: int) -> None:
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
    entity_type: str,
    correlation_id: UUID,
    user_id: UUID,
) -> tuple[int, dict]:
    token = _token_for(tenant_id=tenant_id, user_id=user_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/attribution/explain/{entity_type}/{allocation_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Correlation-ID": str(correlation_id),
            },
        )
    return response.status_code, response.json()


async def _fetch_api_call(*, tenant_id: UUID, request_id: str, user_id: UUID) -> LLMApiCall:
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        row = (
            await session.execute(
                select(LLMApiCall).where(
                    LLMApiCall.tenant_id == tenant_id,
                    LLMApiCall.endpoint == "app.api.attribution.explanation_fastpath",
                    LLMApiCall.request_id == request_id,
                )
            )
        ).scalars().first()
        if row is None:  # pragma: no cover - explicit assertion guard
            raise AssertionError(f"missing llm_api_call for request_id={request_id}")
        return row


@pytest.fixture(autouse=True)
def _force_runtime_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")

    async def _no_revocation(_token_claims):
        return None

    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation)


async def test_b17_p4_execution_state_cold_then_warm_is_machine_observable(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    monkeypatch.setattr(
        attribution_api.settings, "LLM_B17_PREWARM_ENABLED", False, raising=False
    )
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    request_user_id = uuid4()
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=45275,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=12543050)

    cold_status, cold_body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        entity_type="channel_performance",
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert cold_status == 200
    cold_explanation = cold_body["non_authoritative_explanation"]
    assert cold_explanation["execution_path_state"] == "cold_path_generated"
    assert cold_explanation["cache_replay_state"] == "cold_miss_provider_allowed"
    assert cold_explanation["cold_path_strategy"] == "prewarm_required_event_driven_bounded"
    assert cold_explanation["prewarm_state"]["trigger_reason"] == "prewarm_disabled"

    warm_status, warm_body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        entity_type="channel_performance",
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert warm_status == 200
    warm_explanation = warm_body["non_authoritative_explanation"]
    assert warm_explanation["execution_path_state"] == "warm_cache_hit"
    assert warm_explanation["cache_replay_state"] == "cache_hit_truth_match"


async def test_b17_p4_stale_rejection_state_suppresses_prewarm_dispatch(
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
    monkeypatch.setattr(
        attribution_api.settings, "LLM_B17_PREWARM_ENABLED", True, raising=False
    )

    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    request_user_id = uuid4()

    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=31888,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=6000000)

    seed_status, _ = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        entity_type="channel_performance",
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert seed_status == 200

    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=45001,
    )
    stale_correlation = uuid4()
    stale_status, stale_body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        entity_type="channel_performance",
        correlation_id=stale_correlation,
        user_id=request_user_id,
    )
    assert stale_status == 200
    explanation = stale_body["non_authoritative_explanation"]
    assert explanation["execution_path_state"] == "stale_rejected_provider_blocked"
    assert explanation["cache_replay_state"] == "stale_replay_rejected_provider_blocked"
    assert explanation["provider_reentry_blocked"] is True
    assert explanation["prewarm_state"]["trigger_reason"] == "stale_replay_path_suppressed"
    assert explanation["prewarm_state"]["triggered"] is False

    api_call = await _fetch_api_call(
        tenant_id=test_tenant,
        request_id=str(stale_correlation),
        user_id=request_user_id,
    )
    assert api_call.status == "blocked"
    assert api_call.provider_attempted is False


async def test_b17_p4_prewarm_assisted_cache_hit_is_observable(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    monkeypatch.setattr(
        attribution_api.settings, "LLM_B17_PREWARM_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        attribution_api.settings, "LLM_B17_PREWARM_RUN_SYNC", True, raising=False
    )
    monkeypatch.setattr(
        attribution_api.settings,
        "LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES",
        "channel_performance,attribution_score",
        raising=False,
    )
    monkeypatch.setattr(
        attribution_api.settings,
        "LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER",
        2,
        raising=False,
    )

    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    request_user_id = uuid4()
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=50000,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=9000000)

    first_status, _ = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        entity_type="channel_performance",
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert first_status == 200

    second_status, second_body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        entity_type="attribution_score",
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert second_status == 200
    explanation = second_body["non_authoritative_explanation"]
    assert explanation["cache_replay_state"] == "cache_hit_truth_match"
    assert explanation["execution_path_state"] == "prewarm_assisted_cache_hit"
    assert explanation["prewarm_state"]["assisted_cache_hit"] is True


async def test_b17_p4_policy_caps_and_watermark_state_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    monkeypatch.setattr(
        attribution_api.settings, "LLM_B17_PREWARM_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        attribution_api.settings, "LLM_B17_PREWARM_RUN_SYNC", True, raising=False
    )
    monkeypatch.setattr(
        attribution_api.settings,
        "LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES",
        "channel_performance,attribution_score",
        raising=False,
    )
    monkeypatch.setattr(
        attribution_api.settings,
        "LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER",
        2,
        raising=False,
    )
    monkeypatch.setattr(
        attribution_api.settings,
        "LLM_B17_PREWARM_MIN_TRIGGER_INTERVAL_SECONDS",
        0,
        raising=False,
    )
    monkeypatch.setattr(
        attribution_api.settings,
        "LLM_B17_PREWARM_MAX_CALLS_PER_TENANT_PER_HOUR",
        1,
        raising=False,
    )

    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    request_user_id = uuid4()
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=10000,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=910000)

    first_status, _ = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        entity_type="channel_performance",
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert first_status == 200

    async with get_session(tenant_id=test_tenant, user_id=request_user_id) as session:
        authority_before = await fetch_attribution_explanation_authority(
            db_session=session,
            tenant_id=test_tenant,
            entity_type="channel_performance",
            entity_id=allocation_id,
        )
        plan_for_same_watermark = await plan_b17_p4_event_driven_prewarm(
            db_session=session,
            tenant_id=test_tenant,
            user_id=request_user_id,
            entity_type="channel_performance",
            entity_id=allocation_id,
            truth_watermark=authority_before.truth_snapshot_watermark,
            endpoint="app.api.attribution.explanation_fastpath",
        )
    assert plan_for_same_watermark.reason == "already_prewarmed_for_watermark"
    assert plan_for_same_watermark.should_trigger is False

    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=20000,
    )
    async with get_session(tenant_id=test_tenant, user_id=request_user_id) as session:
        authority_after = await fetch_attribution_explanation_authority(
            db_session=session,
            tenant_id=test_tenant,
            entity_type="channel_performance",
            entity_id=allocation_id,
        )
        plan_after_truth_change = await plan_b17_p4_event_driven_prewarm(
            db_session=session,
            tenant_id=test_tenant,
            user_id=request_user_id,
            entity_type="channel_performance",
            entity_id=allocation_id,
            truth_watermark=authority_after.truth_snapshot_watermark,
            endpoint="app.api.attribution.explanation_fastpath",
        )
    assert plan_after_truth_change.reason == "tenant_hourly_cap_reached"
    assert plan_after_truth_change.should_trigger is False

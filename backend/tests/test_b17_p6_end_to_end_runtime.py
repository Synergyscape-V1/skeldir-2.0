"""B1.7-P6 full mounted end-to-end correctness proofs."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api import attribution as attribution_api
from app.db.session import AsyncSessionLocal, get_session, set_tenant_guc_async
from app.main import app
from app.security.auth import mint_internal_jwt
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
                "etag": f'"seed-{tenant_id.hex[:8]}"',
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


@pytest.fixture(autouse=True)
def _force_runtime_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")

    async def _no_revocation(_token_claims):
        return None

    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation)


async def test_b17_p6_full_mounted_response_preserves_authority_and_bounded_explanation(
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

    status_code, body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert status_code == 200
    authoritative = body["authoritative_metric"]
    explanation = body["non_authoritative_explanation"]
    assert authoritative["metric_value_cents"] == 45275
    assert authoritative["tenant_id"] == str(test_tenant)
    assert explanation["execution_path_state"] in {
        "warm_cache_hit",
        "cold_path_generated",
        "prewarm_assisted_cache_hit",
    }
    assert explanation["cache_replay_state"] in {
        "cold_miss_provider_allowed",
        "cache_hit_truth_match",
    }
    assert isinstance(explanation["non_authoritative_summary"], str)
    assert 0 < len(explanation["non_authoritative_summary"]) <= 320


async def test_b17_p6_invalid_numeric_injection_is_fail_closed(test_tenant: UUID) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    request_user_id = uuid4()
    correlation_id = uuid4()
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=31888,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=6000000)

    async def _provider_hallucinated(*, requested_model, prompt, reservation):
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "metric_value_cents 999999 revenue_total_cents 123",
            "reasoning_trace": {"trace_type": "b17-p6-hallucinated"},
            "response_metadata": {"source": "b17-p6-hallucinated"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    original = attribution_api._PROVIDER_BOUNDARY._provider_call
    attribution_api._PROVIDER_BOUNDARY._provider_call = _provider_hallucinated
    try:
        status_code, body = await _call_explain(
            tenant_id=test_tenant,
            allocation_id=allocation_id,
            correlation_id=correlation_id,
            user_id=request_user_id,
        )
    finally:
        attribution_api._PROVIDER_BOUNDARY._provider_call = original

    assert status_code == 200
    assert body["authoritative_metric"]["metric_value_cents"] == 31888
    explanation = body["non_authoritative_explanation"]
    assert explanation["synthesis_state"] == "validation_rejected"
    assert explanation["degraded_reason"] == "numeric_mismatch"
    assert explanation["execution_path_state"] in {"cold_path_generated", "warm_cache_hit"}

    async with get_session(tenant_id=test_tenant, user_id=request_user_id) as session:
        mismatch_count = int(
            (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_validation_failures
                        WHERE tenant_id = :tenant_id
                          AND endpoint = 'app.api.attribution.explanation_fastpath'
                          AND validation_error = 'numeric_mismatch'
                          AND request_payload ->> 'request_id' = :request_id
                        """
                    ),
                    {
                        "tenant_id": str(test_tenant),
                        "request_id": str(correlation_id),
                    },
                )
            ).scalar_one()
        )
    assert mismatch_count >= 1


async def test_b17_p6_stale_cache_replay_is_rejected_without_provider_reentry(
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

    seed_status, _ = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert seed_status == 200

    async def _provider_spy(*, requested_model, prompt, reservation):
        provider_calls["count"] += 1
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "metric_value_cents 31888 revenue_total_cents 6000000",
            "reasoning_trace": {"trace_type": "b17-p6-provider-spy"},
            "response_metadata": {"source": "b17-p6-provider-spy"},
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
    before = provider_calls["count"]
    stale_status, stale_body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=uuid4(),
        user_id=request_user_id,
    )
    assert stale_status == 200
    explanation = stale_body["non_authoritative_explanation"]
    assert explanation["synthesis_state"] == "stale_replay_rejected"
    assert explanation["cache_replay_state"] == "stale_replay_rejected_provider_blocked"
    assert explanation["provider_reentry_blocked"] is True
    assert explanation["execution_path_state"] == "stale_rejected_provider_blocked"
    assert provider_calls["count"] == before

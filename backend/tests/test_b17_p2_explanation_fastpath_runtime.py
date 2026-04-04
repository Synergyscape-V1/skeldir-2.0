"""B1.7-P2 mounted runtime proofs for fast-path sidecar behavior."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import desc, select, text

from app.api import attribution as attribution_api
from app.core.config import settings
from app.db.session import AsyncSessionLocal, get_session, set_tenant_guc_async
from app.main import app
from app.models.llm import LLMApiCall
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


async def _fetch_api_call(*, tenant_id: UUID, request_id: str, user_id: UUID) -> LLMApiCall:
    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        row = (
            await session.execute(
                select(LLMApiCall)
                .where(
                    LLMApiCall.tenant_id == tenant_id,
                    LLMApiCall.endpoint == "app.api.attribution.explanation_fastpath",
                    LLMApiCall.request_id == request_id,
                )
                .order_by(desc(LLMApiCall.created_at))
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


@pytest.mark.asyncio
async def test_b17_p2_route_uses_provider_boundary_and_fast_tier_override(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=45275,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=12543050)

    called = {"count": 0}
    original_complete = attribution_api._PROVIDER_BOUNDARY.complete

    async def _complete_spy(*args, **kwargs):
        called["count"] += 1
        return await original_complete(*args, **kwargs)

    monkeypatch.setattr(attribution_api._PROVIDER_BOUNDARY, "complete", _complete_spy, raising=True)
    monkeypatch.setattr(settings, "LLM_B17_EXPLANATION_FAST_TIER", "cheap", raising=False)

    correlation_id = uuid4()
    request_user_id = uuid4()
    status_code, body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=correlation_id,
        user_id=request_user_id,
    )
    assert status_code == 200
    assert called["count"] == 1
    assert body["authoritative_metric"]["metric_value_cents"] == 45275

    api_call = await _fetch_api_call(
        tenant_id=test_tenant,
        request_id=str(correlation_id),
        user_id=request_user_id,
    )
    assert api_call.chosen_tier == "cheap"
    assert api_call.routing_reason.startswith("tier_override:")


@pytest.mark.asyncio
async def test_b17_p2_fast_tier_is_provider_neutral_under_policy_swap(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
    tmp_path: Path,
) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=33210,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=9988776)

    policy_a = tmp_path / "b17_policy_a.json"
    policy_b = tmp_path / "b17_policy_b.json"
    policy_a.write_text(
        json.dumps(
            {
                "policy_id": "b17-provider-neutral-proof",
                "policy_version": "a",
                "bucket_tiers": [{"min_bucket": 1, "max_bucket": 10, "tier": "cheap"}],
                "tiers": {"cheap": {"provider": "openai", "model": "gpt-4o-mini"}},
                "budget_downgrade": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    policy_b.write_text(
        json.dumps(
            {
                "policy_id": "b17-provider-neutral-proof",
                "policy_version": "b",
                "bucket_tiers": [{"min_bucket": 1, "max_bucket": 10, "tier": "cheap"}],
                "tiers": {"cheap": {"provider": "anthropic", "model": "claude-3-5-sonnet"}},
                "budget_downgrade": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "LLM_B17_EXPLANATION_FAST_TIER", "cheap", raising=False)
    monkeypatch.setattr(settings, "LLM_COMPLEXITY_POLICY_PATH", str(policy_a), raising=False)

    request_user_id = uuid4()
    corr_a = uuid4()
    status_a, _ = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=corr_a,
        user_id=request_user_id,
    )
    assert status_a == 200

    monkeypatch.setattr(settings, "LLM_COMPLEXITY_POLICY_PATH", str(policy_b), raising=False)
    corr_b = uuid4()
    status_b, _ = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=corr_b,
        user_id=request_user_id,
    )
    assert status_b == 200

    api_call_a = await _fetch_api_call(
        tenant_id=test_tenant,
        request_id=str(corr_a),
        user_id=request_user_id,
    )
    api_call_b = await _fetch_api_call(
        tenant_id=test_tenant,
        request_id=str(corr_b),
        user_id=request_user_id,
    )
    assert api_call_a.chosen_tier == "cheap"
    assert api_call_b.chosen_tier == "cheap"
    assert api_call_a.chosen_provider == "openai"
    assert api_call_b.chosen_provider == "anthropic"


@pytest.mark.asyncio
async def test_b17_p2_oversize_output_degrades_without_destroying_authority(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=14567,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=2222222)

    oversized_text = "metric_value_cents 14567 revenue_total_cents 2222222 " + ("x" * 600)

    async def _provider_oversized(*, requested_model, prompt, reservation):
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": oversized_text,
            "reasoning_trace": {"trace_type": "b17-p2-oversized"},
            "response_metadata": {"source": "b17-p2-oversized"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    monkeypatch.setattr(attribution_api._PROVIDER_BOUNDARY, "_provider_call", _provider_oversized, raising=True)

    status_code, body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=uuid4(),
        user_id=uuid4(),
    )
    assert status_code == 200
    assert body["authoritative_metric"]["metric_value_cents"] == 14567
    explanation = body["non_authoritative_explanation"]
    assert explanation["explanation_class"] == "provider_fastpath_degraded"
    assert explanation["synthesis_state"] == "validation_rejected"
    assert len(explanation["non_authoritative_summary"]) <= 320


@pytest.mark.asyncio
async def test_b17_p2_numeric_mismatch_fail_closed_preserves_authority(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
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
            "reasoning_trace": {"trace_type": "b17-p2-hallucinated"},
            "response_metadata": {"source": "b17-p2-hallucinated"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    monkeypatch.setattr(attribution_api._PROVIDER_BOUNDARY, "_provider_call", _provider_hallucinated, raising=True)

    correlation_id = uuid4()
    request_user_id = uuid4()
    status_code, body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=correlation_id,
        user_id=request_user_id,
    )
    assert status_code == 200
    assert body["authoritative_metric"]["metric_value_cents"] == 31888
    explanation = body["non_authoritative_explanation"]
    assert explanation["explanation_class"] == "provider_fastpath_degraded"
    assert explanation["synthesis_state"] == "validation_rejected"
    assert explanation["degraded_reason"] == "numeric_mismatch"

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


@pytest.mark.asyncio
async def test_b17_p2_timeout_degrades_without_destroying_authority(
    monkeypatch: pytest.MonkeyPatch,
    test_tenant: UUID,
) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=7777,
    )
    await _seed_revenue_cache_entry(tenant_id=test_tenant, total_revenue_cents=910000)

    async def _provider_slow(*, requested_model, prompt, reservation):
        await asyncio.sleep(0.05)
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": "metric_value_cents 7777 revenue_total_cents 910000",
            "reasoning_trace": {"trace_type": "b17-p2-slow"},
            "response_metadata": {"source": "b17-p2-slow"},
            "usage": {"input_tokens": 4, "output_tokens": 4, "cost_cents": 1},
        }

    monkeypatch.setattr(attribution_api._PROVIDER_BOUNDARY, "_provider_call", _provider_slow, raising=True)
    monkeypatch.setattr(settings, "LLM_PROVIDER_TIMEOUT_MS", 5000, raising=False)
    monkeypatch.setattr(settings, "LLM_B17_EXPLANATION_TIMEOUT_MS", 5, raising=False)

    status_code, body = await _call_explain(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        correlation_id=uuid4(),
        user_id=uuid4(),
    )
    assert status_code == 200
    assert body["authoritative_metric"]["metric_value_cents"] == 7777
    explanation = body["non_authoritative_explanation"]
    assert explanation["explanation_class"] == "provider_fastpath_degraded"
    assert explanation["synthesis_state"] == "timeout"
    assert explanation["degraded_reason"] == "provider_timeout"

"""B1.7-P1 mounted runtime proofs for canonical explanation authority reads."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.testing.jwt_rs256 import private_ring_payload, public_ring_payload

os.environ.setdefault("AUTH_JWT_SECRET", private_ring_payload())
os.environ.setdefault("AUTH_JWT_PUBLIC_KEY_RING", public_ring_payload())
os.environ.setdefault("AUTH_JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_JWT_ISSUER", "https://issuer.skeldir.test")
os.environ.setdefault("AUTH_JWT_AUDIENCE", "skeldir-api")
os.environ.setdefault("CONTRACT_TESTING", "0")
os.environ.setdefault("TESTING", "1")

from app.db.session import AsyncSessionLocal, set_tenant_guc_async
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


async def _fetch_allocation_revenue(*, tenant_id: UUID, allocation_id: UUID) -> int:
    async with AsyncSessionLocal() as session:
        await set_tenant_guc_async(session, tenant_id, local=False)
        value = await session.scalar(
            text(
                """
                SELECT allocated_revenue_cents
                FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND id = :allocation_id
                """
            ),
            {"tenant_id": str(tenant_id), "allocation_id": str(allocation_id)},
        )
    return int(value or 0)


@pytest.fixture(autouse=True)
def _force_runtime_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTRACT_TESTING", "0")

    async def _no_revocation(_token_claims):
        return None

    monkeypatch.setattr("app.security.auth.assert_access_token_active", _no_revocation)


async def test_b17_p1_route_returns_db_equal_authority_and_separated_explanation(
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

    token = _token_for(tenant_id=test_tenant)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/attribution/explain/channel_performance/{allocation_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Correlation-ID": str(uuid4()),
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"authoritative_metric", "non_authoritative_explanation"}

    authoritative = body["authoritative_metric"]
    explanation = body["non_authoritative_explanation"]

    db_value_cents = await _fetch_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
    )
    assert authoritative["metric_value_cents"] == db_value_cents
    assert authoritative["metric_value"] == pytest.approx(db_value_cents / 100.0)
    assert authoritative["tenant_id"] == str(test_tenant)
    assert authoritative["entity_id"] == str(allocation_id)
    assert authoritative["deterministic_truth_sources"] == [
        "attribution_allocations",
        "revenue_cache_entries",
    ]
    assert explanation["explanation_class"] == "deterministic_placeholder"
    assert isinstance(explanation["non_authoritative_summary"], str)
    assert explanation["non_authoritative_summary"]


async def test_b17_p1_cross_tenant_read_is_denied(test_tenant_pair: tuple[UUID, UUID]) -> None:
    tenant_a, tenant_b = test_tenant_pair
    allocation = await build_attribution_allocation(tenant_id=tenant_a)
    allocation_id = allocation["id"]
    await _set_allocation_revenue(
        tenant_id=tenant_a,
        allocation_id=allocation_id,
        amount_cents=9000,
    )
    await _seed_revenue_cache_entry(tenant_id=tenant_a, total_revenue_cents=70000)
    await _seed_revenue_cache_entry(tenant_id=tenant_b, total_revenue_cents=80000)

    token_b = _token_for(tenant_id=tenant_b)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/attribution/explain/attribution_score/{allocation_id}",
            headers={
                "Authorization": f"Bearer {token_b}",
                "X-Correlation-ID": str(uuid4()),
            },
        )

    assert response.status_code == 404, response.text
    body = response.json()
    assert body["code"] == "NOT_FOUND"


async def test_b17_p1_missing_revenue_authority_fails_closed(test_tenant: UUID) -> None:
    allocation = await build_attribution_allocation(tenant_id=test_tenant)
    allocation_id = allocation["id"]
    await _set_allocation_revenue(
        tenant_id=test_tenant,
        allocation_id=allocation_id,
        amount_cents=1111,
    )

    token = _token_for(tenant_id=test_tenant)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/api/attribution/explain/reconciliation_discrepancy/{allocation_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Correlation-ID": str(uuid4()),
            },
        )

    assert response.status_code == 503, response.text
    body = response.json()
    assert body["code"] == "DETERMINISTIC_AUTHORITY_UNAVAILABLE"

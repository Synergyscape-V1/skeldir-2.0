"""B1.4-P3 DB-backed runtime proofs for attribution locality rebinding."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from sqlalchemy import text

from app.celery_app import celery_app
from app.core.db import engine
from app.db.session import set_tenant_guc
from app.tasks.attribution import BASELINE_CHANNELS, recompute_window
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.enqueue import enqueue_tenant_task
from tests.conftest import _insert_tenant


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _require_b14_p3_schema() -> None:
    async with engine.begin() as conn:
        has_session_authority = await conn.scalar(
            text("SELECT to_regclass('public.session_authority')")
        )
        has_recompute_jobs = await conn.scalar(
            text("SELECT to_regclass('public.attribution_recompute_jobs')")
        )
    if not has_session_authority or not has_recompute_jobs:
        pytest.skip("B1.4-P3 runtime proofs require alembic head schema with session_authority")


async def _seed_active_session(*, tenant_id: UUID, session_id: UUID, issued_by: str) -> None:
    now = datetime.now(timezone.utc)
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                INSERT INTO session_authority
                (
                    tenant_id,
                    session_id,
                    issued_at,
                    expires_at,
                    last_seen_at,
                    invalidated_at,
                    invalidation_reason,
                    issued_by,
                    created_at,
                    updated_at
                )
                VALUES
                (
                    :tenant_id,
                    :session_id,
                    :issued_at,
                    :expires_at,
                    :last_seen_at,
                    NULL,
                    NULL,
                    :issued_by,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (tenant_id, session_id)
                DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    updated_at = EXCLUDED.updated_at,
                    invalidated_at = NULL,
                    invalidation_reason = NULL
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "issued_at": now - timedelta(minutes=5),
                "expires_at": now + timedelta(hours=23),
                "last_seen_at": now,
                "issued_by": issued_by,
                "created_at": now - timedelta(minutes=5),
                "updated_at": now,
            },
        )


async def _seed_event(
    *,
    tenant_id: UUID,
    event_id: UUID,
    session_id: UUID,
    occurred_at: datetime,
    revenue_cents: int,
    external_event_id: str,
    campaign_id: str,
    idempotency_key: str,
    channel: str,
    utm_source: str,
    utm_medium: str,
) -> None:
    payload = {
        "event_type": "purchase",
        "event_timestamp": _iso(occurred_at),
        "vendor": "stripe",
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "external_event_id": external_event_id,
        "campaign_id": campaign_id,
        "channel": channel,
    }
    now = datetime.now(timezone.utc)
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                INSERT INTO attribution_events
                (
                    id,
                    tenant_id,
                    occurred_at,
                    external_event_id,
                    correlation_id,
                    session_id,
                    revenue_cents,
                    raw_payload,
                    idempotency_key,
                    event_type,
                    channel,
                    campaign_id,
                    conversion_value_cents,
                    currency,
                    event_timestamp,
                    processing_status,
                    retry_count,
                    created_at,
                    updated_at
                )
                VALUES
                (
                    :id,
                    :tenant_id,
                    :occurred_at,
                    :external_event_id,
                    :correlation_id,
                    :session_id,
                    :revenue_cents,
                    CAST(:raw_payload AS jsonb),
                    :idempotency_key,
                    'purchase',
                    :channel,
                    :campaign_id,
                    :revenue_cents,
                    'USD',
                    :event_timestamp,
                    'pending',
                    0,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "id": str(event_id),
                "tenant_id": str(tenant_id),
                "occurred_at": occurred_at,
                "external_event_id": external_event_id,
                "correlation_id": str(uuid5(NAMESPACE_URL, idempotency_key)),
                "session_id": str(session_id),
                "revenue_cents": revenue_cents,
                "raw_payload": json.dumps(payload),
                "idempotency_key": idempotency_key,
                "channel": channel,
                "campaign_id": campaign_id,
                "event_timestamp": occurred_at,
                "created_at": now,
                "updated_at": now,
            },
        )


def _enqueue_recompute(
    *,
    tenant_id: UUID,
    window_start: str,
    window_end: str,
    session_id: UUID | None,
) -> dict:
    kwargs: dict[str, str] = {
        "window_start": window_start,
        "window_end": window_end,
        "model_version": "1.0.0",
    }
    if session_id is not None:
        kwargs["session_id"] = str(session_id)
    return enqueue_tenant_task(
        recompute_window,
        envelope=SystemAuthorityEnvelope(tenant_id=tenant_id),
        kwargs=kwargs,
    ).get()


async def _allocation_count_for_event(*, tenant_id: UUID, event_id: UUID) -> int:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        count = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND event_id = :event_id
                  AND model_version = '1.0.0'
                """
            ),
            {"tenant_id": str(tenant_id), "event_id": str(event_id)},
        )
    return int(count or 0)


async def _allocated_sum_for_event(*, tenant_id: UUID, event_id: UUID) -> int:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        total = await conn.scalar(
            text(
                """
                SELECT COALESCE(SUM(allocated_revenue_cents), 0)
                FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND event_id = :event_id
                  AND model_version = '1.0.0'
                """
            ),
            {"tenant_id": str(tenant_id), "event_id": str(event_id)},
        )
    return int(total or 0)


@pytest.mark.asyncio
async def test_b14_p3_runtime_query_locality_blocks_cross_session_reconstruction_attempt():
    await _require_b14_p3_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
    window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    session_a = uuid4()
    session_b = uuid4()
    event_a = uuid4()
    event_b = uuid4()

    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_a, issued_by="b14_p3_runtime")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_b, issued_by="b14_p3_runtime")

        shared_order = f"order-shared-{uuid4().hex[:8]}"
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_a,
            session_id=session_a,
            occurred_at=now,
            revenue_cents=1500,
            external_event_id=shared_order,
            campaign_id="cmp-alpha",
            idempotency_key=f"b14_p3_a_{uuid4()}",
            channel="direct",
            utm_source="shopify",
            utm_medium="paid_social",
        )
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_b,
            session_id=session_b,
            occurred_at=now,
            revenue_cents=2500,
            external_event_id=shared_order,
            campaign_id="cmp-alpha",
            idempotency_key=f"b14_p3_b_{uuid4()}",
            channel="direct",
            utm_source="shopify",
            utm_medium="paid_social",
        )

        result_a = _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=session_a,
        )
        assert result_a["status"] == "succeeded"
        assert result_a["session_scope_count"] == 1
        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_a) == len(BASELINE_CHANNELS)
        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_b) == 0

        result_b = _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=session_b,
        )
        assert result_b["status"] == "succeeded"
        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_b) == len(BASELINE_CHANNELS)
    finally:
        celery_app.conf.task_always_eager = original_eager


@pytest.mark.asyncio
async def test_b14_p3_runtime_conversion_paths_are_session_local_without_durable_bridge_join():
    await _require_b14_p3_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
    window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    session_a = uuid4()
    session_b = uuid4()
    event_a = uuid4()
    event_b = uuid4()

    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_a, issued_by="b14_p3_runtime")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_b, issued_by="b14_p3_runtime")

        shared_order = f"order-conversion-{uuid4().hex[:8]}"
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_a,
            session_id=session_a,
            occurred_at=now,
            revenue_cents=1200,
            external_event_id=shared_order,
            campaign_id="cmp-conv",
            idempotency_key=f"b14_p3_conv_a_{uuid4()}",
            channel="direct",
            utm_source="stripe",
            utm_medium="checkout",
        )
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_b,
            session_id=session_b,
            occurred_at=now,
            revenue_cents=3400,
            external_event_id=shared_order,
            campaign_id="cmp-conv",
            idempotency_key=f"b14_p3_conv_b_{uuid4()}",
            channel="direct",
            utm_source="stripe",
            utm_medium="checkout",
        )

        result = _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=None,
        )
        assert result["status"] == "succeeded"
        assert result["session_scope_count"] >= 2

        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_a) == len(BASELINE_CHANNELS)
        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_b) == len(BASELINE_CHANNELS)
        assert await _allocated_sum_for_event(tenant_id=tenant_id, event_id=event_a) == 1200
        assert await _allocated_sum_for_event(tenant_id=tenant_id, event_id=event_b) == 3400
    finally:
        celery_app.conf.task_always_eager = original_eager


@pytest.mark.asyncio
async def test_b14_p3_runtime_session_local_replay_is_deterministic():
    await _require_b14_p3_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
    window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    session_a = uuid4()
    session_b = uuid4()
    event_a = uuid4()
    event_b = uuid4()

    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_a, issued_by="b14_p3_runtime")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_b, issued_by="b14_p3_runtime")

        shared_order = f"order-replay-{uuid4().hex[:8]}"
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_a,
            session_id=session_a,
            occurred_at=now,
            revenue_cents=2100,
            external_event_id=shared_order,
            campaign_id="cmp-replay",
            idempotency_key=f"b14_p3_replay_a_{uuid4()}",
            channel="direct",
            utm_source="paypal",
            utm_medium="checkout",
        )
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_b,
            session_id=session_b,
            occurred_at=now,
            revenue_cents=1800,
            external_event_id=shared_order,
            campaign_id="cmp-replay",
            idempotency_key=f"b14_p3_replay_b_{uuid4()}",
            channel="direct",
            utm_source="paypal",
            utm_medium="checkout",
        )

        result_first = _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=session_a,
        )
        result_second = _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=session_a,
        )

        assert result_first["status"] == "succeeded"
        assert result_second["status"] == "succeeded"
        assert result_first["event_count"] == result_second["event_count"]
        assert result_first["allocation_count"] == result_second["allocation_count"]
        assert await _allocated_sum_for_event(tenant_id=tenant_id, event_id=event_a) == 2100

        # Cross-session variant should not silently bridge credit into session_a recompute.
        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_b) == 0

        _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=session_b,
        )
        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_b) == len(BASELINE_CHANNELS)
    finally:
        celery_app.conf.task_always_eager = original_eager

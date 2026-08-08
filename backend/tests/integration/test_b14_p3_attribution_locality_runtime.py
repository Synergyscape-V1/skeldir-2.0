"""B1.4-P3 DB-backed runtime proofs for attribution locality rebinding."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api import webhooks as webhooks_api
from app.celery_app import celery_app
from app.core.db import engine
from app.ingestion.event_service import ingest_with_transaction
from app.main import app
from app.db.session import set_tenant_guc
from app.security.auth import AuthContext, get_auth_context
from app.tasks.attribution import BASELINE_CHANNELS, recompute_window
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.enqueue import enqueue_tenant_task
from app.tasks.maintenance import _delete_expired_ephemeral_resolution_rows
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
        has_ephemeral_order_resolution = await conn.scalar(
            text("SELECT to_regclass('public.ephemeral_order_resolution')")
        )
        has_ephemeral_click_resolution = await conn.scalar(
            text("SELECT to_regclass('public.ephemeral_click_resolution')")
        )
    if (
        not has_session_authority
        or not has_recompute_jobs
        or not has_ephemeral_order_resolution
        or not has_ephemeral_click_resolution
    ):
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


async def _expire_session_authority(*, tenant_id: UUID, session_id: UUID) -> None:
    now = datetime.now(timezone.utc)
    issued_at = now - timedelta(hours=26)
    expires_at = now - timedelta(hours=2)
    last_seen_at = now - timedelta(hours=2, minutes=30)
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                UPDATE session_authority
                SET issued_at = :issued_at,
                    expires_at = :expires_at,
                    last_seen_at = :last_seen_at,
                    invalidated_at = :invalidated_at,
                    invalidation_reason = 'runtime_test_expired',
                    updated_at = :updated_at
                WHERE tenant_id = :tenant_id
                  AND session_id = :session_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "issued_at": issued_at,
                "expires_at": expires_at,
                "last_seen_at": last_seen_at,
                "invalidated_at": now - timedelta(hours=1),
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
    raw_payload_overrides: dict[str, str] | None = None,
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
    if raw_payload_overrides:
        payload.update(raw_payload_overrides)
    now = datetime.now(timezone.utc)
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            # RAW_SQL_ALLOWLIST: Controlled integration seed for session-local attribution runtime proofs.
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


def _auth_context_for_tenant(tenant_id: UUID) -> AuthContext:
    return AuthContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        jti=uuid4(),
        issued_at_epoch=int(datetime.now(timezone.utc).timestamp()),
        subject="b14-p3-runtime",
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"scopes": ["viewer"], "tenant_id": str(tenant_id)},
    )


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


@pytest.mark.asyncio
async def test_b14_p3_runtime_export_partition_preserves_aggregate_and_session_scoped_reporting():
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

    async def _auth_override() -> AuthContext:
        return _auth_context_for_tenant(tenant_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_a, issued_by="b14_p3_runtime")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_b, issued_by="b14_p3_runtime")
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_a,
            session_id=session_a,
            occurred_at=now,
            revenue_cents=1500,
            external_event_id=f"export-a-{uuid4().hex[:8]}",
            campaign_id="cmp-export",
            idempotency_key=f"b14_p3_export_a_{uuid4()}",
            channel="direct",
            utm_source="shopify",
            utm_medium="paid_social",
        )
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_b,
            session_id=session_b,
            occurred_at=now,
            revenue_cents=2700,
            external_event_id=f"export-b-{uuid4().hex[:8]}",
            campaign_id="cmp-export",
            idempotency_key=f"b14_p3_export_b_{uuid4()}",
            channel="direct",
            utm_source="shopify",
            utm_medium="paid_social",
        )
        _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=None,
        )
        await _expire_session_authority(tenant_id=tenant_id, session_id=session_a)
        await _expire_session_authority(tenant_id=tenant_id, session_id=session_b)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            aggregate = await client.get(
                "/api/export/json",
                headers={"X-Correlation-ID": str(uuid4())},
            )
            scoped = await client.get(
                "/api/export/json",
                headers={
                    "X-Correlation-ID": str(uuid4()),
                    "X-Attribution-Session-ID": str(session_a),
                },
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)
        celery_app.conf.task_always_eager = original_eager

    assert aggregate.status_code == 200, aggregate.text
    assert scoped.status_code == 200, scoped.text

    aggregate_payload = aggregate.json()
    scoped_payload = scoped.json()
    assert aggregate_payload["projection_authority"] == "non_authoritative_display"
    assert scoped_payload["projection_authority"] == "non_authoritative_display"
    aggregate_rows = aggregate_payload["rows"]
    scoped_rows = scoped_payload["rows"]

    assert aggregate_rows
    assert scoped_rows == []

    aggregate_revenue = sum(int(row["revenue_minor"]) for row in aggregate_rows)
    scoped_revenue = sum(int(row["revenue_minor"]) for row in scoped_rows)
    assert aggregate_revenue == 4200
    assert scoped_revenue == 0
    assert aggregate_revenue > scoped_revenue

    aggregate_conversions = sum(int(row["conversions"]) for row in aggregate_rows)
    scoped_conversions = sum(int(row["conversions"]) for row in scoped_rows)
    assert aggregate_conversions == len(BASELINE_CHANNELS) * 2
    assert scoped_conversions == 0


@pytest.mark.asyncio
async def test_b14_p3_runtime_bounded_telemetry_allowlist_is_sufficient_for_baseline():
    await _require_b14_p3_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
    window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    session_a = uuid4()
    event_a = uuid4()

    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_a, issued_by="b14_p3_runtime")
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_a,
            session_id=session_a,
            occurred_at=now,
            revenue_cents=1900,
            external_event_id=f"telemetry-ok-{uuid4().hex[:8]}",
            campaign_id="cmp-telemetry",
            idempotency_key=f"b14_p3_telemetry_ok_{uuid4()}",
            channel="direct",
            utm_source="stripe",
            utm_medium="checkout",
        )

        result = _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=session_a,
        )
        assert result["status"] == "succeeded"
        assert await _allocation_count_for_event(tenant_id=tenant_id, event_id=event_a) == len(BASELINE_CHANNELS)
        assert await _allocated_sum_for_event(tenant_id=tenant_id, event_id=event_a) == 1900
    finally:
        celery_app.conf.task_always_eager = original_eager


@pytest.mark.asyncio
async def test_b14_p3_runtime_forbidden_proxy_identifier_payload_fails_closed():
    await _require_b14_p3_schema()
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    window_start = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0))
    window_end = _iso(now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    session_a = uuid4()
    idempotency_key = f"b14_p3_telemetry_bad_{uuid4()}"
    external_event_id = f"telemetry-bad-{uuid4().hex[:8]}"

    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(tenant_id=tenant_id, session_id=session_a, issued_by="b14_p3_runtime")
        ingress_result = await ingest_with_transaction(
            tenant_id=tenant_id,
            event_data={
                "event_type": "purchase",
                "event_timestamp": _iso(now),
                "revenue_amount": "11.00",
                "currency": "USD",
                "session_id": str(session_a),
                "vendor": "stripe",
                "utm_source": "stripe",
                "utm_medium": "checkout",
                "external_event_id": external_event_id,
                "campaign_id": "cmp-telemetry",
                "channel": "direct",
                "gclid": "forbidden-click-proxy",
            },
            idempotency_key=idempotency_key,
            source="stripe",
            identity_payload={
                "event_type": "purchase",
                "event_timestamp": _iso(now),
                "gclid": "forbidden-click-proxy",
                "session_id": str(session_a),
            },
            request_headers={},
        )
        assert ingress_result.status == "success"

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_id, local=True)
            payload = await conn.scalar(
                text(
                    """
                    SELECT raw_payload
                    FROM attribution_events
                    WHERE tenant_id = :tenant_id
                      AND idempotency_key = :idempotency_key
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "idempotency_key": idempotency_key,
                },
            )
        assert isinstance(payload, dict)
        assert "gclid" not in payload

        result = _enqueue_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            session_id=session_a,
        )
        assert result["status"] == "succeeded"
        assert result["event_count"] == 1
        assert result["allocation_count"] == len(BASELINE_CHANNELS)
    finally:
        celery_app.conf.task_always_eager = original_eager


@pytest.mark.asyncio
async def test_b14_p3_runtime_stripe_v2_recompute_coverage_and_session_hint_continuity(
    monkeypatch: pytest.MonkeyPatch,
):
    await _require_b14_p3_schema()
    tenant_id = uuid4()
    session_hint = uuid4()
    created_epoch = int(datetime.now(timezone.utc).timestamp())
    idempotency_key = f"b14_p3_stripe_v2_{uuid4().hex[:12]}"
    scheduled_calls: list[dict[str, object]] = []

    async def _stripe_auth_override() -> dict[str, UUID]:
        return {"tenant_id": tenant_id}

    def _schedule_spy(**kwargs) -> None:
        scheduled_calls.append(kwargs)

    app.dependency_overrides[webhooks_api.stripe_webhook_auth] = _stripe_auth_override
    monkeypatch.setattr(webhooks_api, "_schedule_downstream_tasks", _schedule_spy)
    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(
            tenant_id=tenant_id,
            session_id=session_hint,
            issued_by="b14_p3_runtime",
        )

        payload = {
            "id": f"evt_{uuid4().hex[:10]}",
            "created": created_epoch,
            "data": {
                "object": {
                    "id": f"pi_{uuid4().hex[:10]}",
                    "amount": 1234,
                    "currency": "usd",
                    "metadata": {
                        "session_id": str(session_hint),
                        "utm_source": "stripe",
                        "utm_medium": "checkout",
                    },
                }
            },
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/webhooks/stripe/payment_intent/succeeded",
                headers={
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": idempotency_key,
                },
                content=json.dumps(payload).encode("utf-8"),
            )
        assert response.status_code == 200, response.text
        assert response.json().get("status") == "success"

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_id, local=True)
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT session_id::text
                        FROM attribution_events
                        WHERE tenant_id = :tenant_id
                          AND idempotency_key = :idempotency_key
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "idempotency_key": idempotency_key,
                    },
                )
            ).first()
        assert row is not None
        assert row[0] == str(session_hint)
        assert len(scheduled_calls) == 1
        assert scheduled_calls[0]["tenant_id"] == tenant_id
        assert scheduled_calls[0]["session_id"] == str(session_hint)
    finally:
        app.dependency_overrides.pop(webhooks_api.stripe_webhook_auth, None)


@pytest.mark.asyncio
async def test_b14_p3_runtime_universal_webhook_order_resolution_adopts_active_browser_session():
    await _require_b14_p3_schema()
    tenant_id = uuid4()
    browser_session = uuid4()
    order_id = f"order-universal-{uuid4().hex[:10]}"
    ingress_idempotency = f"b14_p3_browser_order_seed_{uuid4().hex[:10]}"
    webhook_idempotency = str(uuid5(NAMESPACE_URL, f"paypal_sale_completed_{order_id}"))

    async def _paypal_auth_override() -> dict[str, UUID]:
        return {"tenant_id": tenant_id}

    app.dependency_overrides[webhooks_api.paypal_webhook_auth] = _paypal_auth_override
    try:
        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
        await _seed_active_session(
            tenant_id=tenant_id,
            session_id=browser_session,
            issued_by="b14_p3_runtime",
        )

        seed_result = await ingest_with_transaction(
            tenant_id=tenant_id,
            event_data={
                "event_type": "click",
                "event_timestamp": _iso(datetime.now(timezone.utc) - timedelta(hours=12)),
                "revenue_amount": "0.00",
                "currency": "USD",
                "session_id": str(browser_session),
                "vendor": "browser",
                "utm_source": "google",
                "utm_medium": "cpc",
                "order_id": order_id,
                "external_event_id": f"browser-seed-{uuid4().hex[:8]}",
                "campaign_id": "cmp-universal-order",
            },
            idempotency_key=ingress_idempotency,
            source="browser",
            identity_payload={"order_id": order_id, "session_id": str(browser_session)},
            request_headers={},
        )
        assert seed_result.status == "success"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/webhooks/paypal/sale_completed",
                headers={"Content-Type": "application/json"},
                json={
                    "id": order_id,
                    "amount": {"total": "29.99", "currency": "USD"},
                    "create_time": _iso(datetime.now(timezone.utc)),
                },
            )
        assert response.status_code == 200, response.text
        assert response.json().get("status") == "success"

        async with engine.begin() as conn:
            await set_tenant_guc(conn, tenant_id, local=True)
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT session_id::text
                        FROM attribution_events
                        WHERE tenant_id = :tenant_id
                          AND idempotency_key = :idempotency_key
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "idempotency_key": webhook_idempotency,
                    },
                )
            ).first()
        assert row is not None
        assert row[0] == str(browser_session)
    finally:
        app.dependency_overrides.pop(webhooks_api.paypal_webhook_auth, None)


@pytest.mark.asyncio
async def test_b14_p3_runtime_ephemeral_click_resolution_routes_and_expires_after_25h():
    await _require_b14_p3_schema()
    tenant_id = uuid4()
    browser_session = uuid4()
    click_id = f"click-{uuid4().hex[:10]}"
    seed_key = f"b14_p3_click_seed_{uuid4().hex[:10]}"
    conversion_key = f"b14_p3_click_conversion_{uuid4().hex[:10]}"
    fallback_session = uuid4()

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
    await _seed_active_session(
        tenant_id=tenant_id,
        session_id=browser_session,
        issued_by="b14_p3_runtime",
    )

    seed_result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "click",
            "event_timestamp": _iso(datetime.now(timezone.utc) - timedelta(hours=1)),
            "revenue_amount": "0.00",
            "currency": "USD",
            "session_id": str(browser_session),
            "vendor": "google",
            "utm_source": "google",
            "utm_medium": "cpc",
            "click_id": click_id,
            "campaign_id": "cmp-click",
            "external_event_id": f"click-seed-{uuid4().hex[:8]}",
        },
        idempotency_key=seed_key,
        source="browser",
        identity_payload={"click_id": click_id, "session_id": str(browser_session)},
        request_headers={},
    )
    assert seed_result.status == "success"

    conversion_result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data={
            "event_type": "purchase",
            "event_timestamp": _iso(datetime.now(timezone.utc)),
            "revenue_amount": "55.00",
            "currency": "USD",
            "session_id": str(fallback_session),
            "vendor": "shopify",
            "utm_source": "shopify",
            "utm_medium": "paid_social",
            "click_id": click_id,
            "campaign_id": "cmp-click",
            "external_event_id": f"click-conv-{uuid4().hex[:8]}",
        },
        idempotency_key=conversion_key,
        source="shopify",
        identity_payload={"click_id": click_id},
        request_headers={},
    )
    assert conversion_result.status == "success"
    assert conversion_result.session_id == str(browser_session)

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                UPDATE ephemeral_click_resolution
                SET observed_at = :observed_at,
                    expires_at = :expired_at,
                    updated_at = :updated_at
                WHERE tenant_id = :tenant_id
                  AND click_id = :click_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "click_id": click_id,
                "observed_at": datetime.now(timezone.utc) - timedelta(hours=26),
                "expired_at": datetime.now(timezone.utc) - timedelta(hours=25),
                "updated_at": datetime.now(timezone.utc),
            },
        )

    gc_result = await _delete_expired_ephemeral_resolution_rows(batch_size=50)
    assert gc_result["deleted_click_rows"] >= 1

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        remaining = await conn.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM ephemeral_click_resolution
                WHERE tenant_id = :tenant_id
                  AND click_id = :click_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "click_id": click_id,
            },
        )
    assert int(remaining or 0) == 0

"""B2.1-P1 runtime proofs for canonical input semantics and replay identity lock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.db import engine
from app.db.session import set_tenant_guc
from app.tasks.attribution import recompute_window
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER, SystemAuthorityEnvelope, authority_envelope_payload
from tests.conftest import _insert_tenant


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _ensure_runtime_tables() -> None:
    async with engine.begin() as conn:
        required_tables = (
            "attribution_events",
            "attribution_allocations",
            "attribution_recompute_jobs",
            "session_authority",
            "channel_taxonomy",
        )
        for table_name in required_tables:
            present = await conn.scalar(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{table_name}"},
            )
            if present is None:
                pytest.skip(
                    f"B2.1-P1 runtime proofs require alembic head schema with {table_name}"
                )


async def _ensure_channel_codes(codes: list[str]) -> None:
    async with engine.begin() as conn:
        for code in codes:
            await conn.execute(
                text(
                    """
                    INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active, state)
                    VALUES (:code, 'b21_p1', false, :display_name, true, 'active')
                    ON CONFLICT (code) DO NOTHING
                    """
                ),
                {"code": code, "display_name": code.replace("_", " ").title()},
            )


async def _seed_session_authority(
    *,
    tenant_id: UUID,
    session_id: UUID,
    issued_at: datetime,
    expires_at: datetime,
) -> None:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                INSERT INTO session_authority (
                    id,
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
                ) VALUES (
                    :id,
                    :tenant_id,
                    :session_id,
                    :issued_at,
                    :expires_at,
                    :last_seen_at,
                    NULL,
                    NULL,
                    'b21_p1_runtime',
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (tenant_id, session_id)
                DO UPDATE SET
                    issued_at = EXCLUDED.issued_at,
                    expires_at = EXCLUDED.expires_at,
                    last_seen_at = EXCLUDED.last_seen_at,
                    invalidated_at = NULL,
                    invalidation_reason = NULL,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "session_id": str(session_id),
                "issued_at": issued_at,
                "expires_at": expires_at,
                "last_seen_at": min(expires_at, issued_at + timedelta(hours=1)),
                "created_at": issued_at,
                "updated_at": issued_at,
            },
        )


async def _rewrite_session_authority_window(
    *,
    tenant_id: UUID,
    session_id: UUID,
    issued_at: datetime,
    expires_at: datetime,
) -> None:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                UPDATE session_authority
                SET issued_at = :issued_at,
                    expires_at = :expires_at,
                    last_seen_at = :last_seen_at,
                    invalidated_at = NULL,
                    invalidation_reason = NULL,
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
                "last_seen_at": min(expires_at, issued_at + timedelta(hours=1)),
                "updated_at": datetime.now(timezone.utc),
            },
        )


async def _seed_event(
    *,
    tenant_id: UUID,
    event_id: UUID,
    session_id: UUID,
    occurred_at: datetime,
    event_type: str,
    idempotency_key: str,
    channel: str,
    revenue_cents: int,
) -> None:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text(
                """
                INSERT INTO attribution_events (
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
                    processed_at,
                    processing_status,
                    retry_count,
                    created_at,
                    updated_at
                ) VALUES (
                    :id,
                    :tenant_id,
                    :occurred_at,
                    :external_event_id,
                    :correlation_id,
                    :session_id,
                    :revenue_cents,
                    CAST(:raw_payload AS jsonb),
                    :idempotency_key,
                    :event_type,
                    :channel,
                    :campaign_id,
                    :conversion_value_cents,
                    'USD',
                    :event_timestamp,
                    :processed_at,
                    'processed',
                    0,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                """
            ),
            {
                "id": str(event_id),
                "tenant_id": str(tenant_id),
                "occurred_at": occurred_at,
                "external_event_id": f"evt-{event_id.hex[:12]}",
                "correlation_id": str(uuid4()),
                "session_id": str(session_id),
                "revenue_cents": int(revenue_cents),
                "raw_payload": (
                    '{"global_idempotency_hash":"'
                    + f"{event_id.hex:0<64}"[:64]
                    + '"}'
                ),
                "idempotency_key": idempotency_key,
                "event_type": event_type,
                "channel": channel,
                "campaign_id": "cmp-b21-p1",
                "conversion_value_cents": int(revenue_cents),
                "event_timestamp": occurred_at,
                "processed_at": occurred_at + timedelta(minutes=1),
                "created_at": occurred_at,
                "updated_at": occurred_at,
            },
        )


def _apply_recompute(
    *,
    tenant_id: UUID,
    window_start: str,
    window_end: str,
    model_version: str = "1.0.0",
    session_id: UUID | None = None,
    lookback_days: int | None = None,
) -> dict:
    kwargs: dict[str, str | int] = {
        "window_start": window_start,
        "window_end": window_end,
        "model_version": model_version,
    }
    if session_id is not None:
        kwargs["session_id"] = str(session_id)
    if lookback_days is not None:
        kwargs["lookback_days"] = int(lookback_days)
    result = recompute_window.apply(
        kwargs=kwargs,
        headers={
            AUTHORITY_ENVELOPE_HEADER: authority_envelope_payload(
                SystemAuthorityEnvelope(tenant_id=tenant_id)
            )
        },
    )
    return result.get(propagate=True)


@pytest.mark.asyncio
async def test_b21_p1_runtime_conversion_taxonomy_excludes_touchpoint_rows():
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    session_id = uuid4()
    event_at = datetime.now(timezone.utc).replace(microsecond=0)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=event_at - timedelta(hours=1),
        expires_at=event_at + timedelta(hours=1),
    )
    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_id,
        occurred_at=event_at - timedelta(minutes=20),
        event_type="click",
        idempotency_key=f"b21p1-touchpoint-{uuid4()}",
        channel="direct",
        revenue_cents=0,
    )
    conversion_event_id = uuid4()
    await _seed_event(
        tenant_id=tenant_id,
        event_id=conversion_event_id,
        session_id=session_id,
        occurred_at=event_at - timedelta(minutes=10),
        event_type="purchase",
        idempotency_key=f"b21p1-conversion-{uuid4()}",
        channel="direct",
        revenue_cents=4200,
    )

    payload = _apply_recompute(
        tenant_id=tenant_id,
        window_start=_iso(event_at - timedelta(hours=2)),
        window_end=_iso(event_at + timedelta(hours=1)),
        session_id=session_id,
    )
    assert payload["status"] == "succeeded"
    assert int(payload["event_count"]) == 1
    assert int(payload["allocation_count"]) == 3

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        allocated_conversion = await conn.scalar(
            text(
                """
                SELECT COUNT(*) FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND event_id = :event_id
                  AND model_version = '1.0.0'
                """
            ),
            {"tenant_id": str(tenant_id), "event_id": str(conversion_event_id)},
        )
    assert int(allocated_conversion or 0) == 3


@pytest.mark.asyncio
async def test_b21_p1_runtime_historical_replay_uses_persisted_session_facts_not_wall_clock():
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    session_id = uuid4()
    historical_start = datetime(2025, 1, 3, 0, 0, tzinfo=timezone.utc)
    historical_end = datetime(2025, 1, 4, 0, 0, tzinfo=timezone.utc)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_id,
        occurred_at=historical_start + timedelta(hours=4),
        event_type="conversion",
        idempotency_key=f"b21p1-historical-{uuid4()}",
        channel="direct",
        revenue_cents=1900,
    )
    await _rewrite_session_authority_window(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=historical_start + timedelta(hours=1),
        expires_at=historical_start + timedelta(hours=23),
    )

    payload = _apply_recompute(
        tenant_id=tenant_id,
        window_start=_iso(historical_start),
        window_end=_iso(historical_end),
        session_id=session_id,
    )
    assert payload["status"] == "succeeded"
    assert int(payload["event_count"]) == 1
    assert int(payload["allocation_count"]) == 3
    assert int(payload["session_scope_count"]) == 1


@pytest.mark.asyncio
async def test_b21_p1_runtime_default_30_day_lookback_and_replay_identity_partitioning():
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    session_old = uuid4()
    session_new = uuid4()
    window_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    window_end = datetime(2025, 3, 20, tzinfo=timezone.utc)
    old_event_ts = datetime(2025, 1, 20, 10, 0, tzinfo=timezone.utc)
    new_event_ts = datetime(2025, 3, 15, 8, 0, tzinfo=timezone.utc)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_old,
        occurred_at=old_event_ts,
        event_type="purchase",
        idempotency_key=f"b21p1-old-{uuid4()}",
        channel="direct",
        revenue_cents=1100,
    )
    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_new,
        occurred_at=new_event_ts,
        event_type="purchase",
        idempotency_key=f"b21p1-new-{uuid4()}",
        channel="direct",
        revenue_cents=2200,
    )
    await _rewrite_session_authority_window(
        tenant_id=tenant_id,
        session_id=session_old,
        issued_at=old_event_ts - timedelta(hours=1),
        expires_at=old_event_ts + timedelta(hours=1),
    )
    await _rewrite_session_authority_window(
        tenant_id=tenant_id,
        session_id=session_new,
        issued_at=new_event_ts - timedelta(hours=1),
        expires_at=new_event_ts + timedelta(hours=1),
    )

    default_payload = _apply_recompute(
        tenant_id=tenant_id,
        window_start=_iso(window_start),
        window_end=_iso(window_end),
    )
    assert default_payload["status"] == "succeeded"
    assert int(default_payload["lookback_days"]) == 30
    assert int(default_payload["event_count"]) == 1

    widened_payload = _apply_recompute(
        tenant_id=tenant_id,
        window_start=_iso(window_start),
        window_end=_iso(window_end),
        lookback_days=90,
    )
    assert widened_payload["status"] == "succeeded"
    assert int(widened_payload["lookback_days"]) == 90
    assert int(widened_payload["event_count"]) == 2
    assert widened_payload["job_model_version"] != default_payload["job_model_version"]

    scoped_payload = _apply_recompute(
        tenant_id=tenant_id,
        window_start=_iso(window_start),
        window_end=_iso(window_end),
        lookback_days=90,
        session_id=session_new,
    )
    assert scoped_payload["status"] == "succeeded"
    assert int(scoped_payload["event_count"]) == 1
    assert scoped_payload["job_model_version"] != widened_payload["job_model_version"]

    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        rows = await conn.execute(
            text(
                """
                SELECT model_version, run_count
                FROM attribution_recompute_jobs
                WHERE tenant_id = :tenant_id
                  AND window_start = :window_start
                  AND window_end = :window_end
                  AND model_version LIKE :model_prefix
                ORDER BY model_version
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "window_start": window_start,
                "window_end": window_end,
                "model_prefix": "1.0.0::taxonomy=b2.1-p1-v1%",
            },
        )
        job_rows = rows.fetchall()
    assert len(job_rows) == 3

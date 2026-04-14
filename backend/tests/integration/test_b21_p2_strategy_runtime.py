"""B2.1-P2 runtime proofs for deterministic strategy kernel behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.attribution.strategy_kernel import (
    FIRST_TOUCH_MODEL,
    LAST_TOUCH_MODEL,
    LINEAR_MODEL,
    TIME_DECAY_MODEL,
    EligibleTouchpoint,
    derive_channel_ratios,
)
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
                pytest.skip(f"B2.1-P2 runtime proofs require table: {table_name}")


async def _ensure_channel_codes(codes: list[str]) -> None:
    async with engine.begin() as conn:
        for code in codes:
            await conn.execute(
                text(
                    """
                    INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active, state)
                    VALUES (:code, 'b21_p2', false, :display_name, true, 'active')
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
                    'b21_p2_runtime',
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
    created_at: datetime | None = None,
) -> None:
    event_created_at = created_at or occurred_at
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        # RAW_SQL_ALLOWLIST: deterministic integration fixture seeding for strategy runtime proofs.
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
                "campaign_id": "cmp-b21-p2",
                "conversion_value_cents": int(revenue_cents),
                "event_timestamp": occurred_at,
                "processed_at": occurred_at + timedelta(minutes=1),
                "created_at": event_created_at,
                "updated_at": event_created_at,
            },
        )


async def _try_seed_event_with_session_boundary(
    *,
    tenant_id: UUID,
    event_id: UUID,
    session_id: UUID,
    occurred_at: datetime,
    event_type: str,
    idempotency_key: str,
    channel: str,
    revenue_cents: int,
    created_at: datetime | None = None,
) -> bool:
    try:
        await _seed_event(
            tenant_id=tenant_id,
            event_id=event_id,
            session_id=session_id,
            occurred_at=occurred_at,
            event_type=event_type,
            idempotency_key=idempotency_key,
            channel=channel,
            revenue_cents=revenue_cents,
            created_at=created_at,
        )
        return True
    except DBAPIError as exc:
        message = str(exc).lower()
        if "session authority violation" not in message:
            raise
        return False


def _apply_recompute(
    *,
    tenant_id: UUID,
    window_start: str,
    window_end: str,
    model_version: str,
    model_type: str,
    session_id: UUID | None = None,
) -> dict:
    kwargs: dict[str, str] = {
        "window_start": window_start,
        "window_end": window_end,
        "model_version": model_version,
        "model_type": model_type,
    }
    if session_id is not None:
        kwargs["session_id"] = str(session_id)
    result = recompute_window.apply(
        kwargs=kwargs,
        headers={
            AUTHORITY_ENVELOPE_HEADER: authority_envelope_payload(
                SystemAuthorityEnvelope(tenant_id=tenant_id)
            )
        },
    )
    return result.get(propagate=True)


async def _fetch_allocations_for_conversion(
    *,
    tenant_id: UUID,
    conversion_event_id: UUID,
    model_version: str,
) -> list[tuple[str, Decimal, int, str]]:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        rows = await conn.execute(
            text(
                """
                SELECT channel_code, allocation_ratio, allocated_revenue_cents, model_type
                FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND event_id = :event_id
                  AND model_version = :model_version
                ORDER BY channel_code ASC
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "event_id": str(conversion_event_id),
                "model_version": model_version,
            },
        )
        return [
            (str(row[0]), Decimal(str(row[1])), int(row[2]), str(row[3]))
            for row in rows.fetchall()
        ]


async def test_b21_p2_runtime_four_strategies_are_separately_executable() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    session_id = uuid4()
    anchor_now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = anchor_now - timedelta(hours=18)
    expires_at = issued_at + timedelta(hours=24)
    conversion_at = issued_at + timedelta(hours=17)
    seed_created_at = anchor_now - timedelta(minutes=1)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    touchpoints = [
        (uuid4(), issued_at + timedelta(hours=1), "email"),
        (uuid4(), issued_at + timedelta(hours=6), "google_search_paid"),
        (uuid4(), issued_at + timedelta(hours=12), "direct"),
    ]
    for touchpoint_id, touchpoint_time, channel in touchpoints:
        await _seed_event(
            tenant_id=tenant_id,
            event_id=touchpoint_id,
            session_id=session_id,
            occurred_at=touchpoint_time,
            event_type="click",
            idempotency_key=f"b21p2-touchpoint-{touchpoint_id}",
            channel=channel,
            revenue_cents=0,
            created_at=seed_created_at,
        )

    conversion_event_id = uuid4()
    await _seed_event(
        tenant_id=tenant_id,
        event_id=conversion_event_id,
        session_id=session_id,
        occurred_at=conversion_at,
        event_type="purchase",
        idempotency_key=f"b21p2-conversion-{conversion_event_id}",
        channel="direct",
        revenue_cents=2100,
        created_at=seed_created_at,
    )

    window_start = _iso(issued_at)
    window_end = _iso(expires_at)

    expectations: dict[str, dict[str, Decimal]] = {
        FIRST_TOUCH_MODEL: {"email": Decimal("1.00000")},
        LAST_TOUCH_MODEL: {"direct": Decimal("1.00000")},
        LINEAR_MODEL: {
            "direct": Decimal("0.33334"),
            "email": Decimal("0.33333"),
            "google_search_paid": Decimal("0.33333"),
        },
        TIME_DECAY_MODEL: {
            row.channel_code: row.allocation_ratio
            for row in derive_channel_ratios(
                model_type=TIME_DECAY_MODEL,
                touchpoints=[
                    EligibleTouchpoint(id=touchpoints[0][0], occurred_at=touchpoints[0][1], channel_code="email"),
                    EligibleTouchpoint(id=touchpoints[1][0], occurred_at=touchpoints[1][1], channel_code="google_search_paid"),
                    EligibleTouchpoint(id=touchpoints[2][0], occurred_at=touchpoints[2][1], channel_code="direct"),
                ],
                conversion_occurred_at=conversion_at,
            )
        },
    }

    for model_type, expected_ratios in expectations.items():
        payload = _apply_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=f"b21p2-{model_type}",
            model_type=model_type,
            session_id=session_id,
        )
        assert payload["status"] == "succeeded"
        assert payload["model_type"] == model_type
        allocations = await _fetch_allocations_for_conversion(
            tenant_id=tenant_id,
            conversion_event_id=conversion_event_id,
            model_version=f"b21p2-{model_type}",
        )
        ratio_map = {channel: ratio for channel, ratio, _cents, _model_type in allocations}
        assert ratio_map == expected_ratios
        for _channel, _ratio, _cents, persisted_model_type in allocations:
            assert persisted_model_type == model_type
        assert abs(sum(ratio_map.values(), start=Decimal("0")) - Decimal("1")) <= Decimal("0.001")


async def test_b21_p2_runtime_session_half_open_boundary_proofs() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    session_id = uuid4()
    anchor_now = datetime.now(timezone.utc).replace(microsecond=0)
    # Keep authority valid with time slack to avoid nondeterministic stale-session
    # insert failures while proving exact [issued_at, expires_at) math.
    issued_at = anchor_now - timedelta(hours=23, minutes=49, seconds=59)
    expires_at = issued_at + timedelta(hours=24)
    seed_created_at = anchor_now - timedelta(minutes=1)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_id,
        occurred_at=issued_at,  # included
        event_type="click",
        idempotency_key=f"b21p2-edge-touchpoint-inc-{uuid4()}",
        channel="email",
        revenue_cents=0,
        created_at=seed_created_at,
    )
    conversion_included = uuid4()
    await _seed_event(
        tenant_id=tenant_id,
        event_id=conversion_included,
        session_id=session_id,
        occurred_at=expires_at - timedelta(seconds=1),  # 23:59:59 included
        event_type="purchase",
        idempotency_key=f"b21p2-edge-conv-235959-{uuid4()}",
        channel="direct",
        revenue_cents=1400,
        created_at=seed_created_at,
    )
    conversion_excluded_at_boundary = uuid4()
    inserted_boundary_conversion = await _try_seed_event_with_session_boundary(
        tenant_id=tenant_id,
        event_id=conversion_excluded_at_boundary,
        session_id=session_id,
        occurred_at=expires_at,  # 24:00:00 excluded
        event_type="purchase",
        idempotency_key=f"b21p2-edge-conv-240000-{uuid4()}",
        channel="direct",
        revenue_cents=1500,
        created_at=seed_created_at,
    )
    conversion_excluded_after_boundary = uuid4()
    inserted_after_boundary_conversion = await _try_seed_event_with_session_boundary(
        tenant_id=tenant_id,
        event_id=conversion_excluded_after_boundary,
        session_id=session_id,
        occurred_at=expires_at + timedelta(seconds=1),  # 24:00:01 excluded
        event_type="purchase",
        idempotency_key=f"b21p2-edge-conv-240001-{uuid4()}",
        channel="direct",
        revenue_cents=1600,
        created_at=seed_created_at,
    )

    payload = _apply_recompute(
        tenant_id=tenant_id,
        window_start=_iso(issued_at - timedelta(minutes=1)),
        window_end=_iso(expires_at + timedelta(minutes=1)),
        model_version="b21p2-edge-half-open",
        model_type=FIRST_TOUCH_MODEL,
        session_id=session_id,
    )
    assert payload["status"] == "succeeded"
    assert int(payload["event_count"]) == 1

    allocations = await _fetch_allocations_for_conversion(
        tenant_id=tenant_id,
        conversion_event_id=conversion_included,
        model_version="b21p2-edge-half-open",
    )
    assert allocations == [("email", Decimal("1.00000"), 1400, FIRST_TOUCH_MODEL)]

    if inserted_boundary_conversion:
        boundary_allocations = await _fetch_allocations_for_conversion(
            tenant_id=tenant_id,
            conversion_event_id=conversion_excluded_at_boundary,
            model_version="b21p2-edge-half-open",
        )
        assert boundary_allocations == []

    if inserted_after_boundary_conversion:
        after_boundary_allocations = await _fetch_allocations_for_conversion(
            tenant_id=tenant_id,
            conversion_event_id=conversion_excluded_after_boundary,
            model_version="b21p2-edge-half-open",
        )
        assert after_boundary_allocations == []


async def test_b21_p2_runtime_null_touchpoint_conversions_get_direct_full_mass() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    session_id = uuid4()
    anchor_now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = anchor_now - timedelta(hours=2)
    expires_at = issued_at + timedelta(hours=24)
    conversion_at = issued_at + timedelta(hours=1)
    seed_created_at = anchor_now - timedelta(minutes=1)
    conversion_event_id = uuid4()

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")

    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    await _seed_event(
        tenant_id=tenant_id,
        event_id=conversion_event_id,
        session_id=session_id,
        occurred_at=conversion_at,
        event_type="purchase",
        idempotency_key=f"b21p2-null-conversion-{uuid4()}",
        channel="direct",
        revenue_cents=2345,
        created_at=seed_created_at,
    )

    payload = _apply_recompute(
        tenant_id=tenant_id,
        window_start=_iso(issued_at),
        window_end=_iso(expires_at),
        model_version="b21p2-null-touchpoint",
        model_type=LAST_TOUCH_MODEL,
        session_id=session_id,
    )
    assert payload["status"] == "succeeded"
    assert int(payload["event_count"]) == 1
    assert int(payload["null_touchpoint_conversions"]) == 1

    allocations = await _fetch_allocations_for_conversion(
        tenant_id=tenant_id,
        conversion_event_id=conversion_event_id,
        model_version="b21p2-null-touchpoint",
    )
    assert allocations == [("direct", Decimal("1.00000"), 2345, LAST_TOUCH_MODEL)]

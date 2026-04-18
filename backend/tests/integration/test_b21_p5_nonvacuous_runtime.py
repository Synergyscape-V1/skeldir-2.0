"""B2.1-P5 runtime proofs for non-vacuous replay and precision adjudication."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.db import engine
from app.db.session import set_tenant_guc
from app.main import app
from app.security.auth import AuthContext, get_auth_context
from app.tasks.attribution import recompute_window
from app.tasks.authority import AUTHORITY_ENVELOPE_HEADER, SystemAuthorityEnvelope, authority_envelope_payload
from tests.conftest import _insert_tenant


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


RATIO_PATTERN = re.compile(r"^(0|1)\.\d{5}$")
CONFIDENCE_PATTERN = re.compile(r"^(0|1)\.\d{3}$")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _auth_context(*, tenant_id: UUID, user_id: UUID) -> AuthContext:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    return AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        jti=uuid4(),
        issued_at_epoch=now_epoch,
        subject=str(user_id),
        issuer="https://issuer.skeldir.test",
        audience="skeldir-api",
        claims={"role": "viewer", "roles": ["viewer"], "scopes": ["viewer"]},
    )


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
                pytest.skip(f"B2.1-P5 runtime proofs require table: {table_name}")


async def _ensure_channel_codes(codes: list[str]) -> None:
    async with engine.begin() as conn:
        for code in codes:
            await conn.execute(
                text(
                    """
                    INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active, state)
                    VALUES (:code, 'b21_p5', false, :display_name, true, 'active')
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
                    'b21_p5_runtime',
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
        # RAW_SQL_ALLOWLIST: deterministic integration fixture seeding for B2.1-P5 runtime proofs.
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
                "campaign_id": "cmp-b21-p5",
                "conversion_value_cents": int(revenue_cents),
                "event_timestamp": occurred_at,
                "processed_at": occurred_at + timedelta(minutes=1),
                "created_at": event_created_at,
                "updated_at": event_created_at,
            },
        )


def _apply_recompute(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    model_type: str,
    model_version: str,
    session_id: UUID,
) -> dict:
    result = recompute_window.apply(
        kwargs={
            "window_start": _iso(window_start),
            "window_end": _iso(window_end),
            "model_type": model_type,
            "model_version": model_version,
            "session_id": str(session_id),
        },
        headers={
            AUTHORITY_ENVELOPE_HEADER: authority_envelope_payload(
                SystemAuthorityEnvelope(tenant_id=tenant_id)
            )
        },
    )
    return result.get(propagate=True)


async def _fetch_conversion_allocations(
    *,
    tenant_id: UUID,
    conversion_event_id: UUID,
    model_version: str,
) -> list[tuple[str, str, int]]:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        rows = await conn.execute(
            text(
                """
                SELECT channel_code, allocation_ratio::text, allocated_revenue_cents
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
        return [(str(row[0]), str(row[1]), int(row[2])) for row in rows.fetchall()]


@pytest.mark.asyncio
async def test_b21_p5_equal_timestamp_ties_replay_determinism_is_stable_across_time_separated_reruns() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    session_id = uuid4()
    anchor_now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = anchor_now - timedelta(hours=2)
    expires_at = issued_at + timedelta(hours=24)
    tie_time = issued_at + timedelta(minutes=20)
    conversion_time = tie_time + timedelta(minutes=5)
    fixed_created_at = anchor_now - timedelta(seconds=1)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    touchpoint_email_id = uuid5(NAMESPACE_URL, f"{tenant_id}:tie:email")
    touchpoint_direct_id = uuid5(NAMESPACE_URL, f"{tenant_id}:tie:direct")
    event_channel = {
        touchpoint_email_id: "email",
        touchpoint_direct_id: "direct",
    }
    expected_first_touch_channel = event_channel[min(event_channel)]

    await _seed_event(
        tenant_id=tenant_id,
        event_id=touchpoint_email_id,
        session_id=session_id,
        occurred_at=tie_time,
        event_type="click",
        idempotency_key=f"b21p5-tie-email-{uuid4()}",
        channel="email",
        revenue_cents=0,
        created_at=fixed_created_at,
    )
    await _seed_event(
        tenant_id=tenant_id,
        event_id=touchpoint_direct_id,
        session_id=session_id,
        occurred_at=tie_time,
        event_type="click",
        idempotency_key=f"b21p5-tie-direct-{uuid4()}",
        channel="direct",
        revenue_cents=0,
        created_at=fixed_created_at,
    )
    conversion_event_id = uuid4()
    await _seed_event(
        tenant_id=tenant_id,
        event_id=conversion_event_id,
        session_id=session_id,
        occurred_at=conversion_time,
        event_type="purchase",
        idempotency_key=f"b21p5-tie-conversion-{uuid4()}",
        channel="direct",
        revenue_cents=900,
        created_at=fixed_created_at,
    )

    first_run = _apply_recompute(
        tenant_id=tenant_id,
        window_start=issued_at,
        window_end=expires_at,
        model_type="first_touch",
        model_version="b21p5-tie-first-touch",
        session_id=session_id,
    )
    assert first_run["status"] == "succeeded"
    assert int(first_run["run_count"]) == 1

    first_allocations = await _fetch_conversion_allocations(
        tenant_id=tenant_id,
        conversion_event_id=conversion_event_id,
        model_version="b21p5-tie-first-touch",
    )
    assert first_allocations == [(expected_first_touch_channel, "1.00000", 900)]

    await asyncio.sleep(2.1)
    second_run = _apply_recompute(
        tenant_id=tenant_id,
        window_start=issued_at,
        window_end=expires_at,
        model_type="first_touch",
        model_version="b21p5-tie-first-touch",
        session_id=session_id,
    )
    assert second_run["status"] == "succeeded"
    assert int(second_run["run_count"]) == 2
    assert second_run["output_identity_digest"] == first_run["output_identity_digest"]
    assert second_run["replay_identity_digest"] == first_run["replay_identity_digest"]
    assert second_run["replay_event_created_ceiling"] == first_run["replay_event_created_ceiling"]

    second_allocations = await _fetch_conversion_allocations(
        tenant_id=tenant_id,
        conversion_event_id=conversion_event_id,
        model_version="b21p5-tie-first-touch",
    )
    assert second_allocations == first_allocations


@pytest.mark.asyncio
async def test_b21_p5_precision_and_fractional_conservation_hold_db_to_api_roundtrip() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid"])

    tenant_id = uuid4()
    user_id = uuid4()
    session_id = uuid4()
    anchor_now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = anchor_now - timedelta(hours=1)
    expires_at = issued_at + timedelta(hours=24)
    conversion_at = issued_at + timedelta(minutes=40)
    seed_created_at = anchor_now - timedelta(seconds=1)

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
        occurred_at=issued_at + timedelta(minutes=5),
        event_type="click",
        idempotency_key=f"b21p5-precision-touch-email-{uuid4()}",
        channel="email",
        revenue_cents=0,
        created_at=seed_created_at,
    )
    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_id,
        occurred_at=issued_at + timedelta(minutes=15),
        event_type="click",
        idempotency_key=f"b21p5-precision-touch-google-{uuid4()}",
        channel="google_search_paid",
        revenue_cents=0,
        created_at=seed_created_at,
    )
    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_id,
        occurred_at=issued_at + timedelta(minutes=25),
        event_type="click",
        idempotency_key=f"b21p5-precision-touch-direct-{uuid4()}",
        channel="direct",
        revenue_cents=0,
        created_at=seed_created_at,
    )

    await _seed_event(
        tenant_id=tenant_id,
        event_id=uuid4(),
        session_id=session_id,
        occurred_at=conversion_at,
        event_type="purchase",
        idempotency_key=f"b21p5-precision-conversion-{uuid4()}",
        channel="direct",
        revenue_cents=100,
        created_at=seed_created_at,
    )

    recompute_result = _apply_recompute(
        tenant_id=tenant_id,
        window_start=issued_at,
        window_end=expires_at,
        model_type="linear",
        model_version="b21p5-linear-precision",
        session_id=session_id,
    )
    assert recompute_result["status"] == "succeeded"

    async def _auth_override() -> AuthContext:
        return _auth_context(tenant_id=tenant_id, user_id=user_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/attribution/channels",
                params={
                    "model_type": "linear",
                    "recompute_job_id": str(recompute_result["job_id"]),
                },
                headers={"X-Correlation-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    assert response.status_code == status.HTTP_200_OK, response.text
    payload = response.json()
    assert payload["projection"]["recompute_job_id"] == str(recompute_result["job_id"])
    assert payload["projection"]["model_type"] == "linear"

    channels = payload["channels"]
    assert len(channels) == 3

    ratio_mass = Decimal("0")
    revenue_cents_mass = 0
    for channel in channels:
        allocation_ratio = str(channel["allocation_ratio"])
        attribution_weight = str(channel["attribution_weight"])
        confidence_score = str(channel["confidence_score"])
        assert RATIO_PATTERN.fullmatch(allocation_ratio)
        assert RATIO_PATTERN.fullmatch(attribution_weight)
        assert CONFIDENCE_PATTERN.fullmatch(confidence_score)
        assert allocation_ratio == attribution_weight
        ratio_mass += Decimal(attribution_weight)
        revenue_cents_mass += int(channel["revenue_cents"])

    assert ratio_mass == Decimal("1.00000")
    assert int(payload["total_revenue_cents"]) == revenue_cents_mass

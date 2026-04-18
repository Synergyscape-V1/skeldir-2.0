"""B2.1-P6 runtime proofs for full deterministic chain closure and downstream readiness."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.db import engine
from app.db.session import get_session, set_tenant_guc
from app.ingestion.event_service import EventIngestionService
from app.main import app
from app.security.auth import AuthContext, get_auth_context
from app.tasks.attribution import recompute_window
from app.tasks.authority import (
    AUTHORITY_ENVELOPE_HEADER,
    SystemAuthorityEnvelope,
    authority_envelope_payload,
)
from tests.conftest import _insert_tenant


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


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
            "tenants",
            "channel_taxonomy",
            "session_authority",
            "attribution_events",
            "attribution_allocations",
            "attribution_recompute_jobs",
            "raw_event_payloads",
        )
        for table_name in required_tables:
            present = await conn.scalar(
                text("SELECT to_regclass(:table_name)"),
                {"table_name": f"public.{table_name}"},
            )
            if present is None:
                pytest.skip(f"B2.1-P6 runtime proofs require table: {table_name}")


async def _ensure_channel_codes(codes: list[str]) -> None:
    async with engine.begin() as conn:
        for code in codes:
            await conn.execute(
                text(
                    """
                    INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active, state)
                    VALUES (:code, 'b21_p6', false, :display_name, true, 'active')
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
                    'b21_p6_runtime',
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


async def _ingest_event(
    *,
    tenant_id: UUID,
    user_id: UUID,
    session_id: UUID,
    event_timestamp: datetime,
    event_type: str,
    revenue_amount: str,
    idempotency_key: str,
    vendor: str,
    utm_source: str,
    correlation_id: UUID | None = None,
) -> UUID:
    service = EventIngestionService()
    event_payload = {
        "event_type": event_type,
        "event_timestamp": _iso(event_timestamp),
        "revenue_amount": revenue_amount,
        "session_id": str(session_id),
        "vendor": vendor,
        "utm_source": utm_source,
        "utm_medium": "campaign",
        "email": "customer.b21.p6@example.test",
        "ip_address": "203.0.113.7",
        "user_agent": "B21P6-Integration/1.0",
        "correlation_id": str(correlation_id or uuid4()),
        "external_event_id": f"evt-{idempotency_key}",
    }

    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        event = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_payload,
            idempotency_key=idempotency_key,
            source=vendor.lower(),
            identity_payload=event_payload,
            request_headers={
                "User-Agent": "B21P6-Integration/1.0",
                "X-Forwarded-For": "203.0.113.7",
                "X-Correlation-ID": str(correlation_id or uuid4()),
            },
        )
    return UUID(str(event.id))


def _apply_recompute(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    model_type: str,
    model_version: str,
    session_id: UUID | None = None,
) -> dict:
    kwargs: dict[str, str] = {
        "window_start": _iso(window_start),
        "window_end": _iso(window_end),
        "model_type": model_type,
        "model_version": model_version,
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


async def _fetch_allocations_for_job(
    *,
    tenant_id: UUID,
    recompute_job_id: UUID,
    conversion_event_id: UUID,
) -> list[tuple[str, str, int]]:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        rows = await conn.execute(
            text(
                """
                SELECT channel_code, allocation_ratio::text, allocated_revenue_cents
                FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND recompute_job_id = :recompute_job_id
                  AND event_id = :event_id
                ORDER BY channel_code ASC
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "recompute_job_id": str(recompute_job_id),
                "event_id": str(conversion_event_id),
            },
        )
        return [(str(row[0]), str(row[1]), int(row[2])) for row in rows.fetchall()]


async def _fetch_raw_payload_text(*, tenant_id: UUID, event_id: UUID) -> str:
    async with engine.begin() as conn:
        await set_tenant_guc(conn, tenant_id, local=True)
        raw_payload_text = await conn.scalar(
            text(
                """
                SELECT payload_json::text
                FROM raw_event_payloads
                WHERE tenant_id = :tenant_id
                  AND event_id = :event_id
                LIMIT 1
                """
            ),
            {"tenant_id": str(tenant_id), "event_id": str(event_id)},
        )
    return str(raw_payload_text or "")


async def _channels_request(
    *,
    tenant_id: UUID,
    user_id: UUID,
    model_type: str,
    recompute_job_id: UUID,
) -> tuple[int, dict]:
    async def _auth_override() -> AuthContext:
        return _auth_context(tenant_id=tenant_id, user_id=user_id)

    app.dependency_overrides[get_auth_context] = _auth_override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/attribution/channels",
                params={
                    "model_type": model_type,
                    "recompute_job_id": str(recompute_job_id),
                },
                headers={"X-Correlation-ID": str(uuid4())},
            )
    finally:
        app.dependency_overrides.pop(get_auth_context, None)

    payload = response.json() if response.content else {}
    return response.status_code, payload


async def test_b21_p6_full_chain_ingestion_to_persistence_to_channels_is_authoritative() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid", "unknown"])

    tenant_id = uuid4()
    user_id = uuid4()
    session_id = uuid4()
    anchor = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = anchor - timedelta(hours=2)
    expires_at = issued_at + timedelta(hours=24)
    window_start = issued_at - timedelta(minutes=1)
    window_end = issued_at + timedelta(hours=2)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_id, api_key_hash=f"test_hash_{tenant_id}")
    await _seed_session_authority(
        tenant_id=tenant_id,
        session_id=session_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    first_touch_event_id = await _ingest_event(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        event_timestamp=issued_at + timedelta(minutes=5),
        event_type="click",
        revenue_amount="0.00",
        idempotency_key=f"b21p6-touch-email-{uuid4()}",
        vendor="stripe",
        utm_source="EMAIL",
    )
    await _ingest_event(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        event_timestamp=issued_at + timedelta(minutes=15),
        event_type="click",
        revenue_amount="0.00",
        idempotency_key=f"b21p6-touch-google-{uuid4()}",
        vendor="google_ads",
        utm_source="SEARCH",
    )
    await _ingest_event(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        event_timestamp=issued_at + timedelta(minutes=25),
        event_type="click",
        revenue_amount="0.00",
        idempotency_key=f"b21p6-touch-direct-{uuid4()}",
        vendor="shopify",
        utm_source="DIRECT",
    )
    conversion_event_id = await _ingest_event(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        event_timestamp=issued_at + timedelta(minutes=40),
        event_type="purchase",
        revenue_amount="123.45",
        idempotency_key=f"b21p6-conversion-{uuid4()}",
        vendor="shopify",
        utm_source="DIRECT",
    )

    raw_payload_text = await _fetch_raw_payload_text(
        tenant_id=tenant_id,
        event_id=first_touch_event_id,
    )
    assert "customer.b21.p6@example.test" not in raw_payload_text
    assert "203.0.113.7" not in raw_payload_text
    assert "\"email\"" not in raw_payload_text
    assert "\"ip_address\"" not in raw_payload_text
    assert "\"user_agent\"" not in raw_payload_text

    model_runs: dict[str, dict] = {}
    for model_type in ("first_touch", "last_touch", "linear", "time_decay"):
        payload = _apply_recompute(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_type=model_type,
            model_version=f"b21p6-{model_type}",
            session_id=session_id,
        )
        assert payload["status"] == "succeeded"
        assert payload["model_type"] == model_type
        model_runs[model_type] = payload

        allocations = await _fetch_allocations_for_job(
            tenant_id=tenant_id,
            recompute_job_id=UUID(str(payload["job_id"])),
            conversion_event_id=conversion_event_id,
        )
        assert allocations
        ratio_mass = sum((Decimal(row[1]) for row in allocations), Decimal("0"))
        assert abs(ratio_mass - Decimal("1.00000")) <= Decimal("0.001")

    await asyncio.sleep(1.2)
    replay_rerun = _apply_recompute(
        tenant_id=tenant_id,
        window_start=window_start,
        window_end=window_end,
        model_type="first_touch",
        model_version="b21p6-first_touch",
        session_id=session_id,
    )
    first_touch_seed = model_runs["first_touch"]
    assert replay_rerun["status"] == "succeeded"
    assert int(replay_rerun["run_count"]) == int(first_touch_seed["run_count"]) + 1
    assert replay_rerun["output_identity_digest"] == first_touch_seed["output_identity_digest"]
    assert replay_rerun["replay_identity_digest"] == first_touch_seed["replay_identity_digest"]
    assert replay_rerun["replay_event_created_ceiling"] == first_touch_seed["replay_event_created_ceiling"]

    for model_type, result_payload in model_runs.items():
        status_code, payload = await _channels_request(
            tenant_id=tenant_id,
            user_id=user_id,
            model_type=model_type,
            recompute_job_id=UUID(str(result_payload["job_id"])),
        )
        assert status_code == status.HTTP_200_OK
        assert payload["projection"]["model_type"] == model_type
        assert payload["projection"]["recompute_job_id"] == str(result_payload["job_id"])
        assert payload["tenant_id"] == str(tenant_id)
        assert isinstance(payload["data_freshness_seconds"], int)
        assert payload["total_revenue_cents"] == 12345
        ratio_mass = sum(
            (Decimal(str(channel["allocation_ratio"])) for channel in payload["channels"]),
            Decimal("0"),
        )
        assert abs(ratio_mass - Decimal("1.00000")) <= Decimal("0.001")


async def test_b21_p6_chain_blocks_cross_tenant_reads_and_preserves_over_24h_session_separation() -> None:
    await _ensure_runtime_tables()
    await _ensure_channel_codes(["direct", "email", "google_search_paid", "unknown"])

    tenant_a = uuid4()
    tenant_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    session_a_old = uuid4()
    session_a_new = uuid4()
    session_b = uuid4()
    anchor = datetime.now(timezone.utc).replace(microsecond=0)

    session_a_old_issued = anchor - timedelta(hours=30)
    session_a_old_expires = session_a_old_issued + timedelta(hours=24)
    session_a_new_issued = anchor - timedelta(hours=2)
    session_a_new_expires = session_a_new_issued + timedelta(hours=24)
    session_b_issued = anchor - timedelta(hours=1)
    session_b_expires = session_b_issued + timedelta(hours=24)

    async with engine.begin() as conn:
        await _insert_tenant(conn, tenant_a, api_key_hash=f"test_hash_{tenant_a}")
        await _insert_tenant(conn, tenant_b, api_key_hash=f"test_hash_{tenant_b}")
    await _seed_session_authority(
        tenant_id=tenant_a,
        session_id=session_a_old,
        issued_at=session_a_old_issued,
        expires_at=session_a_old_expires,
    )
    await _seed_session_authority(
        tenant_id=tenant_a,
        session_id=session_a_new,
        issued_at=session_a_new_issued,
        expires_at=session_a_new_expires,
    )
    await _seed_session_authority(
        tenant_id=tenant_b,
        session_id=session_b,
        issued_at=session_b_issued,
        expires_at=session_b_expires,
    )

    await _ingest_event(
        tenant_id=tenant_a,
        user_id=user_a,
        session_id=session_a_old,
        event_timestamp=session_a_old_issued + timedelta(minutes=10),
        event_type="click",
        revenue_amount="0.00",
        idempotency_key=f"b21p6-old-session-touch-{uuid4()}",
        vendor="google_ads",
        utm_source="SEARCH",
    )
    await _ingest_event(
        tenant_id=tenant_a,
        user_id=user_a,
        session_id=session_a_new,
        event_timestamp=session_a_new_issued + timedelta(minutes=5),
        event_type="click",
        revenue_amount="0.00",
        idempotency_key=f"b21p6-new-session-touch-{uuid4()}",
        vendor="stripe",
        utm_source="EMAIL",
    )
    conversion_a = await _ingest_event(
        tenant_id=tenant_a,
        user_id=user_a,
        session_id=session_a_new,
        event_timestamp=session_a_new_issued + timedelta(minutes=15),
        event_type="purchase",
        revenue_amount="9.00",
        idempotency_key=f"b21p6-new-session-conversion-{uuid4()}",
        vendor="shopify",
        utm_source="DIRECT",
    )

    await _ingest_event(
        tenant_id=tenant_b,
        user_id=user_b,
        session_id=session_b,
        event_timestamp=session_b_issued + timedelta(minutes=4),
        event_type="click",
        revenue_amount="0.00",
        idempotency_key=f"b21p6-tenant-b-touch-{uuid4()}",
        vendor="shopify",
        utm_source="DIRECT",
    )
    await _ingest_event(
        tenant_id=tenant_b,
        user_id=user_b,
        session_id=session_b,
        event_timestamp=session_b_issued + timedelta(minutes=10),
        event_type="purchase",
        revenue_amount="7.00",
        idempotency_key=f"b21p6-tenant-b-conversion-{uuid4()}",
        vendor="shopify",
        utm_source="DIRECT",
    )

    run_a = _apply_recompute(
        tenant_id=tenant_a,
        window_start=session_a_old_issued - timedelta(minutes=1),
        window_end=session_a_new_expires,
        model_type="first_touch",
        model_version="b21p6-tenant-a-first-touch",
    )
    run_b = _apply_recompute(
        tenant_id=tenant_b,
        window_start=session_b_issued - timedelta(minutes=1),
        window_end=session_b_expires,
        model_type="first_touch",
        model_version="b21p6-tenant-b-first-touch",
    )
    assert run_a["status"] == "succeeded"
    assert run_b["status"] == "succeeded"

    allocations_a = await _fetch_allocations_for_job(
        tenant_id=tenant_a,
        recompute_job_id=UUID(str(run_a["job_id"])),
        conversion_event_id=conversion_a,
    )
    assert allocations_a
    assert allocations_a == [("email", "1.00000", 900)]

    status_a, payload_a = await _channels_request(
        tenant_id=tenant_a,
        user_id=user_a,
        model_type="first_touch",
        recompute_job_id=UUID(str(run_a["job_id"])),
    )
    assert status_a == status.HTTP_200_OK
    assert payload_a["tenant_id"] == str(tenant_a)
    assert payload_a["total_revenue_cents"] == 900
    assert "google_search_paid" not in {entry["channel_code"] for entry in payload_a["channels"]}

    status_b, payload_b = await _channels_request(
        tenant_id=tenant_b,
        user_id=user_b,
        model_type="first_touch",
        recompute_job_id=UUID(str(run_b["job_id"])),
    )
    assert status_b == status.HTTP_200_OK
    assert payload_b["tenant_id"] == str(tenant_b)
    assert payload_b["total_revenue_cents"] == 700

    cross_status, cross_payload = await _channels_request(
        tenant_id=tenant_b,
        user_id=user_b,
        model_type="first_touch",
        recompute_job_id=UUID(str(run_a["job_id"])),
    )
    assert cross_status == status.HTTP_404_NOT_FOUND
    assert cross_payload.get("code") == "ATTRIBUTION_PROJECTION_NOT_FOUND"

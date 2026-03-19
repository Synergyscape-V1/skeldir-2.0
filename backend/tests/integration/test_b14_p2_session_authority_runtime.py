"""B1.4-P2 DB-backed runtime proofs for session authority substrate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import select, text

from app.db.session import get_session
from app.ingestion.event_service import EventIngestionService
from app.models import AttributionEvent, SessionAuthority


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _event_payload(*, session_id: str, order_ref: str) -> dict[str, object]:
    return {
        "event_type": "purchase",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "19.99",
        "currency": "USD",
        "session_id": session_id,
        "vendor": "stripe",
        "utm_source": "stripe",
        "external_event_id": order_ref,
    }


@pytest.mark.asyncio
async def test_b14_p2_runtime_stale_session_invalidates_and_rotates(test_tenant):
    tenant_id = test_tenant
    stale_session_id = uuid4()
    now = datetime.now(timezone.utc)
    issued_at = now - timedelta(hours=24, minutes=1)
    expires_at = issued_at + timedelta(hours=24)

    async with get_session(tenant_id=tenant_id) as session:
        session.add(
            SessionAuthority(
                tenant_id=tenant_id,
                session_id=stale_session_id,
                issued_at=issued_at,
                expires_at=expires_at,
                last_seen_at=issued_at + timedelta(hours=1),
                invalidated_at=None,
                invalidation_reason=None,
                issued_by="test_runtime_fixture",
                created_at=issued_at,
                updated_at=issued_at + timedelta(hours=1),
            )
        )
        await session.commit()

    idempotency_key = f"b14_p2_stale_{uuid4()}"
    order_ref = f"order-stale-{uuid4().hex[:8]}"
    event_data = _event_payload(session_id=str(stale_session_id), order_ref=order_ref)

    async with get_session(tenant_id=tenant_id) as session:
        service = EventIngestionService()
        persisted_event = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source="test_suite",
            identity_payload=event_data,
            request_headers={"user-agent": "b14-p2-runtime-agent"},
        )
        await session.commit()
        event_id = persisted_event.id

    async with get_session(tenant_id=tenant_id) as session:
        event = await session.get(AttributionEvent, event_id)
        assert event is not None
        assert event.session_id != stale_session_id

        stale_row = await session.scalar(
            select(SessionAuthority).where(
                SessionAuthority.tenant_id == tenant_id,
                SessionAuthority.session_id == stale_session_id,
            )
        )
        assert stale_row is not None
        assert stale_row.invalidated_at is not None
        assert stale_row.invalidation_reason == "expired"

        rotated_row = await session.scalar(
            select(SessionAuthority).where(
                SessionAuthority.tenant_id == tenant_id,
                SessionAuthority.session_id == event.session_id,
            )
        )
        assert rotated_row is not None
        assert rotated_row.invalidated_at is None
        assert rotated_row.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_b14_p2_runtime_non_linkability_blocks_durable_bridge_candidate(
    test_tenant,
):
    tenant_id = test_tenant
    service = EventIngestionService()
    durable_bridge_candidate = uuid5(NAMESPACE_URL, f"order-bridge:{tenant_id}")
    order_ref = f"order-bridge-{uuid4().hex[:8]}"

    event_a_idempotency = f"b14_p2_bridge_a_{uuid4()}"
    event_b_idempotency = f"b14_p2_bridge_b_{uuid4()}"

    event_a_data = _event_payload(
        session_id=str(durable_bridge_candidate),
        order_ref=order_ref,
    )
    event_b_data = _event_payload(
        session_id=str(durable_bridge_candidate),
        order_ref=order_ref,
    )

    async with get_session(tenant_id=tenant_id) as session:
        event_a = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_a_data,
            idempotency_key=event_a_idempotency,
            source="test_suite",
            identity_payload=event_a_data,
            request_headers={"user-agent": "b14-p2-bridge-agent"},
        )
        await session.commit()

    async with get_session(tenant_id=tenant_id) as session:
        event_b = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_b_data,
            idempotency_key=event_b_idempotency,
            source="test_suite",
            identity_payload=event_b_data,
            request_headers={"user-agent": "b14-p2-bridge-agent"},
        )
        await session.commit()

    assert event_a.session_id != durable_bridge_candidate
    assert event_b.session_id != durable_bridge_candidate
    assert event_a.session_id != event_b.session_id

    async with get_session(tenant_id=tenant_id) as session:
        bridge_authority_rows = await session.scalar(
            text(
                """
                SELECT COUNT(*) FROM public.session_authority
                WHERE tenant_id = :tenant_id AND session_id = :session_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "session_id": str(durable_bridge_candidate),
            },
        )
        assert int(bridge_authority_rows or 0) == 0

        distinct_sessions = await session.scalar(
            text(
                """
                SELECT COUNT(DISTINCT session_id) FROM public.attribution_events
                WHERE tenant_id = :tenant_id
                  AND external_event_id = :external_event_id
                  AND (id = :event_a OR id = :event_b)
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "external_event_id": order_ref,
                "event_a": str(event_a.id),
                "event_b": str(event_b.id),
            },
        )
        assert int(distinct_sessions or 0) == 2

        # Non-vacuous control: active authority session IDs can be reused
        # when the same valid authority session is explicitly presented.
        active_reuse_key = f"b14_p2_bridge_active_reuse_{uuid4()}"
        reuse_payload = _event_payload(session_id=str(event_a.session_id), order_ref=order_ref)
        service_reuse = EventIngestionService()
        reused_event = await service_reuse.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=reuse_payload,
            idempotency_key=active_reuse_key,
            source="test_suite",
            identity_payload=reuse_payload,
            request_headers={"user-agent": "b14-p2-bridge-agent"},
        )
        await session.commit()
        assert reused_event.session_id == event_a.session_id

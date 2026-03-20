"""B1.4-P2 DB-backed runtime proofs for session authority substrate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

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


@pytest.mark.asyncio
async def test_b14_p2_runtime_persisted_expired_rows_cannot_bridge_rotated_session(
    test_tenant,
):
    tenant_id = test_tenant
    service = EventIngestionService()
    legacy_session_id = uuid4()
    order_ref = f"order-severance-{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    async with get_session(tenant_id=tenant_id) as session:
        session.add(
            SessionAuthority(
                tenant_id=tenant_id,
                session_id=legacy_session_id,
                issued_at=now - timedelta(hours=2),
                expires_at=now + timedelta(hours=1),
                last_seen_at=now - timedelta(minutes=5),
                invalidated_at=None,
                invalidation_reason=None,
                issued_by="test_runtime_fixture",
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(minutes=5),
            )
        )
        await session.commit()

    event_a_payload = _event_payload(session_id=str(legacy_session_id), order_ref=order_ref)
    event_a_idempotency = f"b14_p2_severance_a_{uuid4()}"
    async with get_session(tenant_id=tenant_id) as session:
        event_a = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_a_payload,
            idempotency_key=event_a_idempotency,
            source="test_suite",
            identity_payload=event_a_payload,
            request_headers={"user-agent": "b14-p2-severance-agent"},
        )
        await session.commit()

    assert event_a.session_id == legacy_session_id

    async with get_session(tenant_id=tenant_id) as session:
        legacy_row = await session.scalar(
            select(SessionAuthority).where(
                SessionAuthority.tenant_id == tenant_id,
                SessionAuthority.session_id == legacy_session_id,
            )
        )
        assert legacy_row is not None
        legacy_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        legacy_row.updated_at = datetime.now(timezone.utc)
        await session.commit()

    event_b_payload = _event_payload(session_id=str(legacy_session_id), order_ref=order_ref)
    event_b_idempotency = f"b14_p2_severance_b_{uuid4()}"
    async with get_session(tenant_id=tenant_id) as session:
        event_b = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_b_payload,
            idempotency_key=event_b_idempotency,
            source="test_suite",
            identity_payload=event_b_payload,
            request_headers={"user-agent": "b14-p2-severance-agent"},
        )
        await session.commit()

    assert event_b.session_id != legacy_session_id
    assert event_b.session_id != event_a.session_id

    async with get_session(tenant_id=tenant_id) as session:
        stale_row = await session.scalar(
            select(SessionAuthority).where(
                SessionAuthority.tenant_id == tenant_id,
                SessionAuthority.session_id == legacy_session_id,
            )
        )
        assert stale_row is not None
        assert stale_row.invalidated_at is not None
        assert stale_row.invalidation_reason == "expired"

        session_bridge_rows = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM public.attribution_events e_old
                JOIN public.attribution_events e_new
                  ON e_new.tenant_id = e_old.tenant_id
                 AND e_new.session_id = e_old.session_id
                WHERE e_old.tenant_id = :tenant_id
                  AND e_old.id = :event_a
                  AND e_new.id = :event_b
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "event_a": str(event_a.id),
                "event_b": str(event_b.id),
            },
        )
        assert int(session_bridge_rows or 0) == 0

        authority_bridge_rows = await session.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM public.session_authority sa
                JOIN public.attribution_events e_old
                  ON e_old.tenant_id = sa.tenant_id
                 AND e_old.session_id = sa.session_id
                JOIN public.attribution_events e_new
                  ON e_new.tenant_id = sa.tenant_id
                 AND e_new.session_id = sa.session_id
                WHERE sa.tenant_id = :tenant_id
                  AND e_old.id = :event_a
                  AND e_new.id = :event_b
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "event_a": str(event_a.id),
                "event_b": str(event_b.id),
            },
        )
        assert int(authority_bridge_rows or 0) == 0


@pytest.mark.asyncio
async def test_b14_p2_runtime_db_rejects_stale_session_insert_despite_historical_rows(
    test_tenant,
):
    tenant_id = test_tenant
    service = EventIngestionService()
    stale_session_id = uuid4()
    order_ref = f"order-db-guard-{uuid4().hex[:8]}"

    async with get_session(tenant_id=tenant_id) as session:
        now = datetime.now(timezone.utc)
        session.add(
            SessionAuthority(
                tenant_id=tenant_id,
                session_id=stale_session_id,
                issued_at=now - timedelta(hours=26),
                expires_at=now - timedelta(hours=2),
                last_seen_at=now - timedelta(hours=25),
                invalidated_at=now - timedelta(hours=1),
                invalidation_reason="expired",
                issued_by="test_runtime_fixture",
                created_at=now - timedelta(hours=26),
                updated_at=now - timedelta(hours=1),
            )
        )
        await session.commit()

    warm_payload = _event_payload(session_id=str(uuid4()), order_ref=order_ref)
    warm_idempotency = f"b14_p2_db_guard_warm_{uuid4()}"
    async with get_session(tenant_id=tenant_id) as session:
        warm_event = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=warm_payload,
            idempotency_key=warm_idempotency,
            source="test_suite",
            identity_payload=warm_payload,
            request_headers={"user-agent": "b14-p2-db-guard-agent"},
        )
        await session.commit()

    insert_attempt_sql = text(
        """
        INSERT INTO public.attribution_events
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
            CAST(:tenant_id AS uuid),
            CAST(:occurred_at AS timestamptz),
            :external_event_id,
            CAST(:correlation_id AS uuid),
            CAST(:session_id AS uuid),
            :revenue_cents,
            CAST(:raw_payload AS jsonb),
            :idempotency_key,
            :event_type,
            :channel,
            :currency,
            CAST(:event_timestamp AS timestamptz),
            :processing_status,
            :retry_count,
            CAST(:created_at AS timestamptz),
            CAST(:updated_at AS timestamptz)
        )
        """
    )

    async with get_session(tenant_id=tenant_id) as session:
        now = datetime.now(timezone.utc)
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                insert_attempt_sql,
                {
                    "id": str(uuid4()),
                    "tenant_id": str(tenant_id),
                    "occurred_at": now,
                    "external_event_id": f"manual-stale-{uuid4().hex[:8]}",
                    "correlation_id": str(uuid4()),
                    "session_id": str(stale_session_id),
                    "revenue_cents": 1099,
                    "raw_payload": "{}",
                    "idempotency_key": f"b14_p2_manual_stale_{uuid4()}",
                    "event_type": "purchase",
                    "channel": warm_event.channel,
                    "currency": "USD",
                    "event_timestamp": now,
                    "processing_status": "pending",
                    "retry_count": 0,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await session.flush()
        await session.rollback()

    assert "session authority violation" in str(exc_info.value).lower()

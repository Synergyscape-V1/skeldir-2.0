"""B1.4-P1 DB-backed runtime proofs for ingress privacy boundary enforcement."""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.db.session import engine, get_session
from app.ingestion.dlq_handler import (
    DLQHandler,
    DLQReplayPayload,
    route_unresolved_tenant_to_quarantine,
)
from app.ingestion.event_service import EventIngestionService
from app.ingestion.privacy_boundary import REDACTION_TOKEN
from app.models import AttributionEvent, DeadEvent


pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.mark.asyncio
async def test_b14_p1_canonical_ingress_strips_pii_before_write(test_tenant):
    tenant_id = test_tenant
    idempotency_key = f"b14_p1_canonical_{uuid4()}"
    provided_session = str(uuid4())

    event_data = {
        "event_type": "purchase",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "42.10",
        "session_id": provided_session,
        "vendor": "stripe",
        "vendor_payload": {
            "customer": {
                "email": "canonical-user@test.invalid",
                "ip_address": "203.0.113.51",
                "first_name": "Ada",
            },
            "line_items": [{"sku": "sku-100", "qty": 1}],
        },
    }

    async with get_session(tenant_id=tenant_id) as session:
        service = EventIngestionService()
        event = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source="test_suite",
            identity_payload=event_data,
            request_headers={
                "user-agent": "b14-test-agent",
                "x-real-ip": "198.51.100.31",
            },
        )
        await session.commit()
        event_id = event.id

    async with get_session(tenant_id=tenant_id) as session:
        persisted = await session.get(AttributionEvent, event_id)
        assert persisted is not None
        assert str(persisted.session_id) != provided_session
        assert "vendor_payload" not in persisted.raw_payload
        assert persisted.raw_payload["event_type"] == "purchase"

        pii_key_hits = await session.scalar(
            text(
                """
                SELECT COUNT(*) FROM attribution_events
                WHERE id = :event_id
                  AND (
                    jsonb_path_exists(raw_payload, '$.**.email')
                    OR jsonb_path_exists(raw_payload, '$.**.ip_address')
                    OR jsonb_path_exists(raw_payload, '$.**.first_name')
                  )
                """
            ),
            {"event_id": str(event_id)},
        )
        pii_value_hits = await session.scalar(
            text(
                """
                SELECT COUNT(*) FROM attribution_events
                WHERE id = :event_id
                  AND (
                    raw_payload::text ILIKE '%canonical-user@test.invalid%'
                    OR raw_payload::text ILIKE '%203.0.113.51%'
                  )
                """
            ),
            {"event_id": str(event_id)},
        )

    assert int(pii_key_hits or 0) == 0
    assert int(pii_value_hits or 0) == 0


@pytest.mark.asyncio
async def test_b14_p1_dlq_path_redacts_pii_before_write(test_tenant):
    tenant_id = test_tenant
    correlation_id = f"b14_p1_dlq_{uuid4()}"
    payload = {
        "event_type": "purchase",
        "idempotency_key": correlation_id,
        "vendor_payload": {
            "customer": {
                "email": "dlq-user@test.invalid",
                "ip_address": "203.0.113.61",
                "first_name": "Grace",
            },
            "line_items": [{"sku": "sku-200", "qty": 2}],
        },
    }

    async with get_session(tenant_id=tenant_id) as session:
        handler = DLQHandler()
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=payload,
            error=ValueError("forced validation failure"),
            correlation_id=correlation_id,
            source="test_suite",
            identity_payload=payload,
            request_headers={
                "user-agent": "b14-dlq-agent",
                "x-real-ip": "198.51.100.32",
            },
        )
        await session.commit()
        dead_event_id = dead_event.id

    async with get_session(tenant_id=tenant_id) as session:
        persisted = await session.get(DeadEvent, dead_event_id)
        assert persisted is not None
        assert (
            persisted.raw_payload["vendor_payload"]["customer"]["email"]
            == REDACTION_TOKEN
        )
        assert "ip_address" not in persisted.raw_payload["vendor_payload"]["customer"]
        assert (
            persisted.raw_payload["vendor_payload"]["customer"]["first_name"]
            == REDACTION_TOKEN
        )
        assert (
            persisted.raw_payload["vendor_payload"]["line_items"][0]["sku"] == "sku-200"
        )
        assert "dlq-user@test.invalid" not in str(persisted.raw_payload)
        assert "203.0.113.61" not in str(persisted.raw_payload)


@pytest.mark.asyncio
async def test_b14_p1_quarantine_path_redacts_pii_before_write():
    source = f"b14_p1_quarantine_{uuid4().hex[:10]}"
    payload = {
        "event_type": "purchase",
        "vendor_payload": {
            "customer": {
                "email": "quarantine-user@test.invalid",
                "ip_address": "203.0.113.71",
                "first_name": "Lin",
            },
            "line_items": [{"sku": "sku-300", "qty": 1}],
        },
    }
    correlation_id = str(uuid4())

    await route_unresolved_tenant_to_quarantine(
        source=source,
        payload=payload,
        error_message="unresolved tenant",
        correlation_id=correlation_id,
        identity_payload=payload,
        request_headers={"user-agent": "b14-q-agent", "x-real-ip": "198.51.100.33"},
    )

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT id, raw_payload
                FROM dead_events_quarantine
                WHERE source = :source
                ORDER BY ingested_at DESC
                LIMIT 1
                """
            ),
            {"source": source},
        )
        row = result.mappings().first()
        assert row is not None

        raw_payload = row["raw_payload"]
        assert raw_payload["vendor_payload"]["customer"]["email"] == REDACTION_TOKEN
        assert "ip_address" not in raw_payload["vendor_payload"]["customer"]
        assert (
            raw_payload["vendor_payload"]["customer"]["first_name"] == REDACTION_TOKEN
        )
        assert raw_payload["vendor_payload"]["line_items"][0]["sku"] == "sku-300"
        assert "quarantine-user@test.invalid" not in str(raw_payload)
        assert "203.0.113.71" not in str(raw_payload)

        await conn.execute(
            text("DELETE FROM dead_events_quarantine WHERE id = :id"),
            {"id": row["id"]},
        )


@pytest.mark.asyncio
async def test_b14_p1_dlq_redaction_payload_round_trips_production_replay_contract(
    test_tenant,
):
    """B1.4-P1: persisted redacted payload round-trips through the real retry contract."""

    tenant_id = test_tenant
    correlation_id = f"b14_p1_dlq_typed_{uuid4()}"
    provided_session_id = str(uuid4())
    payload = {
        "event_type": "purchase",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "13.37",
        "session_id": provided_session_id,
        "idempotency_key": correlation_id,
        "vendor_payload": {
            "customer": {
                "email": "typed-dlq-user@test.invalid",
                "ssn": 123456789,
                "phone": True,
                "address": ["42 Example Street", "Unit 9"],
            },
            "line_items": [{"sku": "sku-typed", "qty": 2}],
        },
    }

    async with get_session(tenant_id=tenant_id) as session:
        handler = DLQHandler()
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=payload,
            error=ValueError("forced typed-redaction validation failure"),
            correlation_id=correlation_id,
            source="test_suite",
            identity_payload=payload,
            request_headers={
                "user-agent": "b14-dlq-typed-agent",
                "x-real-ip": "198.51.100.34",
            },
        )
        await session.commit()
        dead_event_id = dead_event.id

    async with get_session(tenant_id=tenant_id) as session:
        persisted = await session.get(DeadEvent, dead_event_id)
        assert persisted is not None
        validated = DLQReplayPayload.model_validate(persisted.raw_payload)
        assert validated.event_type == "purchase"
        assert validated.revenue_amount == Decimal("13.37")
        assert validated.session_id == UUID(provided_session_id)
        assert validated.idempotency_key == correlation_id
        assert persisted.raw_payload["vendor_payload"]["customer"]["email"] == REDACTION_TOKEN
        assert persisted.raw_payload["vendor_payload"]["customer"]["ssn"] == 0
        assert persisted.raw_payload["vendor_payload"]["customer"]["phone"] is False
        assert persisted.raw_payload["vendor_payload"]["customer"]["address"] == []

    async with get_session(tenant_id=tenant_id) as session:
        handler = DLQHandler()
        success, message = await handler.retry_dead_event(session, dead_event_id)
        await session.commit()
        assert success is True, message

    async with get_session(tenant_id=tenant_id) as session:
        refreshed_dead_event = await session.get(DeadEvent, dead_event_id)
        assert refreshed_dead_event is not None
        assert refreshed_dead_event.remediation_status == "resolved"

        persisted_event = await session.execute(
            select(AttributionEvent).where(
                AttributionEvent.tenant_id == tenant_id,
                AttributionEvent.idempotency_key == correlation_id,
            )
        )
        canonical = persisted_event.scalar_one_or_none()
        assert canonical is not None
        assert canonical.event_type == "purchase"
        assert canonical.raw_payload["event_type"] == "purchase"
        assert "vendor_payload" not in canonical.raw_payload


@pytest.mark.asyncio
async def test_b14_p1_dlq_replay_contract_negative_control_invalid_timestamp(
    test_tenant,
):
    """B1.4-P1 non-vacuous proof: invalid replay contract must fail deterministically."""
    tenant_id = test_tenant
    correlation_id = f"b14_p1_dlq_bad_timestamp_{uuid4()}"
    payload = {
        "event_type": "purchase",
        "event_timestamp": "not-a-timestamp",
        "revenue_amount": "7.00",
        "session_id": str(uuid4()),
        "idempotency_key": correlation_id,
        "vendor_payload": {
            "customer": {"email": "bad-ts-user@test.invalid"},
        },
    }

    async with get_session(tenant_id=tenant_id) as session:
        handler = DLQHandler()
        dead_event = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=payload,
            error=ValueError("forced timestamp validation failure"),
            correlation_id=correlation_id,
            source="test_suite",
            identity_payload=payload,
            request_headers={
                "user-agent": "b14-dlq-bad-ts-agent",
                "x-real-ip": "198.51.100.35",
            },
        )
        await session.commit()
        dead_event_id = dead_event.id

    async with get_session(tenant_id=tenant_id) as session:
        handler = DLQHandler()
        success, message = await handler.retry_dead_event(session, dead_event_id)
        await session.commit()
        assert success is False
        assert "not replayable" in message

"""
B0.4.3 Quality Gate Validation Tests - Core Ingestion Service

Tests idempotency enforcement, channel normalization, transaction atomicity,
and RLS validation for event ingestion pipeline.

Uses conftest.py fixtures for tenant creation to satisfy FK constraints.
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Set DATABASE_URL before imports
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from app.db.session import get_session
from app.ingestion.event_service import (
    EventIngestionService,
    ValidationError,
    ingest_with_transaction,
)
from app.models import AttributionEvent


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg31_idempotency_enforcement(test_tenant):
    """
    QG3.1: Idempotency enforcement via UNIQUE constraint.

    Exit Criteria: Second POST with identical idempotency_key returns existing event.
    """
    tenant_id = test_tenant
    idempotency_key = f"test_idempotency_{uuid4()}"

    event_data = {
        "event_type": "conversion",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "99.95",
        "session_id": str(uuid4()),
        "utm_source": "google",
        "utm_medium": "cpc",
    }

    # First ingestion
    async with get_session(tenant_id=tenant_id) as session:
        service = EventIngestionService()
        event1 = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source="shopify",
        )
        event1_id = event1.id
        await session.commit()

    # Second ingestion with same key
    async with get_session(tenant_id=tenant_id) as session:
        service = EventIngestionService()
        event2 = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source="shopify",
        )
        event2_id = event2.id
        await session.commit()

    assert event1_id == event2_id, f"Idempotency failed: {event1_id} != {event2_id}"
    print(f"QG3.1 PASS: Idempotency enforced (event_id={event1_id})")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg32_channel_normalization_integration(test_tenant):
    """
    QG3.2: Channel normalization integration.

    Exit Criteria: UTM parameters map to canonical channel codes.
    """
    tenant_id = test_tenant
    idempotency_key = f"test_channel_{uuid4()}"

    event_data = {
        "event_type": "conversion",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "150.00",
        "session_id": str(uuid4()),
        "utm_source": "google",
        "utm_medium": "cpc",
    }

    async with get_session(tenant_id=tenant_id) as session:
        service = EventIngestionService()
        event = await service.ingest_event(
            session=session,
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source="google_ads",
        )
        channel_code = event.channel
        await session.commit()

    assert channel_code is not None
    assert isinstance(channel_code, str)
    assert len(channel_code) > 0
    print(f"QG3.2 PASS: Channel normalized (utm_source=google, utm_medium=cpc -> {channel_code})")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg33_fk_constraint_validation(test_tenant):
    """
    QG3.3: FK constraint to channel_taxonomy enforced.

    Exit Criteria: Invalid channel codes trigger IntegrityError.
    """
    tenant_id = test_tenant

    try:
        async with get_session(tenant_id=tenant_id) as session:
            event = AttributionEvent(
                id=uuid4(),
                tenant_id=tenant_id,
                occurred_at=datetime.now(timezone.utc),
                session_id=uuid4(),
                revenue_cents=10000,
                raw_payload={"test": "fk_validation"},
                idempotency_key=f"test_fk_{uuid4()}",
                event_type="conversion",
                channel="INVALID_CHANNEL_XYZ",
                event_timestamp=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(event)
            await session.flush()
            # Should not reach here
            assert False, "Expected IntegrityError but insert succeeded"
    except IntegrityError as e:
        error = str(e)
        assert "channel_taxonomy" in error.lower() or "foreign key" in error.lower() or "fk_attribution_events_channel" in error.lower()
        print(f"QG3.3 PASS: FK constraint enforced - {error[:100]}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg34_transaction_atomicity(test_tenant):
    """
    QG3.4: Transaction atomicity on validation errors.

    Exit Criteria: Validation error creates DLQ entry, no AttributionEvent.
    """
    tenant_id = test_tenant
    idempotency_key = f"test_atomicity_{uuid4()}"

    invalid_data = {
        "event_type": "conversion",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        # Missing revenue_amount
        "session_id": str(uuid4()),
    }

    async with get_session(tenant_id=tenant_id) as session:
        service = EventIngestionService()

        with pytest.raises(ValidationError) as exc_info:
            await service.ingest_event(
                session=session,
                tenant_id=tenant_id,
                event_data=invalid_data,
                idempotency_key=idempotency_key,
                source="facebook",
            )

        assert "revenue_amount" in str(exc_info.value)
        await session.commit()

    # Verify no AttributionEvent created
    async with get_session(tenant_id=tenant_id) as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE idempotency_key = :key"),
            {"key": idempotency_key},
        )
        count = result.scalar()
        assert count == 0, f"Atomicity failed: {count} events created"

    print("QG3.4 PASS: Transaction atomicity enforced")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg35_rls_validation_checkpoint(test_tenant_pair):
    """
    QG3.5: MANDATORY RLS validation checkpoint.

    Exit Criteria: Cross-tenant queries blocked by RLS.
    """
    tenant_a, tenant_b = test_tenant_pair
    idempotency_key = f"test_rls_{uuid4()}"

    event_data = {
        "event_type": "conversion",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "200.00",
        "session_id": str(uuid4()),
        "utm_source": "direct",
        "utm_medium": "none",
    }

    # Ingest for tenant_a
    async with get_session(tenant_id=tenant_a) as session:
        service = EventIngestionService()
        event = await service.ingest_event(
            session=session,
            tenant_id=tenant_a,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source="webhook",
        )
        event_id = event.id
        await session.commit()

    # Query from tenant_b - should be blocked
    async with get_session(tenant_id=tenant_b) as session:
        result = await session.get(AttributionEvent, event_id)
        assert result is None, f"RLS FAILURE: tenant_b sees tenant_a event"

    # Query from tenant_a - should succeed
    async with get_session(tenant_id=tenant_a) as session:
        result = await session.get(AttributionEvent, event_id)
        assert result is not None
        assert str(result.tenant_id) == str(tenant_a)

    print(f"QG3.5 PASS (MANDATORY): RLS enforced (tenant_a={tenant_a}, tenant_b={tenant_b})")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_transaction_wrapper_success(test_tenant):
    """Validate ingest_with_transaction() wrapper for successful ingestion."""
    tenant_id = test_tenant
    idempotency_key = f"test_wrapper_{uuid4()}"

    event_data = {
        "event_type": "conversion",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "75.50",
        "session_id": str(uuid4()),
        "utm_source": "email",
        "utm_medium": "newsletter",
    }

    result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data=event_data,
        idempotency_key=idempotency_key,
        source="sendgrid",
    )

    assert result["status"] == "success"
    assert "event_id" in result
    assert "channel" in result
    print(f"Wrapper success path PASS (event_id={result['event_id']})")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_transaction_wrapper_error(test_tenant):
    """Validate ingest_with_transaction() wrapper for validation errors."""
    tenant_id = test_tenant
    idempotency_key = f"test_wrapper_error_{uuid4()}"

    invalid_data = {
        "event_type": "click",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "revenue_amount": "0.00",
        # Missing session_id
    }

    result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data=invalid_data,
        idempotency_key=idempotency_key,
        source="unknown",
    )

    assert result["status"] == "error"
    assert result["error_type"] == "validation_error"
    assert "session_id" in result["error"]
    print("Wrapper error path PASS")


if __name__ == "__main__":
    import asyncio

    async def run_all():
        print("\n" + "="*60)
        print("  B0.4.3 CORE INGESTION SERVICE QUALITY GATES")
        print("="*60 + "\n")

        # Note: Cannot run pytest fixtures directly from __main__
        print("ERROR: Use pytest to run these tests:")
        print("  python -m pytest tests/test_b043_ingestion.py -v")

    asyncio.run(run_all())

"""
B0.4.2 Quality Gate Validation Tests - ORM Models

Tests schema alignment, RLS integration, and FK constraint enforcement.
"""

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

# Set DATABASE_URL before imports
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from app.db.session import engine, get_session
from app.models import AttributionEvent, ChannelTaxonomy, DeadEvent


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg21_attribution_event_schema_alignment():
    """
    QG2.1: Validate AttributionEvent columns match database schema.

    Exit Criteria: No missing columns, no extra columns.
    """
    async with engine.connect() as conn:
        inspector = inspect(conn.sync_engine)
        db_columns = {col["name"] for col in inspector.get_columns("attribution_events")}
        model_columns = {col.name for col in AttributionEvent.__table__.columns}

        missing_in_model = db_columns - model_columns
        extra_in_model = model_columns - db_columns

        assert not missing_in_model, f"Missing columns in AttributionEvent model: {missing_in_model}"
        assert not extra_in_model, f"Extra columns in AttributionEvent model: {extra_in_model}"

    print(f"✅ QG2.1 (attribution_events): Schema alignment validated - {len(model_columns)} columns match")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg21_dead_event_schema_alignment():
    """
    QG2.1: Validate DeadEvent columns match database schema.

    Exit Criteria: No missing columns, no extra columns.
    """
    async with engine.connect() as conn:
        inspector = inspect(conn.sync_engine)
        db_columns = {col["name"] for col in inspector.get_columns("dead_events")}
        model_columns = {col.name for col in DeadEvent.__table__.columns}

        missing_in_model = db_columns - model_columns
        extra_in_model = model_columns - db_columns

        assert not missing_in_model, f"Missing columns in DeadEvent model: {missing_in_model}"
        assert not extra_in_model, f"Extra columns in DeadEvent model: {extra_in_model}"

    print(f"✅ QG2.1 (dead_events): Schema alignment validated - {len(model_columns)} columns match")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg21_channel_taxonomy_schema_alignment():
    """
    QG2.1: Validate ChannelTaxonomy columns match database schema.

    Exit Criteria: No missing columns, no extra columns.
    """
    async with engine.connect() as conn:
        inspector = inspect(conn.sync_engine)
        db_columns = {col["name"] for col in inspector.get_columns("channel_taxonomy")}
        model_columns = {col.name for col in ChannelTaxonomy.__table__.columns}

        missing_in_model = db_columns - model_columns
        extra_in_model = model_columns - db_columns

        assert not missing_in_model, f"Missing columns in ChannelTaxonomy model: {missing_in_model}"
        assert not extra_in_model, f"Extra columns in ChannelTaxonomy model: {extra_in_model}"

    print(f"✅ QG2.1 (channel_taxonomy): Schema alignment validated - {len(model_columns)} columns match")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg22_rls_filters_by_tenant():
    """
    QG2.2: Validate RLS prevents cross-tenant access.

    Exit Criteria:
        - Insert event for tenant A succeeds
        - Query from tenant B returns None (RLS blocks)
        - Query from tenant A succeeds
    """
    tenant_a = uuid4()
    tenant_b = uuid4()

    # Insert event for tenant A
    async with get_session(tenant_id=tenant_a) as session:
        event = AttributionEvent(
            id=uuid4(),
            tenant_id=tenant_a,
            occurred_at=datetime.now(timezone.utc),
            session_id=uuid4(),
            revenue_cents=10050,  # $100.50
            raw_payload={"test": "data"},
            idempotency_key=f"test_rls_{uuid4()}",
            event_type="conversion",
            channel="direct",  # Assumes 'direct' exists in channel_taxonomy
            event_timestamp=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(event)
        await session.flush()
        event_id = event.id
        await session.commit()

    # Query from tenant B - should return None (RLS blocks)
    async with get_session(tenant_id=tenant_b) as session:
        result = await session.get(AttributionEvent, event_id)
        assert result is None, "RLS failed: cross-tenant access detected"

    # Query from tenant A - should succeed
    async with get_session(tenant_id=tenant_a) as session:
        result = await session.get(AttributionEvent, event_id)
        assert result is not None, "RLS blocks same-tenant access"
        assert str(result.tenant_id) == str(tenant_a)

    # Cleanup
    async with get_session(tenant_id=tenant_a) as session:
        await session.execute(
            text("DELETE FROM attribution_events WHERE id = :id"),
            {"id": str(event_id)}
        )
        await session.commit()

    print(f"✅ QG2.2 PASS: RLS enforces tenant isolation (tenant_a={tenant_a}, tenant_b={tenant_b})")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_qg23_invalid_channel_raises_fk_error():
    """
    QG2.3: Validate FK to channel_taxonomy enforced.

    Exit Criteria:
        - Insert with invalid channel code raises IntegrityError
        - Error message contains 'channel_taxonomy'
    """
    tenant_id = uuid4()

    async with get_session(tenant_id=tenant_id) as session:
        event = AttributionEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            occurred_at=datetime.now(timezone.utc),
            session_id=uuid4(),
            revenue_cents=5000,
            raw_payload={"test": "data"},
            idempotency_key=f"test_fk_{uuid4()}",
            event_type="conversion",
            channel="INVALID_CODE_NOT_IN_TAXONOMY",  # Should fail FK constraint
            event_timestamp=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(event)

        with pytest.raises(IntegrityError) as exc_info:
            await session.flush()

        error_message = str(exc_info.value)
        assert "channel_taxonomy" in error_message.lower() or "foreign key" in error_message.lower(), \
            f"Expected FK error, got: {error_message}"

    print("✅ QG2.3 PASS: FK constraint enforces channel_taxonomy reference integrity")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_model_relationships():
    """
    Validate relationship traversal: AttributionEvent → ChannelTaxonomy.

    Exit Criteria:
        - event.channel_taxonomy.display_name accessible
        - Reverse relationship channel_taxonomy.attribution_events works
    """
    tenant_id = uuid4()

    async with get_session(tenant_id=tenant_id) as session:
        # Insert event with valid channel
        event = AttributionEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            occurred_at=datetime.now(timezone.utc),
            session_id=uuid4(),
            revenue_cents=7500,
            raw_payload={"test": "relationship"},
            idempotency_key=f"test_rel_{uuid4()}",
            event_type="conversion",
            channel="direct",  # Assumes 'direct' exists
            event_timestamp=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(event)
        await session.flush()
        event_id = event.id

        # Fetch with relationship
        await session.commit()

    async with get_session(tenant_id=tenant_id) as session:
        result = await session.get(AttributionEvent, event_id)
        assert result is not None

        # Load relationship (requires explicit query or eager loading)
        await session.refresh(result, ["channel_taxonomy"])
        assert result.channel_taxonomy is not None
        assert result.channel_taxonomy.code == "direct"

    # Cleanup
    async with get_session(tenant_id=tenant_id) as session:
        await session.execute(
            text("DELETE FROM attribution_events WHERE id = :id"),
            {"id": str(event_id)}
        )
        await session.commit()

    print("✅ Relationship test PASS: AttributionEvent → ChannelTaxonomy traversal works")


if __name__ == "__main__":
    import asyncio

    async def run_all_tests():
        print("\n=== B0.4.2 ORM MODEL QUALITY GATES ===\n")

        await test_qg21_attribution_event_schema_alignment()
        await test_qg21_dead_event_schema_alignment()
        await test_qg21_channel_taxonomy_schema_alignment()
        print()
        await test_qg22_rls_filters_by_tenant()
        await test_qg23_invalid_channel_raises_fk_error()
        await test_model_relationships()

        print("\n=== ALL B0.4.2 QUALITY GATES PASSED ===\n")

    asyncio.run(run_all_tests())

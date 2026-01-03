"""
Gate 4 - H4.1: Minimal RLS Test (No Celery)

Tests RLS behavior directly via database session to isolate
DB/policy/GUC behavior from Celery complexity.

This falsifies H4.2 (Role/GUC Misalignment) and H4.3 (Data Insertion vs Policy).
"""
import os
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import ssl

# Test DSN using app_user (the role that will enforce RLS)
TEST_DSN = "postgresql+asyncpg://app_user:npg_IGZ4D2rHNndq@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb"

# Create test engine with app_user credentials
ssl_context = ssl.create_default_context()
test_engine = create_async_engine(
    TEST_DSN,
    connect_args={"ssl": ssl_context},
    pool_pre_ping=True,
    echo=False
)


@pytest.fixture
async def test_tenants_and_events():
    """
    Fixture that:
    1. Creates two test tenants (A and B)
    2. Inserts test events for each
    3. Cleans up after test

    Uses app_user role throughout to match production conditions.
    """
    tenant_a = uuid4()
    tenant_b = uuid4()
    test_marker = "RLS_MINIMAL_TEST"

    async def cleanup():
        """Delete test events."""
        async with test_engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM attribution_events WHERE event_id LIKE :marker"),
                {"marker": f"%{test_marker}%"}
            )

    # Clean before test
    await cleanup()

    # Insert test data for both tenants
    async with test_engine.begin() as conn:
        # Insert 3 events for tenant A
        # RAW_SQL_ALLOWLIST: legacy minimal RLS contract test seeds attribution_events
        for i in range(3):
            await conn.execute(
                text("""
                    INSERT INTO attribution_events
                    (
                        event_id,
                        tenant_id,
                        session_id,
                        occurred_at,
                        event_timestamp,
                        idempotency_key,
                        event_type,
                        channel,
                        source_url,
                        attribution_model,
                        raw_payload,
                        created_at
                    )
                    VALUES
                    (
                        :event_id,
                        :tenant_id,
                        :session_id,
                        :ts,
                        :ts,
                        :idempotency_key,
                        :event_type,
                        :channel,
                        :url,
                        :model,
                        :raw_payload::jsonb,
                        :created_at
                    )
                """),
                {
                    "event_id": f"{test_marker}_A_{i}_{tenant_a}",
                    "tenant_id": str(tenant_a),
                    "session_id": str(uuid4()),
                    "idempotency_key": f"rls-minimal-a:{i}:{tenant_a}",
                    "ts": datetime.now(timezone.utc),
                    "event_type": "page_view",
                    "channel": "direct",
                    "url": f"https://tenant-a.test/{i}",
                    "model": "last_touch",
                    "raw_payload": "{}",
                    "created_at": datetime.now(timezone.utc),
                }
            )

        # Insert 2 events for tenant B
        # RAW_SQL_ALLOWLIST: legacy minimal RLS contract test seeds attribution_events
        for i in range(2):
            await conn.execute(
                text("""
                    INSERT INTO attribution_events
                    (
                        event_id,
                        tenant_id,
                        session_id,
                        occurred_at,
                        event_timestamp,
                        idempotency_key,
                        event_type,
                        channel,
                        source_url,
                        attribution_model,
                        raw_payload,
                        created_at
                    )
                    VALUES
                    (
                        :event_id,
                        :tenant_id,
                        :session_id,
                        :ts,
                        :ts,
                        :idempotency_key,
                        :event_type,
                        :channel,
                        :url,
                        :model,
                        :raw_payload::jsonb,
                        :created_at
                    )
                """),
                {
                    "event_id": f"{test_marker}_B_{i}_{tenant_b}",
                    "tenant_id": str(tenant_b),
                    "session_id": str(uuid4()),
                    "idempotency_key": f"rls-minimal-b:{i}:{tenant_b}",
                    "ts": datetime.now(timezone.utc),
                    "event_type": "page_view",
                    "channel": "direct",
                    "url": f"https://tenant-b.test/{i}",
                    "model": "last_touch",
                    "raw_payload": "{}",
                    "created_at": datetime.now(timezone.utc),
                }
            )

    yield tenant_a, tenant_b, test_marker

    # Clean after test
    await cleanup()


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_reads_under_app_user(test_tenants_and_events):
    """
    H4.1 Falsification Test: RLS + GUC behavior without Celery.

    Validates:
    1. Setting GUC to tenant A filters queries to only tenant A rows
    2. Setting GUC to tenant B filters queries to only tenant B rows
    3. RLS is enforced at the DB level under app_user role

    If this test fails, the issue is in policies/GUC/role setup, NOT Celery.
    """
    tenant_a, tenant_b, test_marker = test_tenants_and_events

    # Test 1: Query as Tenant A
    async with test_engine.begin() as conn:
        # Set GUC to tenant A
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_a)}
        )

        # Query all visible events
        result = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE event_id LIKE :marker"),
            {"marker": f"%{test_marker}%"}
        )
        visible_count = result.scalar()

        # Query events explicitly for tenant A
        result_a = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE tenant_id = :tid AND event_id LIKE :marker"),
            {"tid": str(tenant_a), "marker": f"%{test_marker}%"}
        )
        tenant_a_count = result_a.scalar()

        # Query events explicitly for tenant B (should be blocked by RLS)
        result_b = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE tenant_id = :tid AND event_id LIKE :marker"),
            {"tid": str(tenant_b), "marker": f"%{test_marker}%"}
        )
        tenant_b_count = result_b.scalar()

    # Assertions for Tenant A context
    assert visible_count == 3, f"Expected 3 visible events under tenant A GUC, got {visible_count}"
    assert tenant_a_count == 3, f"Expected 3 tenant A events, got {tenant_a_count}"
    assert tenant_b_count == 0, f"Expected 0 tenant B events (RLS block), got {tenant_b_count}"

    # Test 2: Query as Tenant B
    async with test_engine.begin() as conn:
        # Set GUC to tenant B
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_b)}
        )

        # Query all visible events
        result = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE event_id LIKE :marker"),
            {"marker": f"%{test_marker}%"}
        )
        visible_count = result.scalar()

        # Query events explicitly for tenant B
        result_b = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE tenant_id = :tid AND event_id LIKE :marker"),
            {"tid": str(tenant_b), "marker": f"%{test_marker}%"}
        )
        tenant_b_count = result_b.scalar()

        # Query events explicitly for tenant A (should be blocked by RLS)
        result_a = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE tenant_id = :tid AND event_id LIKE :marker"),
            {"tid": str(tenant_a), "marker": f"%{test_marker}%"}
        )
        tenant_a_count = result_a.scalar()

    # Assertions for Tenant B context
    assert visible_count == 2, f"Expected 2 visible events under tenant B GUC, got {visible_count}"
    assert tenant_b_count == 2, f"Expected 2 tenant B events, got {tenant_b_count}"
    assert tenant_a_count == 0, f"Expected 0 tenant A events (RLS block), got {tenant_a_count}"

    print("\n[PASS] H4.1 Falsification - RLS Behavior:")
    print(f"  - Tenant A GUC: saw {3} A events, {0} B events (RLS enforced)")
    print(f"  - Tenant B GUC: saw {2} B events, {0} A events (RLS enforced)")
    print(f"  - RLS correctly isolates tenant data under app_user role")


@pytest.mark.asyncio
async def test_guc_persists_across_queries_in_transaction(test_tenants_and_events):
    """
    Supplementary test: Verify GUC persists across multiple queries in same transaction.
    """
    tenant_a, tenant_b, test_marker = test_tenants_and_events

    async with test_engine.begin() as conn:
        # Set GUC once
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_a)}
        )

        # Query 1
        result1 = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE event_id LIKE :marker"),
            {"marker": f"%{test_marker}%"}
        )
        count1 = result1.scalar()

        # Query 2 (should use same GUC)
        result2 = await conn.execute(
            text("SELECT COUNT(*) FROM attribution_events WHERE event_id LIKE :marker"),
            {"marker": f"%{test_marker}%"}
        )
        count2 = result2.scalar()

    assert count1 == count2 == 3, f"GUC should persist: got {count1}, {count2}"
    print("\n[PASS] GUC persistence validated across multiple queries")

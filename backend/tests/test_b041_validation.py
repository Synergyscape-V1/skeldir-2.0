"""
B0.4.1 Quality Gate Validation Tests

Tests database connectivity, configuration loading, and RLS enforcement.
"""

import os
import pytest
from uuid import uuid4
from sqlalchemy import text

# Set DATABASE_URL before importing config
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from app.core.config import settings
from app.db.session import engine, get_session, validate_database_connection


@pytest.mark.asyncio
async def test_qg11_configuration_loads():
    """QG1.1: Configuration loads from environment"""
    assert settings.DATABASE_URL is not None
    assert settings.TENANT_API_KEY_HEADER == "X-Skeldir-Tenant-Key"
    assert settings.DATABASE_POOL_SIZE == 10
    assert settings.DATABASE_MAX_OVERFLOW == 20
    print("✅ QG1.1 PASS: Configuration loads successfully")


@pytest.mark.asyncio
async def test_qg12_database_engine_creation():
    """QG1.2: Engine creates successfully and connects to database"""
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1 AS test"))
        value = result.scalar()
        assert value == 1
    print("✅ QG1.2 PASS: Database engine connects successfully")


@pytest.mark.asyncio
async def test_qg12_extended_database_validation():
    """QG1.2 Extended: Validate database connection helper"""
    await validate_database_connection()
    print("✅ QG1.2 Extended PASS: Database validation function works")


@pytest.mark.asyncio
async def test_qg13_rls_session_variable():
    """QG1.3: Session sets RLS context (app.current_tenant_id)"""
    tenant_id = uuid4()

    async with get_session(tenant_id=tenant_id) as session:
        # Query the session variable that was set
        result = await session.execute(
            text("SELECT current_setting('app.current_tenant_id', true) AS tenant_context")
        )
        set_tenant_id = result.scalar()
        assert set_tenant_id == str(tenant_id), f"Expected {tenant_id}, got {set_tenant_id}"

    print(f"✅ QG1.3 PASS: RLS context set correctly to {tenant_id}")


@pytest.mark.asyncio
async def test_schema_exists():
    """Validate that B0.3 schema foundation exists"""
    async with engine.begin() as conn:
        # Check attribution_events table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'attribution_events'
                )
            """)
        )
        events_exists = result.scalar()
        assert events_exists, "attribution_events table does not exist"

        # Check dead_events table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'dead_events'
                )
            """)
        )
        dead_exists = result.scalar()
        assert dead_exists, "dead_events table does not exist"

        # Check channel_taxonomy table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'channel_taxonomy'
                )
            """)
        )
        taxonomy_exists = result.scalar()
        assert taxonomy_exists, "channel_taxonomy table does not exist"

    print("✅ B0.3 Schema Foundation: All critical tables exist")


@pytest.mark.asyncio
async def test_rls_enabled():
    """Validate RLS is enabled on critical tables"""
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE tablename IN ('attribution_events', 'dead_events', 'channel_taxonomy')
                ORDER BY tablename
            """)
        )
        rows = result.fetchall()

        rls_status = {row[0]: row[1] for row in rows}

        assert rls_status.get('attribution_events') is True, "attribution_events RLS not enabled"
        assert rls_status.get('dead_events') is True, "dead_events RLS not enabled"
        # channel_taxonomy should NOT have RLS (reference data)

    print("✅ RLS Status Validated: attribution_events and dead_events have RLS enabled")


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        print("\n=== B0.4.1 QUALITY GATE VALIDATION ===\n")

        await test_qg11_configuration_loads()
        await test_qg12_database_engine_creation()
        await test_qg12_extended_database_validation()
        await test_qg13_rls_session_variable()
        await test_schema_exists()
        await test_rls_enabled()

        print("\n=== ALL QUALITY GATES PASSED ===\n")

    asyncio.run(run_tests())

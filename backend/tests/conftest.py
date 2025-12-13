"""
Pytest fixtures for B0.4.3 tests.

Provides tenant creation/cleanup fixtures to satisfy FK constraints.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from app.db.session import engine


@pytest.fixture(scope="function")
async def test_tenant():
    """
    Create a test tenant record and clean up after test.

    Returns tenant_id UUID that satisfies FK constraints.
    """
    tenant_id = uuid4()
    api_key_hash = "test_hash_" + str(tenant_id)[:8]

    async with engine.begin() as conn:
        # Insert tenant record (id is the PK, not tenant_id)
        await conn.execute(
            text("""
                INSERT INTO tenants (id, api_key_hash, name, notification_email, created_at, updated_at)
                VALUES (:id, :api_key_hash, :name, :email, NOW(), NOW())
            """),
            {
                "id": str(tenant_id),
                "api_key_hash": api_key_hash,
                "name": f"Test Tenant {str(tenant_id)[:8]}",
                "email": f"test_{str(tenant_id)[:8]}@test.local",
            },
        )

    yield tenant_id

    # Cleanup - delete tenant and cascading records
    # Note: attribution_events is append-only (trg_events_prevent_mutation)
    # We cannot delete from it, so we skip cleanup for that table
    async with engine.begin() as conn:
        # Skip attribution_events cleanup (append-only)
        # await conn.execute(
        #     text("DELETE FROM attribution_events WHERE tenant_id = :tid"),
        #     {"tid": str(tenant_id)},
        # )

        # Dead events can be deleted (no mutation trigger)
        try:
            await conn.execute(
                text("DELETE FROM dead_events WHERE tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )
        except Exception:
            pass  # Best effort cleanup

        # Tenants - may fail due to FK constraints from attribution_events
        # We'll leave test tenants in database for now
        # Production cleanup would use archival/retention policies
        # await conn.execute(
        #     text("DELETE FROM tenants WHERE id = :tid"),
        #     {"tid": str(tenant_id)},
        # )


@pytest.fixture(scope="function")
async def test_tenant_pair():
    """
    Create two test tenant records for RLS validation tests.

    Returns tuple (tenant_a_id, tenant_b_id).
    """
    tenant_a = uuid4()
    tenant_b = uuid4()

    async with engine.begin() as conn:
        # Insert both tenants
        for tenant_id in [tenant_a, tenant_b]:
            await conn.execute(
                text("""
                    INSERT INTO tenants (id, api_key_hash, name, notification_email, created_at, updated_at)
                    VALUES (:id, :api_key_hash, :name, :email, NOW(), NOW())
                """),
                {
                    "id": str(tenant_id),
                    "api_key_hash": f"test_hash_{str(tenant_id)[:8]}",
                    "name": f"Test Tenant {str(tenant_id)[:8]}",
                    "email": f"test_{str(tenant_id)[:8]}@test.local",
                },
            )

    yield (tenant_a, tenant_b)

    # Cleanup (best effort - attribution_events is append-only)
    async with engine.begin() as conn:
        for tenant_id in [tenant_a, tenant_b]:
            # Skip attribution_events (append-only)
            # Dead events cleanup
            try:
                await conn.execute(
                    text("DELETE FROM dead_events WHERE tenant_id = :tid"),
                    {"tid": str(tenant_id)},
                )
            except Exception:
                pass
            # Skip tenants (FK constraints)

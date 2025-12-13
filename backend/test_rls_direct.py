"""Direct RLS test with actual data insertion and querying"""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

os.environ["DATABASE_URL"] = "postgresql://app_user:Sk3ld1r_App_Pr0d_2025!@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from sqlalchemy import text
from app.db.session import engine, get_session
from app.models import AttributionEvent


async def main():
    # Create two test tenants
    tenant_a = uuid4()
    tenant_b = uuid4()

    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO tenants (id, api_key_hash, name, notification_email, created_at, updated_at)
            VALUES
                (:tenant_a, :hash_a, 'Tenant A RLS Test', 'a@test.com', NOW(), NOW()),
                (:tenant_b, :hash_b, 'Tenant B RLS Test', 'b@test.com', NOW(), NOW())
        """), {
            "tenant_a": str(tenant_a),
            "tenant_b": str(tenant_b),
            "hash_a": f"hash_a_{str(tenant_a)[:8]}",
            "hash_b": f"hash_b_{str(tenant_b)[:8]}",
        })

    print("\n" + "="*70)
    print("DIRECT RLS TEST")
    print("="*70)
    print(f"Tenant A: {tenant_a}")
    print(f"Tenant B: {tenant_b}")

    # Insert event for tenant A using ORM
    event_id = None
    async with get_session(tenant_id=tenant_a) as session:
        event = AttributionEvent(
            id=uuid4(),
            tenant_id=tenant_a,
            occurred_at=datetime.now(timezone.utc),
            session_id=uuid4(),
            revenue_cents=10000,
            raw_payload={"test": "rls_direct"},
            idempotency_key=f"rls_direct_test_{uuid4()}",
            event_type="conversion",
            channel="direct",
            event_timestamp=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(event)
        await session.flush()
        event_id = event.id
        await session.commit()

    print(f"\nInserted event: {event_id}")

    # Try to query as tenant B
    print(f"\nQuerying as Tenant B (should fail)...")
    async with get_session(tenant_id=tenant_b) as session:
        # Check current setting
        result = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        current = result.scalar()
        print(f"  Current tenant context: {current}")

        # Try to get the event
        result_event = await session.get(AttributionEvent, event_id)
        if result_event is None:
            print(f"  Result: None (RLS WORKING)")
        else:
            print(f"  Result: {result_event} (RLS NOT WORKING!)")
            print(f"  Event tenant_id: {result_event.tenant_id}")

    # Query as tenant A (should succeed)
    print(f"\nQuerying as Tenant A (should succeed)...")
    async with get_session(tenant_id=tenant_a) as session:
        result = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        current = result.scalar()
        print(f"  Current tenant context: {current}")

        result_event = await session.get(AttributionEvent, event_id)
        if result_event is not None:
            print(f"  Result: {result_event} (RLS WORKING)")
        else:
            print(f"  Result: None (RLS NOT WORKING!)")

    print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())

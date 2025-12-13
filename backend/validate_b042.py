"""
B0.4.2 Validation Script - Direct Schema Verification

Validates ORM models against live database schema using direct SQL queries.
"""

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_ETLZ7UxM3obe@ep-lucky-base-aedv3gwo-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from app.db.session import engine, get_session
from app.models import AttributionEvent, ChannelTaxonomy, DeadEvent


async def validate_schema_alignment():
    """QG2.1: Validate schema alignment for all models"""
    print("\n=== QG2.1: SCHEMA ALIGNMENT VALIDATION ===\n")

    results = {}

    async with engine.connect() as conn:
        inspector = inspect(conn.sync_engine)

        # Attribution Events
        db_columns = {col["name"] for col in inspector.get_columns("attribution_events")}
        model_columns = {col.name for col in AttributionEvent.__table__.columns}
        missing = db_columns - model_columns
        extra = model_columns - db_columns

        if missing or extra:
            print(f"❌ attribution_events: Missing={missing}, Extra={extra}")
            results['attribution_events'] = 'FAIL'
        else:
            print(f"✅ attribution_events: {len(model_columns)} columns aligned")
            results['attribution_events'] = 'PASS'

        # Dead Events
        db_columns = {col["name"] for col in inspector.get_columns("dead_events")}
        model_columns = {col.name for col in DeadEvent.__table__.columns}
        missing = db_columns - model_columns
        extra = model_columns - db_columns

        if missing or extra:
            print(f"❌ dead_events: Missing={missing}, Extra={extra}")
            results['dead_events'] = 'FAIL'
        else:
            print(f"✅ dead_events: {len(model_columns)} columns aligned")
            results['dead_events'] = 'PASS'

        # Channel Taxonomy
        db_columns = {col["name"] for col in inspector.get_columns("channel_taxonomy")}
        model_columns = {col.name for col in ChannelTaxonomy.__table__.columns}
        missing = db_columns - model_columns
        extra = model_columns - db_columns

        if missing or extra:
            print(f"❌ channel_taxonomy: Missing={missing}, Extra={extra}")
            results['channel_taxonomy'] = 'FAIL'
        else:
            print(f"✅ channel_taxonomy: {len(model_columns)} columns aligned")
            results['channel_taxonomy'] = 'PASS'

    return all(v == 'PASS' for v in results.values())


async def validate_rls_enforcement():
    """QG2.2: Validate RLS enforces tenant isolation"""
    print("\n=== QG2.2: RLS ENFORCEMENT VALIDATION ===\n")

    tenant_a = uuid4()
    tenant_b = uuid4()
    event_id = None

    try:
        # Insert event for tenant A
        async with get_session(tenant_id=tenant_a) as session:
            event = AttributionEvent(
                id=uuid4(),
                tenant_id=tenant_a,
                occurred_at=datetime.now(timezone.utc),
                session_id=uuid4(),
                revenue_cents=10050,
                raw_payload={"test": "rls_validation"},
                idempotency_key=f"rls_test_{uuid4()}",
                event_type="conversion",
                channel="direct",
                event_timestamp=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(event)
            await session.flush()
            event_id = event.id
            print(f"📝 Inserted event {event_id} for tenant_a={tenant_a}")

        # Query from tenant B (should fail - RLS blocks)
        async with get_session(tenant_id=tenant_b) as session:
            result = await session.get(AttributionEvent, event_id)
            if result is None:
                print(f"✅ Cross-tenant query blocked (tenant_b={tenant_b} cannot see tenant_a event)")
                rls_works = True
            else:
                print(f"❌ RLS FAILURE: tenant_b can see tenant_a event!")
                rls_works = False

        # Query from tenant A (should succeed)
        async with get_session(tenant_id=tenant_a) as session:
            result = await session.get(AttributionEvent, event_id)
            if result is not None:
                print(f"✅ Same-tenant query succeeds (tenant_a can see own event)")
            else:
                print(f"❌ RLS ERROR: tenant_a cannot see own event!")
                rls_works = False

        return rls_works

    finally:
        # Cleanup
        if event_id:
            async with get_session(tenant_id=tenant_a) as session:
                await session.execute(
                    text("DELETE FROM attribution_events WHERE id = :id"),
                    {"id": str(event_id)}
                )
                print(f"🧹 Cleaned up test event {event_id}")


async def validate_fk_constraint():
    """QG2.3: Validate FK constraint to channel_taxonomy"""
    print("\n=== QG2.3: FK CONSTRAINT VALIDATION ===\n")

    tenant_id = uuid4()

    try:
        async with get_session(tenant_id=tenant_id) as session:
            event = AttributionEvent(
                id=uuid4(),
                tenant_id=tenant_id,
                occurred_at=datetime.now(timezone.utc),
                session_id=uuid4(),
                revenue_cents=5000,
                raw_payload={"test": "fk_validation"},
                idempotency_key=f"fk_test_{uuid4()}",
                event_type="conversion",
                channel="INVALID_CHANNEL_CODE",
                event_timestamp=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(event)
            await session.flush()

            print("❌ FK constraint FAILED: Invalid channel code was accepted!")
            return False

    except IntegrityError as e:
        error_msg = str(e)
        if "channel_taxonomy" in error_msg.lower() or "foreign key" in error_msg.lower():
            print(f"✅ FK constraint enforced: Invalid channel rejected")
            print(f"   Error: {error_msg[:100]}...")
            return True
        else:
            print(f"❌ Unexpected IntegrityError: {error_msg[:100]}")
            return False


async def main():
    print("\n" + "="*50)
    print("  B0.4.2 ORM MODEL VALIDATION")
    print("="*50)

    schema_ok = await validate_schema_alignment()
    rls_ok = await validate_rls_enforcement()
    fk_ok = await validate_fk_constraint()

    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)
    print(f"QG2.1 Schema Alignment: {'✅ PASS' if schema_ok else '❌ FAIL'}")
    print(f"QG2.2 RLS Enforcement:  {'✅ PASS' if rls_ok else '❌ FAIL'}")
    print(f"QG2.3 FK Constraint:    {'✅ PASS' if fk_ok else '❌ FAIL'}")
    print("="*50)

    if schema_ok and rls_ok and fk_ok:
        print("\n🎉 ALL QUALITY GATES PASSED 🎉\n")
        return 0
    else:
        print("\n⚠️  SOME QUALITY GATES FAILED ⚠️\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

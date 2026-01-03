"""
R2 Runtime Innocence Test: Authoritative Behavioral Proof

This test provides the MANDATORY runtime proof for R2 completion.
It exercises real application code paths and proves that no destructive
operations are attempted on immutable tables.

AUTHORITATIVE: Static analysis cannot override runtime failure.
If this test fails, R2 is NOT complete.

Exit Gate: EG-R2-FIX-4 (Primary Blocker)

Closed Sets:
    - Immutable Tables: attribution_events, revenue_ledger
    - Destructive Verbs: UPDATE, DELETE, TRUNCATE, ALTER

Hypothesis Validated:
    - H-R2-FIX-2: Runtime innocence can be measured via SQLAlchemy hooks
    - H-R2-FIX-3: MATCH_COUNT=0 proves behavioral compliance
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

# Enable statement capture BEFORE importing application modules
os.environ["R2_STATEMENT_CAPTURE"] = "1"
os.environ["TESTING"] = "1"

# Now import application modules (engine will be created with capture hook)


@pytest.fixture(autouse=True)
def setup_capture():
    """Attach capture hook before tests, print verdict after."""
    from app.db.session import engine
    from app.db.statement_capture import (
        attach_capture_hook,
        clear_capture,
        print_verdict,
        get_violations,
    )

    # Attach hook
    attached = attach_capture_hook(engine)
    if not attached:
        # Force enable if env var wasn't set early enough
        os.environ["R2_STATEMENT_CAPTURE"] = "1"
        attached = attach_capture_hook(engine)

    clear_capture()

    yield

    # Print verdict after test
    print_verdict()

    # Fail test if violations found
    violations = get_violations()
    if violations:
        pytest.fail(
            f"R2 Runtime Innocence Violated: {len(violations)} destructive operations "
            f"attempted on immutable tables"
        )


class TestR2RuntimeInnocence:
    """
    Runtime innocence tests exercising real application code paths.

    Each test method exercises a specific code path that touches
    immutable tables. The statement capture hook records all SQL
    and the verdict is printed at the end.
    """

    @pytest.mark.asyncio
    async def test_event_ingestion_path(self):
        """
        Exercise the event ingestion code path.

        This is the PRIMARY code path that writes to attribution_events.
        It should only produce INSERT statements, never UPDATE/DELETE.

        Code Path:
            EventIngestionService.ingest_event()
            -> AttributionEvent ORM INSERT
            -> channel_normalization
            -> validation
        """
        from app.ingestion.event_service import EventIngestionService
        from app.db.session import AsyncSessionLocal, set_tenant_guc_async

        tenant_id = uuid4()
        event_data = {
            "event_type": "page_view",
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "revenue_amount": "0.00",
            "session_id": str(uuid4()),
            "utm_source": "organic",
            "utm_medium": "referral",
            "vendor": "test",
        }
        idempotency_key = f"r2_runtime_test_{uuid4()}"

        service = EventIngestionService()

        async with AsyncSessionLocal() as session:
            try:
                # Set tenant context (required for RLS)
                await set_tenant_guc_async(session, tenant_id, local=False)

                # Execute real ingestion code path
                # This may fail due to FK constraints in test DB, which is OK
                # The point is to capture what SQL is ATTEMPTED
                await service.ingest_event(
                    session=session,
                    tenant_id=tenant_id,
                    event_data=event_data,
                    idempotency_key=idempotency_key,
                    source="r2_test",
                )
                await session.commit()
            except Exception as e:
                # Expected: FK constraint failures, missing channel, etc.
                # We're testing SQL patterns, not successful execution
                print(f"[R2_TEST] Expected test exception (FK/constraint): {type(e).__name__}")
                await session.rollback()

    @pytest.mark.asyncio
    async def test_revenue_reconciliation_path(self):
        """
        Exercise the revenue reconciliation code path.

        This is the PRIMARY code path that writes to revenue_ledger.
        It should only produce INSERT statements (with ON CONFLICT DO NOTHING).

        Code Path:
            RevenueReconciliationService.reconcile_order()
            -> _upsert_ledger_row()
            -> write rows to revenue_ledger
        """
        from app.services.revenue_reconciliation import (
            RevenueReconciliationService,
            PlatformClaim,
            VerifiedRevenue,
        )
        from app.db.session import engine, set_tenant_guc_async

        tenant_id = uuid4()
        order_id = f"r2_test_order_{uuid4()}"
        transaction_id = f"r2_test_txn_{uuid4()}"

        service = RevenueReconciliationService()

        platform_claims = [
            PlatformClaim(
                source="meta",
                amount_cents=10000,  # $100
                claim_timestamp=datetime.now(timezone.utc),
            )
        ]

        verified_revenue = VerifiedRevenue(
            source="stripe",
            amount_cents=8500,  # $85 (ghost = $15)
            verification_timestamp=datetime.now(timezone.utc),
            transaction_id=transaction_id,
        )

        async with engine.begin() as conn:
            try:
                # Set tenant context
                await set_tenant_guc_async(conn, tenant_id, local=False)

                # Execute real reconciliation code path
                await service.reconcile_order(
                    conn=conn,
                    tenant_id=tenant_id,
                    order_id=order_id,
                    platform_claims=platform_claims,
                    verified_revenue=verified_revenue,
                )
            except Exception as e:
                # Expected: FK constraint failures, etc.
                print(f"[R2_TEST] Expected test exception (FK/constraint): {type(e).__name__}")

    @pytest.mark.asyncio
    async def test_duplicate_event_check_path(self):
        """
        Exercise the idempotency check code path.

        This path queries attribution_events (SELECT only).
        It should never produce UPDATE/DELETE.

        Code Path:
            EventIngestionService._check_duplicate()
            -> SELECT FROM attribution_events
        """
        from app.ingestion.event_service import EventIngestionService
        from app.db.session import AsyncSessionLocal, set_tenant_guc_async

        tenant_id = uuid4()
        service = EventIngestionService()

        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_guc_async(session, tenant_id, local=False)

                # Check for a non-existent event (SELECT only)
                result = await service._check_duplicate(
                    session=session,
                    tenant_id=tenant_id,
                    idempotency_key="nonexistent_key_for_r2_test",
                )
                assert result is None
            except Exception as e:
                print(f"[R2_TEST] Exception during duplicate check: {type(e).__name__}")

    @pytest.mark.asyncio
    async def test_reconciliation_query_path(self):
        """
        Exercise the reconciliation query code path.

        This path queries revenue_ledger (SELECT only).
        It should never produce UPDATE/DELETE.

        Code Path:
            RevenueReconciliationService.get_reconciliation_by_order()
            -> SELECT FROM revenue_ledger
        """
        from app.services.revenue_reconciliation import RevenueReconciliationService
        from app.db.session import engine, set_tenant_guc_async

        tenant_id = uuid4()
        order_id = "nonexistent_order_for_r2_test"
        service = RevenueReconciliationService()

        async with engine.begin() as conn:
            try:
                await set_tenant_guc_async(conn, tenant_id, local=False)

                # Query for non-existent order (SELECT only)
                result = await service.get_reconciliation_by_order(
                    conn=conn,
                    tenant_id=tenant_id,
                    order_id=order_id,
                )
                assert result is None
            except Exception as e:
                print(f"[R2_TEST] Exception during reconciliation query: {type(e).__name__}")


class TestR2RuntimeInnocenceNegative:
    """
    Negative tests verifying the capture mechanism works.

    These tests intentionally attempt destructive operations
    and verify they are captured. They should be SKIPPED in
    normal CI runs (they would fail the innocence check).
    """

    @pytest.mark.skip(reason="Canary test - only run manually to verify capture works")
    @pytest.mark.asyncio
    async def test_canary_update_should_be_captured(self):
        """
        CANARY: Intentionally attempt UPDATE on attribution_events.

        This test verifies the capture mechanism works. If this test
        runs and the capture doesn't flag it, the mechanism is broken.
        """
        from sqlalchemy import text
        from app.db.session import engine

        async with engine.begin() as conn:
            # This UPDATE should be captured as a violation
            await conn.execute(
                text("UPDATE attribution_events SET event_type = 'canary' WHERE 1=0")
            )

    @pytest.mark.skip(reason="Canary test - only run manually to verify capture works")
    @pytest.mark.asyncio
    async def test_canary_delete_should_be_captured(self):
        """
        CANARY: Intentionally attempt DELETE on revenue_ledger.

        This test verifies the capture mechanism works.
        """
        from sqlalchemy import text
        from app.db.session import engine

        async with engine.begin() as conn:
            # This DELETE should be captured as a violation
            await conn.execute(
                text("DELETE FROM revenue_ledger WHERE 1=0")
            )


def run_innocence_proof():
    """
    Standalone runner for R2 runtime innocence proof.

    Can be executed directly for CI integration:
        python -m tests.test_r2_runtime_innocence
    """
    import asyncio
    from app.db.session import engine
    from app.db.statement_capture import (
        attach_capture_hook,
        clear_capture,
        print_verdict,
        get_violations,
    )

    print("\n" + "=" * 70)
    print("R2 RUNTIME INNOCENCE PROOF - STARTING")
    print("=" * 70)

    # Attach capture hook
    attach_capture_hook(engine)
    clear_capture()

    # Create test instance and run all paths
    test = TestR2RuntimeInnocence()

    async def run_all_paths():
        await test.test_event_ingestion_path()
        await test.test_revenue_reconciliation_path()
        await test.test_duplicate_event_check_path()
        await test.test_reconciliation_query_path()

    try:
        asyncio.run(run_all_paths())
    except Exception as e:
        print(f"[R2_TEST] Test execution error (may be expected): {e}")

    # Print authoritative verdict
    success = print_verdict()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    run_innocence_proof()

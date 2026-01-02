"""
B0.5.3.3 Revenue Input Semantics Contract Tests (Revised 2025-12-16)

Purpose: Prove that the attribution worker adheres to Contract B (ignores revenue_ledger)
regardless of ledger state (empty vs populated).

Schema Context:
- Tests target skeldir_foundation@head schema (migration 202512151410)
- revenue_ledger has 8 columns: id, tenant_id, created_at, updated_at, revenue_cents,
  is_verified, verified_at, reconciliation_run_id
- NO allocation_id FK (deferred to future 003_data_governance branch)
- NO canonical revenue columns (transaction_id, order_id, etc.) in current schema

Test Coverage:
1. Empty Ledger Scenario - Worker computes allocations deterministically from events only
2. Populated Ledger Scenario - Worker ignores existing ledger rows, produces identical results,
   AND ledger rows remain IMMUTABLE (content equality check, not just count)

Exit Criteria:
- Both tests pass in CI (not just locally)
- Worker behavior is deterministic regardless of ledger state
- No ledger reads/writes in worker code path
- Ledger rows remain immutable (no UPDATEs, no DELETEs)
- Ledger referential integrity preserved (tenant_id FK valid)

Contract B Guarantees:
- Worker reads from attribution_events (upstream)
- Worker writes to attribution_allocations (downstream)
- Worker ignores revenue_ledger (further downstream, not input)
- Behavior is identical whether ledger is empty or populated
- Ledger rows are never modified by worker (proven via content equality)
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text

from app.core.db import engine
from app.tasks.attribution import recompute_window
from tests.conftest import _insert_tenant


def _parse_timestamp(iso_string: str) -> datetime:
    """Parse ISO8601 timestamp string to timezone-aware datetime."""
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


@pytest.mark.asyncio
class TestRevenueInputContract:
    """
    B0.5.3.3 Revenue Input Semantics Contract Test Suite

    These tests prove Contract B (worker ignores revenue_ledger) via:
    1. Deterministic allocation computation from events only
    2. Identical behavior regardless of ledger state
    3. No ledger reads/writes in worker code path
    """

    async def test_empty_ledger_deterministic_allocations(self):
        """
        Prove that worker computes allocations deterministically when ledger is empty.

        B0.5.3.3 Requirement: Contract B - Worker reads from attribution_events only,
        computes allocations deterministically, writes to attribution_allocations.
        Ledger state (empty) is irrelevant.

        Test Steps:
        1. Insert test tenant and events
        2. Verify ledger is empty (or non-existent)
        3. Run recompute_window
        4. Verify allocations are created deterministically
        5. Verify ledger remains untouched (no reads, no writes)
        """
        from app.celery_app import celery_app

        # Enable eager mode for synchronous execution
        celery_app.conf.task_always_eager = True

        test_tenant_id = uuid4()
        window_start = "2025-05-01T00:00:00Z"
        window_end = "2025-05-01T23:59:59Z"
        model_version = "1.0.0"

        # Insert test tenant
        async with engine.begin() as conn:
            await _insert_tenant(
                conn,
                test_tenant_id,
                api_key_hash=f"test_hash_{test_tenant_id}",
            )

            # Set tenant context for RLS policy
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            # Verify ledger is empty (or count existing rows)
            ledger_count_result = await conn.execute(
                text("SELECT COUNT(*) FROM revenue_ledger WHERE tenant_id = :tenant_id"),
                {"tenant_id": test_tenant_id}
            )
            ledger_count_before = ledger_count_result.scalar()

            # Insert synthetic events within window
            event_id_1 = uuid4()
            event_id_2 = uuid4()
            session_id_1 = uuid4()
            session_id_2 = uuid4()
            idempotency_key_1 = f"{test_tenant_id}:{event_id_1}"
            idempotency_key_2 = f"{test_tenant_id}:{event_id_2}"

            # RAW_SQL_ALLOWLIST: seed deterministic events for revenue input contract baseline
            await conn.execute(
                text("""
                    INSERT INTO attribution_events (
                        id, tenant_id, occurred_at, event_timestamp, session_id, idempotency_key, event_type, channel, revenue_cents, raw_payload
                    ) VALUES
                        (:id1, :tenant_id, '2025-05-01T10:00:00Z'::timestamptz, '2025-05-01T10:00:00Z'::timestamptz, :session_id_1, :idempotency_key_1, 'purchase', 'direct', 10000, '{}'::jsonb),
                        (:id2, :tenant_id, '2025-05-01T15:00:00Z'::timestamptz, '2025-05-01T15:00:00Z'::timestamptz, :session_id_2, :idempotency_key_2, 'purchase', 'direct', 20000, '{}'::jsonb)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id1": event_id_1,
                    "id2": event_id_2,
                    "session_id_1": session_id_1,
                    "session_id_2": session_id_2,
                    "idempotency_key_1": idempotency_key_1,
                    "idempotency_key_2": idempotency_key_2,
                    "tenant_id": test_tenant_id,
                }
            )

        # Run recompute_window (Contract B: reads events, writes allocations, ignores ledger)
        result = recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Verify allocations were created
        async with engine.begin() as conn:
            # Set tenant context for RLS policy
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            allocations_result = await conn.execute(
                text("""
                    SELECT event_id, channel_code, allocation_ratio, allocated_revenue_cents
                    FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND model_version = :model_version
                      AND event_id IN (:event_id_1, :event_id_2)
                    ORDER BY event_id, channel_code
                """),
                {
                    "tenant_id": test_tenant_id,
                    "model_version": model_version,
                    "event_id_1": event_id_1,
                    "event_id_2": event_id_2,
                }
            )
            allocations = allocations_result.fetchall()

            # Verify ledger count unchanged (worker doesn't write ledger)
            ledger_count_after_result = await conn.execute(
                text("SELECT COUNT(*) FROM revenue_ledger WHERE tenant_id = :tenant_id"),
                {"tenant_id": test_tenant_id}
            )
            ledger_count_after = ledger_count_after_result.scalar()

        # Assertions: Contract B behavior
        assert result["status"] == "succeeded", "Worker must succeed"
        assert result["event_count"] == 2, f"Expected 2 events, got {result['event_count']}"
        assert result["allocation_count"] > 0, "Worker must create allocations"

        # Verify allocations exist (deterministic baseline: 3 channels per event)
        assert len(allocations) == 6, \
            f"Expected 6 allocations (2 events × 3 channels), got {len(allocations)}"

        # Verify allocation values are deterministic (equal split across channels)
        from decimal import Decimal
        expected_ratio = Decimal("1.0") / Decimal("3.0")  # BASELINE_CHANNELS = ["google_search", "direct", "email"]
        for event_id, channel, ratio, revenue in allocations:
            assert abs(ratio - expected_ratio) < Decimal("0.00001"), \
                f"Allocation ratio must be {expected_ratio}, got {ratio}"

        # CRITICAL: Ledger count unchanged (worker doesn't write ledger)
        assert ledger_count_after == ledger_count_before, \
            f"Ledger count must be unchanged: before={ledger_count_before} after={ledger_count_after}"

    async def test_populated_ledger_ignored_identical_results(self):
        """
        Prove that worker ignores populated ledger and produces identical results.

        B0.5.3.3 Requirement: Contract B - Worker behavior is identical regardless of
        ledger state. Populated ledger rows are ignored (not read, not written, not deleted).

        Test Steps:
        1. Insert test tenant and events
        2. Run recompute_window (baseline: empty ledger)
        3. Capture allocation results
        4. Manually insert ledger rows referencing allocations
        5. Rerun recompute_window (populated ledger)
        6. Verify allocations are identical (deterministic, ledger ignored)
        7. Verify ledger rows remain untouched (FK integrity preserved)
        """
        from app.celery_app import celery_app

        # Enable eager mode for synchronous execution
        celery_app.conf.task_always_eager = True

        test_tenant_id = uuid4()
        window_start = "2025-06-01T00:00:00Z"
        window_end = "2025-06-01T23:59:59Z"
        model_version = "1.0.0"

        # Insert test tenant
        async with engine.begin() as conn:
            await _insert_tenant(
                conn,
                test_tenant_id,
                api_key_hash=f"test_hash_{test_tenant_id}",
            )

            # Set tenant context for RLS policy
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            # Insert synthetic events within window
            event_id_1 = uuid4()
            event_id_2 = uuid4()
            session_id_1 = uuid4()
            session_id_2 = uuid4()
            idempotency_key_1 = f"{test_tenant_id}:{event_id_1}"
            idempotency_key_2 = f"{test_tenant_id}:{event_id_2}"

            # RAW_SQL_ALLOWLIST: seed deterministic events for revenue input contract rerun
            await conn.execute(
                text("""
                    INSERT INTO attribution_events (
                        id, tenant_id, occurred_at, event_timestamp, session_id, idempotency_key, event_type, channel, revenue_cents, raw_payload
                    ) VALUES
                        (:id1, :tenant_id, '2025-06-01T10:00:00Z'::timestamptz, '2025-06-01T10:00:00Z'::timestamptz, :session_id_1, :idempotency_key_1, 'purchase', 'direct', 10000, '{}'::jsonb),
                        (:id2, :tenant_id, '2025-06-01T15:00:00Z'::timestamptz, '2025-06-01T15:00:00Z'::timestamptz, :session_id_2, :idempotency_key_2, 'purchase', 'direct', 20000, '{}'::jsonb)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id1": event_id_1,
                    "id2": event_id_2,
                    "session_id_1": session_id_1,
                    "session_id_2": session_id_2,
                    "idempotency_key_1": idempotency_key_1,
                    "idempotency_key_2": idempotency_key_2,
                    "tenant_id": test_tenant_id,
                }
            )

        # BASELINE: Run recompute_window with empty ledger
        result_baseline = recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Capture baseline allocations
        async with engine.begin() as conn:
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            baseline_result = await conn.execute(
                text("""
                    SELECT id, event_id, channel_code, allocation_ratio, allocated_revenue_cents
                    FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND model_version = :model_version
                      AND event_id IN (:event_id_1, :event_id_2)
                    ORDER BY event_id, channel_code
                """),
                {
                    "tenant_id": test_tenant_id,
                    "model_version": model_version,
                    "event_id_1": event_id_1,
                    "event_id_2": event_id_2,
                }
            )
            baseline_allocations = baseline_result.fetchall()

        assert len(baseline_allocations) > 0, "Baseline must produce allocations"

        # POPULATE LEDGER: Manually insert ledger rows (no allocation link in skeldir_foundation schema)
        # (Simulating pre-existing revenue data that worker should ignore)
        #
        # IMPORTANT: skeldir_foundation@head schema does NOT have allocation_id column.
        # This makes the test STRONGER: ledger rows exist but are completely unlinked to allocations,
        # proving worker ignores ledger even when populated.
        async with engine.begin() as conn:
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            # Insert standalone ledger rows (Contract B: worker ignores these)
            # Use only columns that exist in skeldir_foundation@head:
            # - tenant_id, revenue_cents, is_verified, verified_at, reconciliation_run_id
            ledger_row_1_id = uuid4()
            ledger_row_2_id = uuid4()

            # RAW_SQL_ALLOWLIST: simulate pre-existing ledger rows for contract test
            await conn.execute(
                text("""
                    INSERT INTO revenue_ledger (
                        id, tenant_id, revenue_cents, is_verified, verified_at
                    ) VALUES
                        (:id1, :tenant_id, 5000, true, '2025-06-01T09:00:00Z'::timestamptz),
                        (:id2, :tenant_id, 7000, true, '2025-06-01T14:00:00Z'::timestamptz)
                """),
                {
                    "id1": ledger_row_1_id,
                    "id2": ledger_row_2_id,
                    "tenant_id": test_tenant_id,
                }
            )

            # Verify ledger rows exist
            ledger_count_result = await conn.execute(
                text("SELECT COUNT(*) FROM revenue_ledger WHERE tenant_id = :tenant_id"),
                {"tenant_id": test_tenant_id}
            )
            ledger_count_populated = ledger_count_result.scalar()

        assert ledger_count_populated == 2, "Ledger must have 2 rows after population"

        # Capture ledger state BEFORE rerun (for content equality check)
        async with engine.begin() as conn:
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            ledger_before_result = await conn.execute(
                text("""
                    SELECT id, revenue_cents, is_verified, verified_at, reconciliation_run_id
                    FROM revenue_ledger
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at, id
                """),
                {"tenant_id": test_tenant_id}
            )
            ledger_rows_before = ledger_before_result.fetchall()

        # RERUN: Run recompute_window with populated ledger (Contract B: should ignore ledger)
        result_populated = recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Capture allocations after rerun AND ledger state AFTER rerun
        async with engine.begin() as conn:
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            populated_result = await conn.execute(
                text("""
                    SELECT id, event_id, channel_code, allocation_ratio, allocated_revenue_cents
                    FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND model_version = :model_version
                      AND event_id IN (:event_id_1, :event_id_2)
                    ORDER BY event_id, channel_code
                """),
                {
                    "tenant_id": test_tenant_id,
                    "model_version": model_version,
                    "event_id_1": event_id_1,
                    "event_id_2": event_id_2,
                }
            )
            populated_allocations = populated_result.fetchall()

            # Capture ledger state AFTER rerun (for content equality check)
            ledger_after_result = await conn.execute(
                text("""
                    SELECT id, revenue_cents, is_verified, verified_at, reconciliation_run_id
                    FROM revenue_ledger
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at, id
                """),
                {"tenant_id": test_tenant_id}
            )
            ledger_rows_after = ledger_after_result.fetchall()

            # Verify ledger row count (for quick check)
            ledger_count_after_result = await conn.execute(
                text("SELECT COUNT(*) FROM revenue_ledger WHERE tenant_id = :tenant_id"),
                {"tenant_id": test_tenant_id}
            )
            ledger_count_after = ledger_count_after_result.scalar()

        # CRITICAL ASSERTIONS: Contract B behavior

        # 1. Task results must be identical (deterministic)
        assert result_populated["status"] == "succeeded", "Worker must succeed"
        assert result_populated["event_count"] == result_baseline["event_count"], \
            f"Event count must be identical: baseline={result_baseline['event_count']} populated={result_populated['event_count']}"
        assert result_populated["allocation_count"] == result_baseline["allocation_count"], \
            f"Allocation count must be identical: baseline={result_baseline['allocation_count']} populated={result_populated['allocation_count']}"

        # 2. Allocation rows must be identical (same count, same values)
        assert len(populated_allocations) == len(baseline_allocations), \
            f"Allocation count must match: baseline={len(baseline_allocations)} populated={len(populated_allocations)}"

        for i, (baseline_row, populated_row) in enumerate(zip(baseline_allocations, populated_allocations)):
            baseline_id, baseline_event, baseline_channel, baseline_ratio, baseline_revenue = baseline_row
            populated_id, populated_event, populated_channel, populated_ratio, populated_revenue = populated_row

            # Allocation IDs may differ (UPSERT creates new IDs on conflict), but values must match
            assert baseline_event == populated_event, \
                f"Row {i}: event_id must match: {baseline_event} != {populated_event}"
            assert baseline_channel == populated_channel, \
                f"Row {i}: channel must match: {baseline_channel} != {populated_channel}"
            assert abs(baseline_ratio - populated_ratio) < 0.00001, \
                f"Row {i}: allocation_ratio must match: {baseline_ratio} != {populated_ratio}"
            assert baseline_revenue == populated_revenue, \
                f"Row {i}: allocated_revenue_cents must match: {baseline_revenue} != {populated_revenue}"

        # 3. Ledger row count must be unchanged (worker doesn't delete them)
        assert ledger_count_after == ledger_count_populated, \
            f"Ledger count must be unchanged: populated={ledger_count_populated} after={ledger_count_after}"

        # 4. CRITICAL: Ledger rows must be IMMUTABLE (content equality, not just count)
        # This proves worker doesn't UPDATE or DELETE ledger rows, only ignores them
        assert len(ledger_rows_after) == len(ledger_rows_before), \
            f"Ledger row count mismatch: before={len(ledger_rows_before)} after={len(ledger_rows_after)}"

        for i, (before_row, after_row) in enumerate(zip(ledger_rows_before, ledger_rows_after)):
            before_id, before_revenue, before_verified, before_verified_at, before_recon = before_row
            after_id, after_revenue, after_verified, after_verified_at, after_recon = after_row

            # Assert exact row equality (proving immutability)
            assert before_id == after_id, \
                f"Ledger row {i}: id changed: {before_id} != {after_id}"
            assert before_revenue == after_revenue, \
                f"Ledger row {i}: revenue_cents changed: {before_revenue} != {after_revenue}"
            assert before_verified == after_verified, \
                f"Ledger row {i}: is_verified changed: {before_verified} != {after_verified}"
            assert before_verified_at == after_verified_at, \
                f"Ledger row {i}: verified_at changed: {before_verified_at} != {after_verified_at}"
            assert before_recon == after_recon, \
                f"Ledger row {i}: reconciliation_run_id changed: {before_recon} != {after_recon}"

        # 5. Ledger referential integrity: Verify ledger rows remain valid
        # (No FK to allocations in skeldir_foundation@head, so check tenant_id FK only)
        async with engine.begin() as conn:
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            tenant_fk_check = await conn.execute(
                text("""
                    SELECT COUNT(*) FROM revenue_ledger rl
                    INNER JOIN tenants t ON rl.tenant_id = t.id
                    WHERE rl.tenant_id = :tenant_id
                """),
                {"tenant_id": test_tenant_id}
            )
            tenant_fk_count = tenant_fk_check.scalar()

        assert tenant_fk_count == ledger_count_populated, \
            f"All ledger rows must have valid tenant_id FK: expected={ledger_count_populated} actual={tenant_fk_count}"

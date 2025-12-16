"""
B0.5.3.2 Window-Scoped Idempotency Tests

Purpose: Prove that window-scoped idempotency enforcement prevents duplicate
derived outputs when rerunning the same attribution window.

Test Coverage:
1. Job Identity Uniqueness - Same window creates one job row, increments run_count
2. Derived Output Repeatability - Rerun produces identical allocations (no duplicates)

Exit Criteria:
- All tests pass in CI (not just locally)
- Migration applies cleanly (attribution_recompute_jobs table exists)
- UNIQUE constraint prevents duplicate job identities
- Rerun behavior is deterministic (same rows + same values)

Failure Mode Prevention:
- Prevents "Window Re-Run Produces Duplicates" flagged in Landscape Report
- Ensures same window → identical derived outputs (provable via SQL queries)
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import text

from app.core.db import engine
from app.tasks.attribution import recompute_window


def _parse_timestamp(iso_string: str) -> datetime:
    """Parse ISO8601 timestamp string to timezone-aware datetime."""
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


@pytest.mark.asyncio
class TestWindowIdempotency:
    """
    B0.5.3.2 Window-Scoped Idempotency Test Suite

    These tests prove window-scoped idempotency enforcement via:
    1. attribution_recompute_jobs table with UNIQUE constraint
    2. Deterministic baseline allocation logic
    3. Event-scoped overwrite strategy (inherited from B0.3)
    """

    async def test_job_identity_uniqueness(self):
        """
        Prove that scheduling/executing the same window twice results in:
        - Exactly one attribution_recompute_jobs row for that identity
        - run_count == 2 (monotonic increment)
        - Deterministic status transitions

        B0.5.3.2 Requirement: Job tracking mechanism with explicit UNIQUE constraint
        prevents duplicate window execution rows.
        """
        from app.celery_app import celery_app

        # Enable eager mode for synchronous execution
        celery_app.conf.task_always_eager = True

        test_tenant_id = uuid4()
        window_start = "2025-01-01T00:00:00Z"
        window_end = "2025-01-01T23:59:59Z"
        model_version = "1.0.0"

        # Insert test tenant
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
                {"id": test_tenant_id, "name": f"Test Tenant {test_tenant_id}"}
            )

        # First execution - creates job identity
        result1 = recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Query job row after first execution
        async with engine.begin() as conn:
            result_first = await conn.execute(
                text("""
                    SELECT id, run_count, status
                    FROM attribution_recompute_jobs
                    WHERE tenant_id = :tenant_id
                      AND window_start = :window_start
                      AND window_end = :window_end
                      AND model_version = :model_version
                """),
                {
                    "tenant_id": test_tenant_id,
                    "window_start": _parse_timestamp(window_start),
                    "window_end": _parse_timestamp(window_end),
                    "model_version": model_version,
                }
            )
            row_first = result_first.fetchone()

        assert row_first is not None, "Job identity row must exist after first execution"
        job_id_first = row_first[0]
        run_count_first = row_first[1]
        status_first = row_first[2]

        assert run_count_first == 1, f"First execution must have run_count=1, got {run_count_first}"
        assert status_first == "succeeded", f"First execution must succeed, got status={status_first}"

        # Second execution - reuses job identity (idempotency proof)
        result2 = recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Query job row after second execution
        async with engine.begin() as conn:
            result_second = await conn.execute(
                text("""
                    SELECT id, run_count, status
                    FROM attribution_recompute_jobs
                    WHERE tenant_id = :tenant_id
                      AND window_start = :window_start
                      AND window_end = :window_end
                      AND model_version = :model_version
                """),
                {
                    "tenant_id": test_tenant_id,
                    "window_start": _parse_timestamp(window_start),
                    "window_end": _parse_timestamp(window_end),
                    "model_version": model_version,
                }
            )
            row_second = result_second.fetchone()

            # Count total job rows for this window identity
            count_result = await conn.execute(
                text("""
                    SELECT COUNT(*) FROM attribution_recompute_jobs
                    WHERE tenant_id = :tenant_id
                      AND window_start = :window_start
                      AND window_end = :window_end
                      AND model_version = :model_version
                """),
                {
                    "tenant_id": test_tenant_id,
                    "window_start": _parse_timestamp(window_start),
                    "window_end": _parse_timestamp(window_end),
                    "model_version": model_version,
                }
            )
            job_count = count_result.scalar()

        assert row_second is not None, "Job identity row must still exist after second execution"
        job_id_second = row_second[0]
        run_count_second = row_second[1]
        status_second = row_second[2]

        # CRITICAL IDEMPOTENCY ASSERTION: Only one job row exists for this window
        assert job_count == 1, f"UNIQUE constraint violated: expected 1 job row, got {job_count}"

        # Job ID must be the same (reused, not created new)
        assert job_id_second == job_id_first, \
            f"Job ID must be reused (idempotent), got first={job_id_first} second={job_id_second}"

        # run_count must increment (monotonic observability metric)
        assert run_count_second == 2, \
            f"Second execution must have run_count=2, got {run_count_second}"

        # Status must be succeeded (deterministic outcome)
        assert status_second == "succeeded", \
            f"Second execution must succeed, got status={status_second}"

        # Task results must include correct metadata
        assert result1["run_count"] == 1, "First task result must report run_count=1"
        assert result2["run_count"] == 2, "Second task result must report run_count=2"

    async def test_derived_output_repeatability(self):
        """
        Prove that rerunning the same window produces identical derived outputs:
        - Insert synthetic events into attribution_events (within window)
        - Run recompute_window twice in eager mode
        - Assert allocations set after run #2 equals run #1 (same rows + same values)
        - Assert row count does not increase on rerun (no duplicates)

        B0.5.3.2 Requirement: Deterministic baseline allocation logic + event-scoped
        overwrite strategy must prevent duplicates and ensure stability.
        """
        from app.celery_app import celery_app

        # Enable eager mode for synchronous execution
        celery_app.conf.task_always_eager = True

        test_tenant_id = uuid4()
        window_start = "2025-02-01T00:00:00Z"
        window_end = "2025-02-01T23:59:59Z"
        model_version = "1.0.0"

        # Insert test tenant
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
                {"id": test_tenant_id, "name": f"Test Tenant {test_tenant_id}"}
            )

            # Insert synthetic events within window (deterministic test data)
            event_id_1 = uuid4()
            event_id_2 = uuid4()

            # Set tenant context for RLS policy
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            await conn.execute(
                text("""
                    INSERT INTO attribution_events (
                        id, tenant_id, occurred_at, revenue_cents, raw_payload
                    ) VALUES
                        (:id1, :tenant_id, '2025-02-01T10:00:00Z'::timestamptz, 10000, '{}'::jsonb),
                        (:id2, :tenant_id, '2025-02-01T15:00:00Z'::timestamptz, 20000, '{}'::jsonb)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id1": event_id_1,
                    "id2": event_id_2,
                    "tenant_id": test_tenant_id,
                }
            )

        # First execution - creates allocations
        result1 = recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Query allocations after first execution
        async with engine.begin() as conn:
            # Set tenant context for RLS policy
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            result_first = await conn.execute(
                text("""
                    SELECT event_id, channel, allocation_ratio, allocated_revenue_cents
                    FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND model_version = :model_version
                      AND event_id IN (:event_id_1, :event_id_2)
                    ORDER BY event_id, channel
                """),
                {
                    "tenant_id": test_tenant_id,
                    "model_version": model_version,
                    "event_id_1": event_id_1,
                    "event_id_2": event_id_2,
                }
            )
            allocations_first = result_first.fetchall()

            count_first_result = await conn.execute(
                text("""
                    SELECT COUNT(*) FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND model_version = :model_version
                      AND event_id IN (:event_id_1, :event_id_2)
                """),
                {
                    "tenant_id": test_tenant_id,
                    "model_version": model_version,
                    "event_id_1": event_id_1,
                    "event_id_2": event_id_2,
                }
            )
            count_first = count_first_result.scalar()

        # Verify first execution produced allocations
        assert len(allocations_first) > 0, "First execution must produce allocations"
        assert count_first > 0, "First execution must have non-zero allocation count"

        # Second execution - should produce IDENTICAL allocations (idempotency proof)
        result2 = recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Query allocations after second execution
        async with engine.begin() as conn:
            # Set tenant context for RLS policy
            await conn.execute(
                text(f"SET LOCAL app.current_tenant_id = '{test_tenant_id}'")
            )

            result_second = await conn.execute(
                text("""
                    SELECT event_id, channel, allocation_ratio, allocated_revenue_cents
                    FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND model_version = :model_version
                      AND event_id IN (:event_id_1, :event_id_2)
                    ORDER BY event_id, channel
                """),
                {
                    "tenant_id": test_tenant_id,
                    "model_version": model_version,
                    "event_id_1": event_id_1,
                    "event_id_2": event_id_2,
                }
            )
            allocations_second = result_second.fetchall()

            count_second_result = await conn.execute(
                text("""
                    SELECT COUNT(*) FROM attribution_allocations
                    WHERE tenant_id = :tenant_id
                      AND model_version = :model_version
                      AND event_id IN (:event_id_1, :event_id_2)
                """),
                {
                    "tenant_id": test_tenant_id,
                    "model_version": model_version,
                    "event_id_1": event_id_1,
                    "event_id_2": event_id_2,
                }
            )
            count_second = count_second_result.scalar()

        # CRITICAL REPEATABILITY ASSERTIONS

        # Row count must NOT increase (no duplicates created on rerun)
        assert count_second == count_first, \
            f"Allocation count must be stable: first={count_first} second={count_second}"

        # Allocation rows must be IDENTICAL (same event_id, channel, values)
        assert len(allocations_second) == len(allocations_first), \
            f"Allocation row count must match: first={len(allocations_first)} second={len(allocations_second)}"

        for i, (row_first, row_second) in enumerate(zip(allocations_first, allocations_second)):
            event_id_first, channel_first, ratio_first, revenue_first = row_first
            event_id_second, channel_second, ratio_second, revenue_second = row_second

            assert event_id_first == event_id_second, \
                f"Row {i}: event_id mismatch: {event_id_first} != {event_id_second}"
            assert channel_first == channel_second, \
                f"Row {i}: channel mismatch: {channel_first} != {channel_second}"
            assert abs(ratio_first - ratio_second) < 0.00001, \
                f"Row {i}: allocation_ratio mismatch: {ratio_first} != {ratio_second}"
            assert revenue_first == revenue_second, \
                f"Row {i}: allocated_revenue_cents mismatch: {revenue_first} != {revenue_second}"

        # Task metadata must match
        assert result1["event_count"] == result2["event_count"], \
            f"Event count must be stable: first={result1['event_count']} second={result2['event_count']}"
        assert result1["allocation_count"] == result2["allocation_count"], \
            f"Allocation count must be stable: first={result1['allocation_count']} second={result2['allocation_count']}"

    async def test_window_identity_unique_constraint(self):
        """
        Prove that the UNIQUE constraint on (tenant_id, window_start, window_end, model_version)
        exists and is enforced at the database level.

        B0.5.3.2 Requirement: Schema artifact exists + is enforced (not just convention).
        """
        from app.celery_app import celery_app

        # Enable eager mode
        celery_app.conf.task_always_eager = True

        test_tenant_id = uuid4()
        window_start = "2025-03-01T00:00:00Z"
        window_end = "2025-03-01T23:59:59Z"
        model_version = "1.0.0"

        # Insert test tenant
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
                {"id": test_tenant_id, "name": f"Test Tenant {test_tenant_id}"}
            )

        # First execution - establishes job identity
        recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
        ).get()

        # Query job identity
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id FROM attribution_recompute_jobs
                    WHERE tenant_id = :tenant_id
                      AND window_start = :window_start
                      AND window_end = :window_end
                      AND model_version = :model_version
                """),
                {
                    "tenant_id": test_tenant_id,
                    "window_start": _parse_timestamp(window_start),
                    "window_end": _parse_timestamp(window_end),
                    "model_version": model_version,
                }
            )
            job_row = result.fetchone()

        assert job_row is not None, "Job identity row must exist after first execution"

        # Verify index/constraint exists (schema validation)
        async with engine.begin() as conn:
            constraint_result = await conn.execute(
                text("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'attribution_recompute_jobs'
                      AND indexname = 'idx_attribution_recompute_jobs_window_identity'
                """)
            )
            constraint_row = constraint_result.fetchone()

        assert constraint_row is not None, \
            "UNIQUE index idx_attribution_recompute_jobs_window_identity must exist"

        indexdef = constraint_row[1]
        assert "UNIQUE" in indexdef, "Index must be UNIQUE"
        assert "tenant_id" in indexdef, "Index must include tenant_id"
        assert "window_start" in indexdef, "Index must include window_start"
        assert "window_end" in indexdef, "Index must include window_end"
        assert "model_version" in indexdef, "Index must include model_version"

    async def test_different_model_versions_allowed(self):
        """
        Prove that different model versions for the same window create separate job identities.

        B0.5.3.2 Requirement: model_version is part of window identity for A/B testing support.
        """
        from app.celery_app import celery_app

        # Enable eager mode
        celery_app.conf.task_always_eager = True

        test_tenant_id = uuid4()
        window_start = "2025-04-01T00:00:00Z"
        window_end = "2025-04-01T23:59:59Z"

        # Insert test tenant
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
                {"id": test_tenant_id, "name": f"Test Tenant {test_tenant_id}"}
            )

        # Execute with model_version 1.0.0
        recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version="1.0.0",
        ).get()

        # Execute with model_version 2.0.0 (same window, different model)
        recompute_window.delay(
            tenant_id=test_tenant_id,
            window_start=window_start,
            window_end=window_end,
            model_version="2.0.0",
        ).get()

        # Query job identities - should have TWO rows (one per model version)
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT model_version, run_count
                    FROM attribution_recompute_jobs
                    WHERE tenant_id = :tenant_id
                      AND window_start = :window_start
                      AND window_end = :window_end
                    ORDER BY model_version
                """),
                {
                    "tenant_id": test_tenant_id,
                    "window_start": _parse_timestamp(window_start),
                    "window_end": _parse_timestamp(window_end),
                }
            )
            rows = result.fetchall()

        assert len(rows) == 2, f"Expected 2 job rows (one per model version), got {len(rows)}"

        model_v1, run_count_v1 = rows[0]
        model_v2, run_count_v2 = rows[1]

        assert model_v1 == "1.0.0", f"First row must be model_version=1.0.0, got {model_v1}"
        assert model_v2 == "2.0.0", f"Second row must be model_version=2.0.0, got {model_v2}"
        assert run_count_v1 == 1, f"Model 1.0.0 must have run_count=1, got {run_count_v1}"
        assert run_count_v2 == 1, f"Model 2.0.0 must have run_count=1, got {run_count_v2}"

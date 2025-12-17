"""
B0.5.3.4 Worker-Scoped Tenant Isolation & DLQ Proofs

Objective: Empirically prove that attribution worker executions enforce tenant
isolation (RLS) and produce idempotent, retry-safe outputs even under
concurrency, and that missing tenant context is captured in the worker DLQ with
correlation metadata.
"""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.celery_app import celery_app
from app.core.db import engine
from app.tasks.attribution import recompute_window


async def _insert_tenant(conn, tenant_id):
    await conn.execute(
        text("INSERT INTO tenants (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
        {"id": tenant_id, "name": f"Test Tenant {tenant_id}"},
    )


async def _insert_events(conn, tenant_id, events):
    # RLS requires the tenant GUC to be set for writes.
    await conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    await conn.execute(
        text(
            """
            INSERT INTO attribution_events (id, tenant_id, occurred_at, revenue_cents, raw_payload)
            VALUES
                (:id1, :tenant_id, :ts1::timestamptz, :rev1, '{}'::jsonb),
                (:id2, :tenant_id, :ts2::timestamptz, :rev2, '{}'::jsonb)
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id1": events[0][0],
            "id2": events[1][0],
            "tenant_id": tenant_id,
            "ts1": events[0][1],
            "ts2": events[1][1],
            "rev1": events[0][2],
            "rev2": events[1][2],
        },
    )


def _parse_uuid(value):
    return UUID(str(value))


@pytest.mark.asyncio
class TestWorkerTenantIsolation:
    async def test_allocations_and_jobs_are_tenant_scoped(self):
        """
        Gate A: allocations and job rows are created only for the correct tenant
        and are invisible across tenant contexts (RLS enforced in worker path).
        """
        original_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        tenant_a = uuid4()
        tenant_b = uuid4()
        window_start = "2025-06-01T00:00:00Z"
        window_end = "2025-06-02T00:00:00Z"

        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_a)
            await _insert_tenant(conn, tenant_b)
            await _insert_events(
                conn,
                tenant_a,
                [
                    (uuid4(), "2025-06-01T10:00:00Z", 10000),
                    (uuid4(), "2025-06-01T12:00:00Z", 20000),
                ],
            )
            await _insert_events(
                conn,
                tenant_b,
                [
                    (uuid4(), "2025-06-01T14:00:00Z", 30000),
                    (uuid4(), "2025-06-01T16:00:00Z", 40000),
                ],
            )

        try:
            # Execute worker tasks for both tenants
            result_a = recompute_window.delay(
                tenant_id=tenant_a,
                window_start=window_start,
                window_end=window_end,
                correlation_id=str(uuid4()),
            ).get()
            result_b = recompute_window.delay(
                tenant_id=tenant_b,
                window_start=window_start,
                window_end=window_end,
                correlation_id=str(uuid4()),
            ).get()

            assert result_a["status"] == "succeeded"
            assert result_b["status"] == "succeeded"

            # Tenant A visibility
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_a)},
                )
                alloc_a = await conn.execute(
                    text(
                        """
                        SELECT event_id, channel, allocation_ratio, allocated_revenue_cents
                        FROM attribution_allocations
                        WHERE tenant_id = :tenant_id
                        ORDER BY event_id, channel
                        """
                    ),
                    {"tenant_id": tenant_a},
                )
                alloc_rows_a = alloc_a.fetchall()

                jobs_a = await conn.execute(
                    text(
                        """
                        SELECT id, run_count, status
                        FROM attribution_recompute_jobs
                        WHERE tenant_id = :tenant_id
                    """
                    ),
                    {"tenant_id": tenant_a},
                )
                job_rows_a = jobs_a.fetchall()

            assert len(alloc_rows_a) == 6, "Tenant A should have 6 allocations (2 events x 3 channels)"
            assert all(row[0] is not None for row in alloc_rows_a), "event_id must never be NULL"
            assert len(job_rows_a) == 1, "Tenant A should have one recompute job row"
            assert job_rows_a[0][1] == 1 and job_rows_a[0][2] == "succeeded"

            # Tenant B cannot see Tenant A data under RLS
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_b)},
                )
                cross_alloc = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM attribution_allocations
                        WHERE tenant_id = :tenant_a
                    """
                    ),
                    {"tenant_a": tenant_a},
                )
                cross_jobs = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM attribution_recompute_jobs
                        WHERE tenant_id = :tenant_a
                    """
                    ),
                    {"tenant_a": tenant_a},
                )

            assert cross_alloc.scalar() == 0, "RLS should prevent cross-tenant allocation visibility"
            assert cross_jobs.scalar() == 0, "RLS should prevent cross-tenant job visibility"
        finally:
            celery_app.conf.task_always_eager = original_eager

    async def test_retry_idempotent_and_event_id_non_null(self):
        """
        Gate A/H3: retries do not duplicate allocations and never write NULL event_ids.
        """
        original_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        tenant_id = uuid4()
        window_start = "2025-06-05T00:00:00Z"
        window_end = "2025-06-06T00:00:00Z"
        model_version = "1.0.0"

        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id)
            await _insert_events(
                conn,
                tenant_id,
                [
                    (uuid4(), "2025-06-05T10:00:00Z", 15000),
                    (uuid4(), "2025-06-05T12:00:00Z", 25000),
                ],
            )

        try:
            recompute_window.delay(
                tenant_id=tenant_id,
                window_start=window_start,
                window_end=window_end,
                model_version=model_version,
            ).get()
            recompute_window.delay(
                tenant_id=tenant_id,
                window_start=window_start,
                window_end=window_end,
                model_version=model_version,
            ).get()

            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )
                total_allocations = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM attribution_allocations
                        WHERE tenant_id = :tenant_id AND model_version = :model_version
                        """
                    ),
                    {"tenant_id": tenant_id, "model_version": model_version},
                )
                distinct_allocations = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM (
                            SELECT DISTINCT event_id, channel, model_version
                            FROM attribution_allocations
                            WHERE tenant_id = :tenant_id AND model_version = :model_version
                        ) AS distinct_rows
                        """
                    ),
                    {"tenant_id": tenant_id, "model_version": model_version},
                )
                null_events = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM attribution_allocations
                        WHERE tenant_id = :tenant_id AND model_version = :model_version AND event_id IS NULL
                        """
                    ),
                    {"tenant_id": tenant_id, "model_version": model_version},
                )
                job_row = await conn.execute(
                    text(
                        """
                        SELECT run_count FROM attribution_recompute_jobs
                        WHERE tenant_id = :tenant_id
                        """
                    ),
                    {"tenant_id": tenant_id},
                )

            expected_allocations = 2 * 3  # 2 events x 3 baseline channels
            assert total_allocations.scalar() == expected_allocations
            assert distinct_allocations.scalar() == expected_allocations
            assert null_events.scalar() == 0, "event_id must never be NULL even on retries"
            assert job_row.scalar() == 2, "run_count should reflect two executions"
        finally:
            celery_app.conf.task_always_eager = original_eager

    async def test_concurrent_recompute_converges_without_duplicates(self):
        """
        H4: concurrent recompute executions converge to a single correct persisted state.
        """
        original_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        tenant_id = uuid4()
        window_start = "2025-06-10T00:00:00Z"
        window_end = "2025-06-11T00:00:00Z"

        async with engine.begin() as conn:
            await _insert_tenant(conn, tenant_id)
            await _insert_events(
                conn,
                tenant_id,
                [
                    (uuid4(), "2025-06-10T10:00:00Z", 18000),
                    (uuid4(), "2025-06-10T12:00:00Z", 22000),
                ],
            )

        def _run_task():
            return recompute_window.delay(
                tenant_id=tenant_id,
                window_start=window_start,
                window_end=window_end,
            ).get()

        try:
            loop = asyncio.get_event_loop()
            result_one, result_two = await asyncio.gather(
                loop.run_in_executor(None, _run_task),
                loop.run_in_executor(None, _run_task),
            )

            assert result_one["status"] == "succeeded"
            assert result_two["status"] == "succeeded"

            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )
                allocation_count = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM attribution_allocations
                        WHERE tenant_id = :tenant_id
                        """
                    ),
                    {"tenant_id": tenant_id},
                )
                distinct_allocation_count = await conn.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM (
                            SELECT DISTINCT event_id, channel, model_version
                            FROM attribution_allocations
                            WHERE tenant_id = :tenant_id
                        ) AS distinct_rows
                        """
                    ),
                    {"tenant_id": tenant_id},
                )
                run_count = await conn.execute(
                    text(
                        """
                        SELECT run_count FROM attribution_recompute_jobs
                        WHERE tenant_id = :tenant_id
                        """
                    ),
                    {"tenant_id": tenant_id},
                )

            expected_allocations = 2 * 3
            assert allocation_count.scalar() == expected_allocations, "Concurrency must not create duplicates"
            assert distinct_allocation_count.scalar() == expected_allocations
            assert run_count.scalar() >= 2, "run_count must reflect multiple executions"
        finally:
            celery_app.conf.task_always_eager = original_eager

    async def test_missing_tenant_context_captured_in_dlq_with_correlation(self):
        """
        Gate B: missing tenant context fails deterministically and lands in DLQ with correlation metadata.
        """
        original_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True

        try:
            with pytest.raises(ValueError):
                recompute_window.delay(
                    window_start="2025-06-15T00:00:00Z",
                    window_end="2025-06-16T00:00:00Z",
                ).get(propagate=True)

            async with engine.begin() as conn:
                dlq_result = await conn.execute(
                    text(
                        """
                        SELECT task_name, error_type, tenant_id, correlation_id, task_kwargs
                        FROM worker_failed_jobs
                        WHERE task_name = 'app.tasks.attribution.recompute_window'
                        ORDER BY failed_at DESC
                        LIMIT 1
                        """
                    )
                )
                dlq_row = dlq_result.fetchone()

            assert dlq_row is not None, "DLQ entry must be recorded for missing tenant"
            assert dlq_row[0] == "app.tasks.attribution.recompute_window"
            assert dlq_row[1] == "validation_error"
            assert dlq_row[2] is None, "tenant_id can be null when missing"
            assert dlq_row[3] is not None, "correlation_id must be captured for DLQ diagnostics"
            _parse_uuid(dlq_row[3])  # validate UUID format
            assert "window_start" in dlq_row[4]
            assert "window_end" in dlq_row[4]
        finally:
            celery_app.conf.task_always_eager = original_eager
            # Cleanup DLQ rows created by this test
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        DELETE FROM worker_failed_jobs
                        WHERE task_name = 'app.tasks.attribution.recompute_window'
                        AND error_type = 'validation_error'
                    """
                    )
                )

"""
B0.5.3.6: True E2E proof using real Celery worker subprocess.

Validates deterministic allocations, idempotency, and DLQ correlation propagation
via the schedule_recompute_window scheduling layer (not direct task invocation).
"""
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

pytest_plugins = ["tests.test_b051_celery_foundation"]

from app.celery_app import celery_app  # noqa: E402
from app.db.session import engine, set_tenant_guc  # noqa: E402
from app.services.attribution import schedule_recompute_window  # noqa: E402
from tests.test_b051_celery_foundation import celery_worker_proc as foundation_worker_proc  # noqa: E402
from tests.conftest import _insert_tenant

DEFAULT_SYNC_DSN = os.environ.get(
    "TEST_SYNC_DSN", "postgresql://app_user:app_user@localhost:5432/skeldir_validation"
)
DEFAULT_ASYNC_DSN = os.environ.get(
    "TEST_ASYNC_DSN", "postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"
)
os.environ.setdefault("DATABASE_URL", DEFAULT_ASYNC_DSN)
os.environ.setdefault("CELERY_BROKER_URL", f"sqla+{DEFAULT_SYNC_DSN}")
os.environ.setdefault("CELERY_RESULT_BACKEND", f"db+{DEFAULT_SYNC_DSN}")

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
EVENT_A_ID = UUID("00000000-0000-0000-0000-0000000000a1")
EVENT_B_ID = UUID("00000000-0000-0000-0000-0000000000b2")
EVENT_A_SESSION_ID = UUID("00000000-0000-0000-0000-00000000a0a1")
EVENT_B_SESSION_ID = UUID("00000000-0000-0000-0000-00000000b0b2")
WINDOW_START = "2025-06-01T00:00:00Z"
WINDOW_END = "2025-06-01T23:59:59.999999Z"
MODEL_VERSION = "1.0.0"
EXPECTED_ALLOCATION_RATIO = round(1.0 / 3.0, 6)
EVENT_A_OCCURRED_AT = datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc)
EVENT_B_OCCURRED_AT = datetime(2025, 6, 1, 15, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def celery_worker_proc(foundation_worker_proc):
    return foundation_worker_proc


async def _prepare_facts():
    """Insert tenant and deterministic events for the test window."""
    async with engine.begin() as conn:
        await _insert_tenant(
            conn,
            TENANT_ID,
            api_key_hash=f"test_hash_{TENANT_ID}",
        )
        await set_tenant_guc(conn, TENANT_ID, local=True)
        await conn.execute(text("SELECT set_config('app.execution_context', 'ingestion', true)"))
        # RAW_SQL_ALLOWLIST: seed deterministic events for end-to-end attribution proof
        await conn.execute(
            text(
                """
                INSERT INTO attribution_events (id, tenant_id, session_id, occurred_at, revenue_cents, raw_payload)
                VALUES
                    (:id1, :tenant_id, :session_id_1, CAST(:ts1 AS timestamptz), :rev1, '{}'::jsonb),
                    (:id2, :tenant_id, :session_id_2, CAST(:ts2 AS timestamptz), :rev2, '{}'::jsonb)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "id1": EVENT_A_ID,
                "id2": EVENT_B_ID,
                "session_id_1": EVENT_A_SESSION_ID,
                "session_id_2": EVENT_B_SESSION_ID,
                "tenant_id": TENANT_ID,
                "ts1": EVENT_A_OCCURRED_AT,
                "ts2": EVENT_B_OCCURRED_AT,
                "rev1": 10000,
                "rev2": 15000,
            },
        )


async def _fetch_allocations():
    async with engine.begin() as conn:
        await set_tenant_guc(conn, TENANT_ID, local=True)
        rows = await conn.execute(
            text(
                """
                SELECT event_id, channel, allocation_ratio, allocated_revenue_cents, model_version
                FROM attribution_allocations
                WHERE tenant_id = :tenant_id
                  AND event_id IN (:event_a, :event_b)
                  AND model_version = :model_version
                ORDER BY event_id, channel
                """
            ),
            {
                "tenant_id": TENANT_ID,
                "event_a": EVENT_A_ID,
                "event_b": EVENT_B_ID,
                "model_version": MODEL_VERSION,
            },
        )
        return [
            (row[0], row[1], float(row[2]), row[3], row[4])
            for row in rows.fetchall()
        ]


async def _fetch_latest_dlq_row(correlation_id: str):
    async with engine.begin() as conn:
        await set_tenant_guc(conn, TENANT_ID, local=True)
        result = await conn.execute(
            text(
                """
                SELECT task_name, exception_class, error_message, correlation_id, task_kwargs
                FROM worker_failed_jobs
                WHERE task_name = 'app.tasks.attribution.recompute_window'
                  AND correlation_id = :correlation_id
                ORDER BY failed_at DESC
                LIMIT 1
                """
            ),
            {"correlation_id": UUID(str(correlation_id))},
        )
        return result.fetchone()


def _expected_rows():
    return [
        (EVENT_A_ID, "direct", EXPECTED_ALLOCATION_RATIO, 3333, MODEL_VERSION),
        (EVENT_A_ID, "email", EXPECTED_ALLOCATION_RATIO, 3333, MODEL_VERSION),
        (EVENT_A_ID, "google_search", EXPECTED_ALLOCATION_RATIO, 3333, MODEL_VERSION),
        (EVENT_B_ID, "direct", EXPECTED_ALLOCATION_RATIO, 5000, MODEL_VERSION),
        (EVENT_B_ID, "email", EXPECTED_ALLOCATION_RATIO, 5000, MODEL_VERSION),
        (EVENT_B_ID, "google_search", EXPECTED_ALLOCATION_RATIO, 5000, MODEL_VERSION),
    ]


@pytest.mark.asyncio
async def test_b0536_attribution_e2e_true_worker(celery_worker_proc):
    """
    Execution A: deterministic allocations
    Execution B: idempotent rerun (no duplicates)
    Execution C: failure path yields DLQ with propagated correlation_id
    """
    _ = celery_worker_proc  # Ensure worker process fixture is active
    original_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = False
    try:
        await _prepare_facts()

        # Execution A — success path
        first_result = schedule_recompute_window(
            tenant_id=TENANT_ID,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            model_version=MODEL_VERSION,
        )
        first_payload = first_result.get(timeout=60)
        assert first_payload["status"] == "succeeded"
        assert first_payload["event_count"] == 2
        assert first_payload["allocation_count"] == 6

        allocations_first = await _fetch_allocations()
        assert len(allocations_first) == 6
        assert allocations_first == _expected_rows()

        # Execution B — idempotency proof
        second_result = schedule_recompute_window(
            tenant_id=TENANT_ID,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            model_version=MODEL_VERSION,
        )
        second_payload = second_result.get(timeout=60)
        allocations_second = await _fetch_allocations()

        assert second_payload["status"] == "succeeded"
        assert len(allocations_second) == len(allocations_first) == 6
        assert allocations_second == allocations_first

        # Execution C — failure mode with explicit correlation propagation
        failure_correlation = str(uuid4())
        failing_result = schedule_recompute_window(
            tenant_id=TENANT_ID,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            model_version=MODEL_VERSION,
            correlation_id=failure_correlation,
            fail=True,
        )
        with pytest.raises(ValueError):
            failing_result.get(timeout=60, propagate=True)

        dlq_row = await _fetch_latest_dlq_row(failure_correlation)
        assert dlq_row is not None, "DLQ row must exist after induced failure"
        assert dlq_row[0] == "app.tasks.attribution.recompute_window"
        assert dlq_row[1] == "ValueError"
        assert "attribution recompute failure requested" in dlq_row[2]
        assert str(dlq_row[3]) == failure_correlation
        task_kwargs = dlq_row[4] or {}
        assert task_kwargs.get("correlation_id") == failure_correlation
    finally:
        celery_app.conf.task_always_eager = original_eager

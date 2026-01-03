from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

import os

import pytest
from prometheus_client import generate_latest
from sqlalchemy import text

# Align DB credentials for local/CI parity
DEFAULT_ASYNC_DSN = os.environ.get(
    "TEST_ASYNC_DSN",
    "postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation",
)
os.environ["DATABASE_URL"] = DEFAULT_ASYNC_DSN

from app.celery_app import celery_app
from app.db.session import engine
from app.matviews import executor
from app.observability import metrics
from app.tasks import matviews as matview_tasks


def _make_result(outcome, *, tenant_id: UUID, correlation_id: str) -> executor.RefreshResult:
    return executor.RefreshResult(
        view_name="mv_allocation_summary",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        outcome=outcome,
        started_at=datetime.now(timezone.utc),
        duration_ms=25,
        error_type="unit_test" if outcome == executor.RefreshOutcome.FAILED else None,
        error_message="boom" if outcome == executor.RefreshOutcome.FAILED else None,
        lock_key_debug=None,
    )


def test_strategy_mapping_covers_executor_outcomes():
    tenant_id = uuid4()
    correlation_id = str(uuid4())
    for outcome in executor.RefreshOutcome:
        result = _make_result(outcome, tenant_id=tenant_id, correlation_id=correlation_id)
        strategy = matview_tasks.strategy_for_refresh_result(result)
        assert isinstance(strategy, matview_tasks.TaskOutcomeStrategy)


def test_strategy_mapping_unmapped_outcome_raises():
    class FakeOutcome(Enum):
        UNKNOWN = "UNKNOWN"

    tenant_id = uuid4()
    correlation_id = str(uuid4())
    result = _make_result(FakeOutcome.UNKNOWN, tenant_id=tenant_id, correlation_id=correlation_id)

    with pytest.raises(matview_tasks.UnmappedOutcomeError):
        matview_tasks.strategy_for_refresh_result(result)


def test_matview_metrics_emitted(monkeypatch):
    original = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        tenant_id = uuid4()
        correlation_id = str(uuid4())
        result = _make_result(executor.RefreshOutcome.SUCCESS, tenant_id=tenant_id, correlation_id=correlation_id)

        def fake_refresh_single(view_name, tenant_id_arg, correlation_id_arg):
            return result

        monkeypatch.setattr(matview_tasks, "refresh_single", fake_refresh_single)

        counter = metrics.matview_refresh_total.labels(
            view_name=result.view_name,
            outcome=result.outcome.value,
            strategy=matview_tasks.TaskOutcomeStrategy.SUCCESS.value,
        )
        before = counter._value.get()

        matview_tasks.matview_refresh_single.delay(
            tenant_id=str(tenant_id),
            view_name=result.view_name,
            correlation_id=correlation_id,
        ).get(propagate=True)

        after = counter._value.get()
        assert after == before + 1

        metrics_payload = generate_latest()
        assert b"matview_refresh_total" in metrics_payload
        assert b"matview_refresh_duration_seconds" in metrics_payload
    finally:
        celery_app.conf.task_always_eager = original


@pytest.mark.asyncio
async def test_matview_failure_persists_correlation_id(monkeypatch):
    original = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True
    try:
        tenant_id = uuid4()
        correlation_id = str(uuid4())
        result = _make_result(executor.RefreshOutcome.FAILED, tenant_id=tenant_id, correlation_id=correlation_id)

        def fake_refresh_single(view_name, tenant_id_arg, correlation_id_arg):
            return result

        monkeypatch.setattr(matview_tasks, "refresh_single", fake_refresh_single)

        with pytest.raises(matview_tasks.MatviewTaskFailure):
            matview_tasks.matview_refresh_single.delay(
                tenant_id=str(tenant_id),
                view_name=result.view_name,
                correlation_id=correlation_id,
            ).get(propagate=True)

        async with engine.begin() as conn:
            row = await conn.execute(
                text(
                    """
                    SELECT correlation_id, task_kwargs
                    FROM worker_failed_jobs
                    WHERE task_name = 'app.tasks.matviews.refresh_single'
                    ORDER BY failed_at DESC
                    LIMIT 1
                    """
                )
            )
            row = row.fetchone()

        assert row is not None, "Failed matview task should be captured in worker_failed_jobs"
        assert str(row[0]) == correlation_id
        assert row[1] is not None
        assert str(row[1].get("correlation_id")) == correlation_id

    finally:
        celery_app.conf.task_always_eager = original
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    DELETE FROM worker_failed_jobs
                    WHERE task_name = 'app.tasks.matviews.refresh_single'
                    AND correlation_id = :correlation_id
                    """
                ),
                {"correlation_id": UUID(correlation_id)},
            )

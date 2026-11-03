"""XXV realtime coalescing must not strand the final event of a burst."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.tasks import matviews


def _reset() -> None:
    matviews._REALTIME_REFRESH_LAST.clear()
    matviews._REALTIME_REFRESH_ACTIVE.clear()
    matviews._REALTIME_REFRESH_PENDING.clear()


def test_serial_arrival_during_refresh_queues_one_delayed_owner(monkeypatch) -> None:
    _reset()
    tenant = uuid4()
    monkeypatch.setattr(matviews.time, "monotonic", lambda: 100.0)
    assert matviews._begin_realtime_refresh(tenant, 100.0) == (True, 0.0)
    assert matviews._begin_realtime_refresh(tenant, 100.1) == (False, 0.0)
    assert tenant in matviews._REALTIME_REFRESH_PENDING
    assert tenant in matviews._REALTIME_REFRESH_ACTIVE

    calls = []
    monkeypatch.setattr(
        matviews,
        "enqueue_tenant_task",
        lambda task, **kwargs: calls.append((task, kwargs)),
    )
    delay = matviews._pending_realtime_refresh_delay(tenant)
    assert delay is not None
    matviews._schedule_realtime_trailing(tenant, "corr", delay)
    assert len(calls) == 1
    task, kwargs = calls[0]
    assert task is matviews.matview_refresh_all_for_tenant
    assert kwargs["kwargs"]["trailing"] is True
    assert kwargs["countdown"] == delay
    assert tenant in matviews._REALTIME_REFRESH_ACTIVE
    assert tenant not in matviews._REALTIME_REFRESH_PENDING


def test_arrival_after_owner_releases_becomes_the_next_owner(monkeypatch) -> None:
    _reset()
    tenant = uuid4()
    monkeypatch.setattr(matviews.time, "monotonic", lambda: 100.0)
    assert matviews._begin_realtime_refresh(tenant, 100.0) == (True, 0.0)
    assert matviews._pending_realtime_refresh_delay(tenant) is None
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE
    assert matviews._begin_realtime_refresh(tenant, 101.0) == (True, 0.0)


def test_serial_task_inside_interval_defers_to_one_trailing_refresh(
    monkeypatch,
) -> None:
    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) == (True, 0.0)
    assert matviews._pending_realtime_refresh_delay(tenant) is None
    may_refresh, delay = matviews._begin_realtime_refresh(tenant, 100.2)
    assert may_refresh is False
    assert delay == pytest.approx(0.8)
    assert tenant in matviews._REALTIME_REFRESH_ACTIVE
    assert tenant not in matviews._REALTIME_REFRESH_PENDING

    calls = []
    monkeypatch.setattr(
        matviews,
        "enqueue_tenant_task",
        lambda task, **kwargs: calls.append((task, kwargs)),
    )
    matviews._schedule_realtime_trailing(tenant, "corr", 0.8)
    assert len(calls) == 1
    task, kwargs = calls[0]
    assert task is matviews.matview_refresh_all_for_tenant
    assert kwargs["kwargs"]["trailing"] is True
    assert kwargs["countdown"] == 0.8
    assert tenant in matviews._REALTIME_REFRESH_ACTIVE


def test_task_inside_interval_defers_without_refreshing(monkeypatch) -> None:
    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) == (True, 0.0)
    assert matviews._pending_realtime_refresh_delay(tenant) is None

    calls = []
    monkeypatch.setattr(matviews, "task_tenant_id", lambda _task: tenant)
    monkeypatch.setattr(matviews.time, "monotonic", lambda: 100.2)
    monkeypatch.setattr(
        matviews,
        "enqueue_tenant_task",
        lambda task, **kwargs: calls.append((task, kwargs)),
    )
    monkeypatch.setattr(
        matviews,
        "refresh_all_for_tenant",
        lambda *_args, **_kwargs: pytest.fail("deferred task refreshed"),
    )

    result = matviews.matview_refresh_all_for_tenant.run(
        correlation_id="corr", schedule_class="realtime"
    )
    assert result["status"] == "deferred"
    assert result["delay_s"] == pytest.approx(0.8)
    assert len(calls) == 1
    _task, kwargs = calls[0]
    assert kwargs["kwargs"]["trailing"] is True
    assert kwargs["countdown"] == pytest.approx(0.8)


def test_failed_deferral_publication_refreshes_inline(monkeypatch) -> None:
    from datetime import datetime, timezone

    from app.matviews.executor import RefreshOutcome, RefreshResult

    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) == (True, 0.0)
    assert matviews._pending_realtime_refresh_delay(tenant) is None
    refresh_calls = []

    def _refresh(_tenant, _correlation):
        refresh_calls.append((_tenant, _correlation))
        return [
            RefreshResult(
                view_name="mv_allocation_summary",
                tenant_id=tenant,
                correlation_id="corr",
                outcome=RefreshOutcome.SUCCESS,
                started_at=datetime.now(timezone.utc),
                duration_ms=1,
                error_type=None,
                error_message=None,
                lock_key_debug=None,
            )
        ]

    monkeypatch.setattr(matviews, "task_tenant_id", lambda _task: tenant)
    monkeypatch.setattr(matviews.time, "monotonic", lambda: 100.2)
    monkeypatch.setattr(
        matviews,
        "enqueue_tenant_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("broker_down")
        ),
    )
    monkeypatch.setattr(matviews, "refresh_all_for_tenant", _refresh)

    result = matviews.matview_refresh_all_for_tenant.run(
        correlation_id="corr", schedule_class="realtime"
    )
    assert result["status"] == "ok"
    assert len(refresh_calls) == 1
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE


def test_failed_deferral_and_failed_inline_refresh_is_not_deferred(
    monkeypatch,
) -> None:
    from datetime import datetime, timezone

    from app.matviews.executor import RefreshOutcome, RefreshResult

    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) == (True, 0.0)
    assert matviews._pending_realtime_refresh_delay(tenant) is None
    monkeypatch.setattr(matviews, "task_tenant_id", lambda _task: tenant)
    monkeypatch.setattr(matviews.time, "monotonic", lambda: 100.2)
    monkeypatch.setattr(
        matviews,
        "enqueue_tenant_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("broker_down")
        ),
    )
    monkeypatch.setattr(
        matviews,
        "refresh_all_for_tenant",
        lambda *_args, **_kwargs: [
            RefreshResult(
                view_name="mv_allocation_summary",
                tenant_id=tenant,
                correlation_id="corr",
                outcome=RefreshOutcome.FAILED,
                started_at=datetime.now(timezone.utc),
                duration_ms=1,
                error_type="RuntimeError",
                error_message="refresh_failed",
                lock_key_debug=None,
            )
        ],
    )

    with pytest.raises(matviews.MatviewTaskFailure):
        matviews.matview_refresh_all_for_tenant.run(
            correlation_id="corr", schedule_class="realtime"
        )
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE


def test_failed_owner_releases_claim_then_interval_governs_next_arrival() -> None:
    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) == (True, 0.0)
    matviews._abandon_realtime_refresh(tenant)
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE
    may_refresh, delay = matviews._begin_realtime_refresh(tenant, 100.1)
    assert may_refresh is False
    assert delay == pytest.approx(0.9)
    assert tenant in matviews._REALTIME_REFRESH_ACTIVE


def test_lock_held_is_retry_not_silent_success() -> None:
    from datetime import datetime, timezone

    from app.matviews.executor import RefreshOutcome, RefreshResult

    result = RefreshResult(
        view_name="mv_allocation_summary",
        tenant_id=uuid4(),
        correlation_id="corr",
        outcome=RefreshOutcome.SKIPPED_LOCK_HELD,
        started_at=datetime.now(timezone.utc),
        duration_ms=1,
        error_type=None,
        error_message=None,
        lock_key_debug=None,
    )
    assert (
        matviews.strategy_for_refresh_result(result)
        is matviews.TaskOutcomeStrategy.RETRY
    )

    class _Request:
        retries = 12

    class _Task:
        request = _Request()

        def retry(self, **kwargs):
            raise RuntimeError(kwargs)

    try:
        matviews._apply_strategy(
            task=_Task(),
            result=result,
            strategy=matviews.TaskOutcomeStrategy.RETRY,
        )
    except RuntimeError as exc:
        kwargs = exc.args[0]
    else:  # pragma: no cover - defensive
        raise AssertionError("lock-held refresh did not request a retry")
    assert kwargs["countdown"] == 30
    assert kwargs["max_retries"] is None
    assert matviews.matview_refresh_single.max_retries is None
    assert matviews.matview_refresh_all_for_tenant.max_retries is None


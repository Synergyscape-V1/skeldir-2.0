"""XXV realtime coalescing must not strand the final event of a burst."""

from __future__ import annotations

from uuid import uuid4

from app.tasks import matviews


def _reset() -> None:
    matviews._REALTIME_REFRESH_LAST.clear()
    matviews._REALTIME_REFRESH_PENDING.clear()


def test_coalesced_arrival_is_pending_and_schedules_one_trailing_refresh(
    monkeypatch,
) -> None:
    _reset()
    tenant = uuid4()
    assert matviews._coalesce_realtime_refresh(tenant, 100.0) is False
    assert matviews._coalesce_realtime_refresh(tenant, 100.1) is True
    assert tenant in matviews._REALTIME_REFRESH_PENDING

    calls = []
    monkeypatch.setattr(
        matviews,
        "enqueue_tenant_task",
        lambda task, **kwargs: calls.append((task, kwargs)),
    )
    matviews._schedule_trailing_realtime_refresh(tenant, "corr")
    assert len(calls) == 1
    task, kwargs = calls[0]
    assert task is matviews.matview_refresh_all_for_tenant
    assert kwargs["kwargs"]["trailing"] is True
    assert kwargs["kwargs"]["schedule_class"] == "realtime"
    assert tenant not in matviews._REALTIME_REFRESH_PENDING

    matviews._schedule_trailing_realtime_refresh(tenant, "corr")
    assert len(calls) == 1


def test_trailing_enqueue_failure_keeps_pending(monkeypatch) -> None:
    _reset()
    tenant = uuid4()
    matviews._coalesce_realtime_refresh(tenant, 100.0)
    matviews._coalesce_realtime_refresh(tenant, 100.1)

    def _fail(*_args, **_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(matviews, "enqueue_tenant_task", _fail)
    matviews._schedule_trailing_realtime_refresh(tenant, "corr")
    assert tenant in matviews._REALTIME_REFRESH_PENDING

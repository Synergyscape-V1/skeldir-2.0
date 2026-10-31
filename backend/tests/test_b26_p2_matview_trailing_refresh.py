"""XXV realtime coalescing must not strand the final event of a burst."""

from __future__ import annotations

from uuid import uuid4

from app.tasks import matviews


def _reset() -> None:
    matviews._REALTIME_REFRESH_LAST.clear()
    matviews._REALTIME_REFRESH_ACTIVE.clear()
    matviews._REALTIME_REFRESH_PENDING.clear()


def test_serial_arrival_during_refresh_queues_one_delayed_owner(monkeypatch) -> None:
    _reset()
    tenant = uuid4()
    monkeypatch.setattr(matviews.time, "monotonic", lambda: 100.0)
    assert matviews._begin_realtime_refresh(tenant, 100.0) is True
    assert matviews._begin_realtime_refresh(tenant, 100.1) is False
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
    assert matviews._begin_realtime_refresh(tenant, 100.0) is True
    assert matviews._pending_realtime_refresh_delay(tenant) is None
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE
    assert matviews._begin_realtime_refresh(tenant, 100.2) is True


def test_failed_owner_releases_claim_for_a_later_arrival() -> None:
    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) is True
    matviews._abandon_realtime_refresh(tenant)
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE
    assert matviews._begin_realtime_refresh(tenant, 100.1) is True

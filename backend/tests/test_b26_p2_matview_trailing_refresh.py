"""XXV realtime coalescing must not strand the final event of a burst."""

from __future__ import annotations

from uuid import uuid4

from app.tasks import matviews


def _reset() -> None:
    matviews._REALTIME_REFRESH_LAST.clear()
    matviews._REALTIME_REFRESH_ACTIVE.clear()
    matviews._REALTIME_REFRESH_PENDING.clear()


def test_serial_arrival_during_refresh_keeps_the_owner_alive() -> None:
    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) is True
    assert matviews._begin_realtime_refresh(tenant, 100.1) is False
    assert tenant in matviews._REALTIME_REFRESH_PENDING
    assert matviews._finish_realtime_refresh(tenant) is True
    assert tenant in matviews._REALTIME_REFRESH_ACTIVE
    assert tenant not in matviews._REALTIME_REFRESH_PENDING
    assert matviews._finish_realtime_refresh(tenant) is False
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE


def test_arrival_after_owner_finishes_becomes_the_next_owner() -> None:
    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) is True
    assert matviews._finish_realtime_refresh(tenant) is False
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE
    assert matviews._begin_realtime_refresh(tenant, 100.2) is True
    assert matviews._finish_realtime_refresh(tenant) is False


def test_failed_owner_releases_claim_for_a_later_arrival() -> None:
    _reset()
    tenant = uuid4()
    assert matviews._begin_realtime_refresh(tenant, 100.0) is True
    matviews._abandon_realtime_refresh(tenant)
    assert tenant not in matviews._REALTIME_REFRESH_ACTIVE
    assert matviews._begin_realtime_refresh(tenant, 100.1) is True

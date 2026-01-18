"""
B0.5.6.4: Broker-truth queue depth/max-age metrics.

Enforces:
- TTL cache + single-flight: burst scrapes do not amplify DB load
- Failure safety: /metrics does not crash and keeps last-good values
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _extract_line(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    return None


@pytest.mark.asyncio
async def test_b0564_metrics_cache_singleflight_sequential(monkeypatch, client):
    """
    Burst-scraping /metrics within TTL triggers <= 1 DB refresh.
    """
    from app.observability import broker_queue_stats

    broker_queue_stats._reset_cache_for_tests()
    monkeypatch.setenv("BROKER_QUEUE_STATS_CACHE_TTL_SECONDS", "60")

    calls = {"count": 0}

    async def _fake_fetch():
        calls["count"] += 1
        visible = {"housekeeping": 1}
        invisible = {"housekeeping": 2}
        total = {"housekeeping": 3}
        max_age = {"housekeeping": 4.0}
        return visible, invisible, total, max_age

    monkeypatch.setattr(broker_queue_stats, "_fetch_broker_truth_stats_from_db", _fake_fetch)

    for _ in range(10):
        resp = await client.get("/metrics")
        assert resp.status_code == 200

    assert calls["count"] <= 1


@pytest.mark.asyncio
async def test_b0564_metrics_cache_singleflight_concurrent(monkeypatch, client):
    """
    Concurrent /metrics scrapes share a single in-flight refresh.
    """
    import asyncio
    from app.observability import broker_queue_stats

    broker_queue_stats._reset_cache_for_tests()
    monkeypatch.setenv("BROKER_QUEUE_STATS_CACHE_TTL_SECONDS", "60")

    calls = {"count": 0}

    async def _fake_fetch():
        calls["count"] += 1
        await asyncio.sleep(0.01)
        visible = {"maintenance": 10}
        invisible = {"maintenance": 20}
        total = {"maintenance": 30}
        max_age = {"maintenance": 40.0}
        return visible, invisible, total, max_age

    monkeypatch.setattr(broker_queue_stats, "_fetch_broker_truth_stats_from_db", _fake_fetch)

    results = await asyncio.gather(*[client.get("/metrics") for _ in range(10)])
    assert all(r.status_code == 200 for r in results)
    assert calls["count"] <= 1


@pytest.mark.asyncio
async def test_b0564_refresh_failure_keeps_last_good(monkeypatch, client):
    """
    Refresh failures do not crash /metrics and keep last-good values.
    """
    from app.observability import broker_queue_stats

    broker_queue_stats._reset_cache_for_tests()

    monkeypatch.setenv("BROKER_QUEUE_STATS_CACHE_TTL_SECONDS", "60")

    async def _first_fetch_ok():
        visible = {"housekeeping": 1}
        invisible = {"housekeeping": 0}
        total = {"housekeeping": 1}
        max_age = {"housekeeping": 12.0}
        return visible, invisible, total, max_age

    monkeypatch.setattr(broker_queue_stats, "_fetch_broker_truth_stats_from_db", _first_fetch_ok)

    first = await client.get("/metrics")
    assert first.status_code == 200
    assert (
        _extract_line(
            first.text,
            'celery_queue_messages{queue="housekeeping",state="visible"} 1.0',
        )
        is not None
    )

    async def _second_fetch_fails():
        raise RuntimeError("db_read_failed")

    monkeypatch.setattr(broker_queue_stats, "_fetch_broker_truth_stats_from_db", _second_fetch_fails)
    monkeypatch.setenv("BROKER_QUEUE_STATS_CACHE_TTL_SECONDS", "0")

    second = await client.get("/metrics")
    assert second.status_code == 200
    assert (
        _extract_line(
            second.text,
            'celery_queue_messages{queue="housekeeping",state="visible"} 1.0',
        )
        is not None
    )
    assert _extract_line(second.text, "celery_queue_stats_refresh_errors_total 1.0") is not None


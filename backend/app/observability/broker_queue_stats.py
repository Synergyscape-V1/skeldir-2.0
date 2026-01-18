"""
Broker-truth Celery queue depth + max age metrics (B0.5.6.4).

These metrics are derived from the Postgres SQLAlchemy kombu transport tables:
- public.kombu_queue
- public.kombu_message

Design constraints:
- Read-only: SELECT-only SQL
- Safe: TTL cache + single-flight refresh to avoid DB DoS via /metrics scrapes
- Bounded: queue labels normalized to a closed allowlist (plus 'unknown')
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

from prometheus_client import REGISTRY
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from sqlalchemy import text

from app.core.queues import ALLOWED_QUEUES
from app.db.session import engine
from app.observability.metrics_policy import (
    ALLOWED_QUEUE_STATES,
    normalize_queue,
    normalize_queue_state,
)


PIDBOX_QUEUE_EXCLUSION_LIKE = "%.reply.celery.pidbox"


@dataclass(frozen=True)
class BrokerQueueStatsSnapshot:
    """
    Immutable snapshot of broker-truth queue stats for metric export.

    All values are pre-normalized/bounded so metric exposition cannot explode
    cardinality even if kombu_queue contains unexpected names.
    """

    as_of_unix_timestamp_seconds: float
    visible_counts: dict[str, int]
    invisible_counts: dict[str, int]
    total_counts: dict[str, int]
    max_age_seconds: dict[str, float]
    refresh_errors_total: int


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _cache_ttl_seconds() -> float:
    raw = os.getenv("BROKER_QUEUE_STATS_CACHE_TTL_SECONDS", "5")
    try:
        ttl = float(raw)
    except Exception:
        ttl = 5.0
    if ttl < 0:
        ttl = 0.0
    return ttl


_cache_lock = asyncio.Lock()
_refresh_inflight: asyncio.Task[None] | None = None
_last_refresh_monotonic: float | None = None

# Cache always exists (even if zeroed) so /metrics never crashes.
_snapshot: BrokerQueueStatsSnapshot = BrokerQueueStatsSnapshot(
    as_of_unix_timestamp_seconds=0.0,
    visible_counts={},
    invisible_counts={},
    total_counts={},
    max_age_seconds={},
    refresh_errors_total=0,
)


BROKER_QUEUE_MESSAGES_METRIC = "celery_queue_messages"
BROKER_QUEUE_MAX_AGE_METRIC = "celery_queue_max_age_seconds"
BROKER_QUEUE_LAST_REFRESH_METRIC = "celery_queue_stats_last_refresh_timestamp_seconds"
BROKER_QUEUE_REFRESH_ERRORS_METRIC = "celery_queue_stats_refresh_errors_total"

QUEUE_STATE_ORDER: tuple[str, ...] = ("visible", "invisible", "total")


def _all_queues_with_unknown() -> tuple[str, ...]:
    # Stable ordering to avoid churn in exposition diffs.
    return tuple(sorted(ALLOWED_QUEUES)) + ("unknown",)


async def _fetch_broker_truth_stats_from_db() -> tuple[
    dict[str, int], dict[str, int], dict[str, int], dict[str, float]
]:
    """
    Fetch queue stats from kombu tables using SELECT-only SQL.

    Returns (visible_counts, invisible_counts, total_counts, max_age_seconds) keyed by raw queue name.
    """
    sql = text(
        """
        SELECT
            q.name AS queue_name,
            COALESCE(SUM(CASE WHEN m.visible THEN 1 ELSE 0 END), 0) AS visible_count,
            COALESCE(SUM(CASE WHEN NOT m.visible THEN 1 ELSE 0 END), 0) AS invisible_count,
            COALESCE(COUNT(m.id), 0) AS total_count,
            COALESCE(
                EXTRACT(EPOCH FROM (NOW() - (MIN(m.timestamp) FILTER (WHERE m.visible)))),
                0
            ) AS max_age_seconds
        FROM kombu_queue q
        LEFT JOIN kombu_message m ON m.queue_id = q.id
        WHERE q.name NOT LIKE :pidbox_like
        GROUP BY q.name
        """
    )
    async with engine.connect() as conn:
        res = await conn.execute(sql, {"pidbox_like": PIDBOX_QUEUE_EXCLUSION_LIKE})
        rows = res.fetchall()

    visible: dict[str, int] = {}
    invisible: dict[str, int] = {}
    total: dict[str, int] = {}
    max_age: dict[str, float] = {}
    for row in rows:
        queue_name = str(row.queue_name) if row.queue_name is not None else "unknown"
        visible[queue_name] = _coerce_int(row.visible_count)
        invisible[queue_name] = _coerce_int(row.invisible_count)
        total[queue_name] = _coerce_int(row.total_count)
        max_age[queue_name] = _coerce_float(row.max_age_seconds)

    return visible, invisible, total, max_age


def _aggregate_bounded_counts(
    raw_counts: dict[str, int], *, all_queues: Iterable[str]
) -> dict[str, int]:
    bounded = {q: 0 for q in all_queues}
    for raw_queue, count in raw_counts.items():
        bounded_queue = normalize_queue(raw_queue)
        bounded[bounded_queue] = bounded.get(bounded_queue, 0) + _coerce_int(count)
    return bounded


def _aggregate_bounded_max_age(
    raw_max_age_seconds: dict[str, float], *, all_queues: Iterable[str]
) -> dict[str, float]:
    bounded = {q: 0.0 for q in all_queues}
    for raw_queue, age_s in raw_max_age_seconds.items():
        bounded_queue = normalize_queue(raw_queue)
        bounded[bounded_queue] = max(bounded.get(bounded_queue, 0.0), _coerce_float(age_s))
    return bounded


def _is_cache_valid() -> bool:
    ttl = _cache_ttl_seconds()
    if ttl == 0:
        return False
    if _last_refresh_monotonic is None:
        return False
    return (time.monotonic() - _last_refresh_monotonic) < ttl


async def maybe_refresh_broker_queue_stats() -> None:
    """
    Refresh cached broker stats if TTL expired (single-flight).

    Never raises. On failure, increments a bounded error counter and keeps last-good values.
    """
    global _refresh_inflight

    async with _cache_lock:
        if _is_cache_valid():
            return
        if _refresh_inflight is None:
            _refresh_inflight = asyncio.create_task(_refresh_cache_from_db())
        inflight = _refresh_inflight

    try:
        await inflight
    finally:
        async with _cache_lock:
            if _refresh_inflight is inflight:
                _refresh_inflight = None


async def _refresh_cache_from_db() -> None:
    global _last_refresh_monotonic, _snapshot

    try:
        raw_visible, raw_invisible, raw_total, raw_max_age = await _fetch_broker_truth_stats_from_db()
        all_queues = _all_queues_with_unknown()
        visible = _aggregate_bounded_counts(raw_visible, all_queues=all_queues)
        invisible = _aggregate_bounded_counts(raw_invisible, all_queues=all_queues)
        total = _aggregate_bounded_counts(raw_total, all_queues=all_queues)
        max_age_seconds = _aggregate_bounded_max_age(raw_max_age, all_queues=all_queues)

        _snapshot = BrokerQueueStatsSnapshot(
            as_of_unix_timestamp_seconds=time.time(),
            visible_counts=visible,
            invisible_counts=invisible,
            total_counts=total,
            max_age_seconds=max_age_seconds,
            refresh_errors_total=_snapshot.refresh_errors_total,
        )
        _last_refresh_monotonic = time.monotonic()
    except Exception:
        _snapshot = BrokerQueueStatsSnapshot(
            as_of_unix_timestamp_seconds=_snapshot.as_of_unix_timestamp_seconds,
            visible_counts=_snapshot.visible_counts,
            invisible_counts=_snapshot.invisible_counts,
            total_counts=_snapshot.total_counts,
            max_age_seconds=_snapshot.max_age_seconds,
            refresh_errors_total=_snapshot.refresh_errors_total + 1,
        )


class BrokerQueueStatsCollector:
    def collect(self):
        snapshot = _snapshot
        all_queues = _all_queues_with_unknown()

        messages = GaugeMetricFamily(
            BROKER_QUEUE_MESSAGES_METRIC,
            "Celery queue depth derived from kombu tables (broker truth)",
            labels=["queue", "state"],
        )

        for queue in all_queues:
            for state in QUEUE_STATE_ORDER:
                if state not in ALLOWED_QUEUE_STATES:
                    continue
                normalized_state = normalize_queue_state(state)
                if normalized_state == "visible":
                    value = snapshot.visible_counts.get(queue, 0)
                elif normalized_state == "invisible":
                    value = snapshot.invisible_counts.get(queue, 0)
                else:
                    value = snapshot.total_counts.get(queue, 0)
                messages.add_metric([queue, normalized_state], float(value))

        max_age = GaugeMetricFamily(
            BROKER_QUEUE_MAX_AGE_METRIC,
            "Age in seconds of the oldest visible message in each Celery queue (broker truth)",
            labels=["queue"],
        )
        for queue in all_queues:
            max_age.add_metric([queue], snapshot.max_age_seconds.get(queue, 0.0))

        last_refresh = GaugeMetricFamily(
            BROKER_QUEUE_LAST_REFRESH_METRIC,
            "Unix timestamp (seconds) of the last successful broker truth refresh",
            labels=[],
        )
        last_refresh.add_metric([], snapshot.as_of_unix_timestamp_seconds)

        errors = CounterMetricFamily(
            BROKER_QUEUE_REFRESH_ERRORS_METRIC,
            "Total broker truth refresh errors in this process",
            labels=[],
        )
        errors.add_metric([], float(snapshot.refresh_errors_total))

        yield messages
        yield max_age
        yield last_refresh
        yield errors


_default_registry_registered = False


def ensure_default_registry_registered() -> None:
    global _default_registry_registered
    if _default_registry_registered:
        return
    REGISTRY.register(BrokerQueueStatsCollector())
    _default_registry_registered = True


def register_collector(registry) -> None:
    """
    Register this collector to a provided registry (e.g., multiprocess aggregation registry).
    """
    registry.register(BrokerQueueStatsCollector())


def _reset_cache_for_tests() -> None:
    global _refresh_inflight, _last_refresh_monotonic, _snapshot
    _refresh_inflight = None
    _last_refresh_monotonic = None
    _snapshot = BrokerQueueStatsSnapshot(
        as_of_unix_timestamp_seconds=0.0,
        visible_counts={},
        invisible_counts={},
        total_counts={},
        max_age_seconds={},
        refresh_errors_total=0,
    )

"""
Canonical response builders for realtime revenue semantics (B0.6 Phase 5).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from app.core import clock as clock_module
from app.services.realtime_revenue_cache import RealtimeRevenueSnapshot

ClockFn = Callable[[], datetime]


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now(clock_fn: ClockFn | None) -> datetime:
    return (clock_fn or clock_module.utcnow)()


def _freshness_seconds(now: datetime, fetch_time: datetime) -> int:
    delta = now - fetch_time
    return max(0, int(delta.total_seconds()))


def build_attribution_realtime_revenue_response(
    snapshot: RealtimeRevenueSnapshot,
    tenant_id: UUID,
    *,
    clock: ClockFn | None = None,
) -> dict[str, object]:
    fetch_time = _normalize_datetime(snapshot.data_as_of)
    now = _now(clock)
    return {
        "total_revenue": snapshot.revenue_total_cents / 100.0,
        "event_count": snapshot.event_count,
        "last_updated": fetch_time,
        "data_freshness_seconds": _freshness_seconds(now, fetch_time),
        "verified": False,
        "tenant_id": str(tenant_id),
        "confidence_score": snapshot.confidence_score if snapshot.confidence_score is not None else 0.0,
        "upgrade_notice": snapshot.upgrade_notice,
    }


def build_realtime_revenue_v1_response(
    snapshot: RealtimeRevenueSnapshot,
    tenant_id: UUID,
) -> dict[str, object]:
    fetch_time = _normalize_datetime(snapshot.data_as_of)
    return {
        "tenant_id": str(tenant_id),
        "interval": snapshot.interval,
        "currency": snapshot.currency,
        "revenue_total": snapshot.revenue_total_cents / 100.0,
        "verified": False,
        "data_as_of": fetch_time,
        "sources": snapshot.sources,
    }

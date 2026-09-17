"""Governed UTC day-window quantization shared by B2.3 dispatch and P2 scope.

Single-implementation law (B2.6-P2 Corrective II, H-II-03): the UTC
calendar-day half-open quantization ``[00:00, +1d)`` is defined exactly once
here. The webhook natural-dispatch path (B2.3 batch window) and the P2
dispatch authority (reconciliation window) both delegate to this function,
so the two window ontologies cannot silently diverge into different day
boundaries while appearing equal in fixtures. B2.3 matching and P2
reconciliation remain distinct authorities sharing one quantization
function -- not one implicit window, and never wall/worker/statement clocks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def quantize_utc_day(event_time: datetime) -> tuple[datetime, datetime]:
    """Quantize one instant to its UTC day half-open window.

    Leniency law (webhook compat): naive datetimes assume UTC (matching the
    historical ``_coerce_event_timestamp`` behavior relied upon by ingestion
    callers and benchmarks). P2 scope strictness (naive-refused) is enforced
    by the dispatch authority *before* delegating here, so financial scope
    never silently coerces a naive clock while ingestion keeps its lenient
    contract. Aware instants quantize identically through this single
    implementation.
    """
    if not isinstance(event_time, datetime):
        raise ValueError("day_window_event_time_not_datetime")
    if event_time.tzinfo is None or event_time.tzinfo.utcoffset(event_time) is None:
        occurred = event_time.replace(tzinfo=timezone.utc)
    else:
        occurred = event_time.astimezone(timezone.utc)
    start = occurred.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def quantize_utc_day_iso(event_timestamp_iso: str) -> tuple[str, str]:
    """ISO-string façade returning ``Z``-suffixed day boundaries."""
    token = (event_timestamp_iso or "").strip()
    if not token:
        raise ValueError("day_window_event_time_missing")
    try:
        event_time = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"day_window_malformed:{exc}") from exc
    start, end = quantize_utc_day(event_time)
    return (
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
    )


__all__ = ("quantize_utc_day", "quantize_utc_day_iso")

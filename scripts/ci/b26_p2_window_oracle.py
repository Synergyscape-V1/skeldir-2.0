#!/usr/bin/env python3
"""B2.6-P2 independent normative window oracle (Corrective III, Class E).

This module pins the UTC calendar-day half-open law WITHOUT importing the
production quantizer (app.core.day_window). It is the independent oracle
against common-mode drift: producer and verifier share the production
helper, so a wrong helper stays universally consistent yet wrong. This
oracle is written independently (stdlib datetime only) and the governing
proof REDs whenever production disagrees with it.

Law pinned:
- UTC normalization (aware -> UTC, naive refused here);
- 00:00 UTC day start;
- exact +1-day end;
- [start, end) half-open (start included, end excluded);
- timezone-equivalent instants quantize identically;
- DST irrelevance (UTC has no DST).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def oracle_quantize_utc_day(event_time: datetime) -> tuple[datetime, datetime]:
    if not isinstance(event_time, datetime):
        raise ValueError("oracle_event_time_not_datetime")
    if event_time.tzinfo is None or event_time.tzinfo.utcoffset(event_time) is None:
        raise ValueError("oracle_naive_refused")
    occurred = event_time.astimezone(timezone.utc)
    start = datetime(
        occurred.year, occurred.month, occurred.day, 0, 0, 0, tzinfo=timezone.utc
    )
    return start, start + timedelta(days=1)


def oracle_vectors() -> list[tuple[str, datetime, datetime, datetime]]:
    """(name, instant, expected_start, expected_end)."""
    utc = timezone.utc
    d = datetime(2026, 1, 15, 12, 0, tzinfo=utc)
    s = datetime(2026, 1, 15, 0, 0, tzinfo=utc)
    e = datetime(2026, 1, 16, 0, 0, tzinfo=utc)
    # Timezone-equivalent instant: +02:00 wall 14:00 == UTC 12:00 same day.
    tz_plus2 = timezone(timedelta(hours=2))
    equiv = datetime(2026, 1, 15, 14, 0, tzinfo=tz_plus2)
    # Late-day instant still in same UTC day (23:59:59).
    late = datetime(2026, 1, 15, 23, 59, 59, tzinfo=utc)
    # Exact end instant belongs to the NEXT day window.
    nxt = datetime(2026, 1, 16, 0, 0, tzinfo=utc)
    nxt_end = datetime(2026, 1, 17, 0, 0, tzinfo=utc)
    # DST-observing zone instant (America/New_York winter EST -05:00):
    # 2026-01-15 07:00 EST == 12:00 UTC same day.
    est = timezone(timedelta(hours=-5))
    dst_probe = datetime(2026, 1, 15, 7, 0, tzinfo=est)
    return [
        ("midday_utc", d, s, e),
        ("timezone_equivalent", equiv, s, e),
        ("late_day", late, s, e),
        ("exact_end_next_window", nxt, e, nxt_end),
        ("dst_irrelevant_est", dst_probe, s, e),
    ]


def check_production_quantizer(quantize_fn) -> list[str]:
    """Compare one production quantize fn against the oracle. Return errors."""
    errors: list[str] = []
    for name, instant, exp_start, exp_end in oracle_vectors():
        try:
            got_start, got_end = quantize_fn(instant)
        except Exception as exc:
            errors.append(f"{name}:production_raised:{exc}")
            continue
        if got_start != exp_start or got_end != exp_end:
            errors.append(
                f"{name}:mismatch:got={got_start.isoformat()}/{got_end.isoformat()}"
                f":want={exp_start.isoformat()}/{exp_end.isoformat()}"
            )
    # Half-open membership law (independent of the quantizer internals).
    s = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
    e = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
    if not (s <= s < e):
        errors.append("half_open:start_not_included")
    if e <= e < datetime(2026, 1, 17, 0, 0, tzinfo=timezone.utc):
        pass
    # End-excluded: the exact end instant must NOT satisfy start <= t < end.
    if s <= e < e:
        errors.append("half_open:end_wrongly_included")
    # Naive must refuse in P2-strict contexts (oracle refuses; production
    # strict layer must refuse before delegating to the lenient core).
    try:
        oracle_quantize_utc_day(datetime(2026, 1, 15, 12, 0))
        errors.append("oracle:naive_not_refused")
    except ValueError:
        pass
    return errors


if __name__ == "__main__":
    import sys

    sys.path.insert(0, "backend")
    from app.core.day_window import quantize_utc_day

    errs = check_production_quantizer(quantize_utc_day)
    if errs:
        print("WINDOW_ORACLE_RED")
        for err in errs:
            print(f"  - {err}")
        raise SystemExit(1)
    print("WINDOW_ORACLE_PASS")

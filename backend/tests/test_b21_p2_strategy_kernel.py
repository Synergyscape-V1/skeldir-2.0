from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from app.attribution.strategy_kernel import (
    ChannelRatio,
    EligibleTouchpoint,
    FIRST_TOUCH_MODEL,
    LAST_TOUCH_MODEL,
    LINEAR_MODEL,
    TIME_DECAY_MODEL,
    assert_ratio_conservation,
    build_channel_allocations_for_conversion,
    derive_channel_ratios,
)


def _tp(*, raw_id: str, channel: str, occurred_at: datetime) -> EligibleTouchpoint:
    return EligibleTouchpoint(
        id=UUID(raw_id),
        channel_code=channel,
        occurred_at=occurred_at,
    )


def test_b21_p2_first_touch_and_last_touch_use_total_tie_break_order() -> None:
    conversion_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    tied_time = conversion_at - timedelta(hours=2)
    touchpoints = [
        _tp(
            raw_id="00000000-0000-0000-0000-000000000002",
            channel="email",
            occurred_at=tied_time,
        ),
        _tp(
            raw_id="00000000-0000-0000-0000-000000000001",
            channel="direct",
            occurred_at=tied_time,
        ),
    ]

    first = derive_channel_ratios(
        model_type=FIRST_TOUCH_MODEL,
        touchpoints=touchpoints,
        conversion_occurred_at=conversion_at,
    )
    last = derive_channel_ratios(
        model_type=LAST_TOUCH_MODEL,
        touchpoints=touchpoints,
        conversion_occurred_at=conversion_at,
    )

    assert len(first) == 1
    assert len(last) == 1
    assert first[0].channel_code == "direct"
    assert first[0].allocation_ratio == Decimal("1.00000")
    assert last[0].channel_code == "email"
    assert last[0].allocation_ratio == Decimal("1.00000")


def test_b21_p2_linear_and_time_decay_match_expected_math() -> None:
    conversion_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    touchpoints = [
        _tp(
            raw_id="00000000-0000-0000-0000-000000000010",
            channel="direct",
            occurred_at=conversion_at,
        ),
        _tp(
            raw_id="00000000-0000-0000-0000-000000000011",
            channel="email",
            occurred_at=conversion_at - timedelta(days=7),
        ),
        _tp(
            raw_id="00000000-0000-0000-0000-000000000012",
            channel="google_search_paid",
            occurred_at=conversion_at - timedelta(days=14),
        ),
    ]

    linear = derive_channel_ratios(
        model_type=LINEAR_MODEL,
        touchpoints=touchpoints,
        conversion_occurred_at=conversion_at,
    )
    time_decay = derive_channel_ratios(
        model_type=TIME_DECAY_MODEL,
        touchpoints=touchpoints,
        conversion_occurred_at=conversion_at,
    )

    linear_by_channel = {row.channel_code: row.allocation_ratio for row in linear}
    assert linear_by_channel["direct"] == Decimal("0.33334")
    assert linear_by_channel["email"] == Decimal("0.33333")
    assert linear_by_channel["google_search_paid"] == Decimal("0.33333")
    assert_ratio_conservation(linear)

    # Exponential 7-day half-life: weights [1, 0.5, 0.25] normalized.
    time_decay_by_channel = {row.channel_code: row.allocation_ratio for row in time_decay}
    assert time_decay_by_channel["direct"] == Decimal("0.57143")
    assert time_decay_by_channel["email"] == Decimal("0.28571")
    assert time_decay_by_channel["google_search_paid"] == Decimal("0.14286")
    assert_ratio_conservation(time_decay)


def test_b21_p2_null_touchpoint_fallback_and_conservation() -> None:
    conversion_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    allocations, used_null_touchpoint_fallback = build_channel_allocations_for_conversion(
        model_type=FIRST_TOUCH_MODEL,
        touchpoints=[],
        conversion_occurred_at=conversion_at,
        revenue_cents=12345,
    )
    assert used_null_touchpoint_fallback is True
    assert len(allocations) == 1
    assert allocations[0].channel_code == "direct"
    assert allocations[0].allocation_ratio == Decimal("1.00000")
    assert allocations[0].allocated_revenue_cents == 12345


def test_b21_p2_known_bad_ratio_fixture_fails_conservation_guard() -> None:
    bad_fixture = [
        ChannelRatio(channel_code="direct", allocation_ratio=Decimal("0.60000"), residual_rank=1),
        ChannelRatio(channel_code="email", allocation_ratio=Decimal("0.30000"), residual_rank=2),
    ]
    with pytest.raises(ValueError, match="conservation"):
        assert_ratio_conservation(bad_fixture)

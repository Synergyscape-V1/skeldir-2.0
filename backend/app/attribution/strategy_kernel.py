"""Deterministic attribution strategy kernel for B2.1-P2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, localcontext
from typing import Callable
from uuid import UUID


DETERMINISTIC_BASELINE_MODEL = "deterministic_baseline"
FIRST_TOUCH_MODEL = "first_touch"
LAST_TOUCH_MODEL = "last_touch"
LINEAR_MODEL = "linear"
TIME_DECAY_MODEL = "time_decay"

SUPPORTED_DETERMINISTIC_MODEL_TYPES: frozenset[str] = frozenset(
    {
        DETERMINISTIC_BASELINE_MODEL,
        FIRST_TOUCH_MODEL,
        LAST_TOUCH_MODEL,
        LINEAR_MODEL,
        TIME_DECAY_MODEL,
    }
)
STRATEGY_MODEL_TYPES: frozenset[str] = frozenset(
    {
        FIRST_TOUCH_MODEL,
        LAST_TOUCH_MODEL,
        LINEAR_MODEL,
        TIME_DECAY_MODEL,
    }
)

_MODEL_ALIASES: dict[str, str] = {
    "deterministic_baseline": DETERMINISTIC_BASELINE_MODEL,
    "baseline": DETERMINISTIC_BASELINE_MODEL,
    "first_touch": FIRST_TOUCH_MODEL,
    "deterministic_first_touch": FIRST_TOUCH_MODEL,
    "last_touch": LAST_TOUCH_MODEL,
    "deterministic_last_touch": LAST_TOUCH_MODEL,
    "linear": LINEAR_MODEL,
    "deterministic_linear": LINEAR_MODEL,
    "time_decay": TIME_DECAY_MODEL,
    "deterministic_time_decay": TIME_DECAY_MODEL,
}

DIRECT_UNATTRIBUTED_CHANNEL = "direct"
RATIO_QUANTUM = Decimal("0.00001")
RATIO_TOLERANCE = Decimal("0.001")
ONE = Decimal("1")
_HALF_LIFE_SECONDS = Decimal("604800")
_LOG_TWO = Decimal("2").ln()


@dataclass(frozen=True)
class EligibleTouchpoint:
    id: UUID
    occurred_at: datetime
    channel_code: str


@dataclass(frozen=True)
class ChannelRatio:
    channel_code: str
    allocation_ratio: Decimal
    residual_rank: int


@dataclass(frozen=True)
class ChannelAllocation:
    channel_code: str
    allocation_ratio: Decimal
    allocated_revenue_cents: int
    residual_rank: int


def canonical_model_type(raw_model_type: str | None) -> str:
    token = str(raw_model_type or DETERMINISTIC_BASELINE_MODEL).strip().lower()
    if token not in _MODEL_ALIASES:
        raise ValueError(
            f"Unsupported deterministic model_type: {raw_model_type}. "
            f"Allowed: {sorted(SUPPORTED_DETERMINISTIC_MODEL_TYPES)}"
        )
    return _MODEL_ALIASES[token]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sorted_touchpoints_ascending(touchpoints: list[EligibleTouchpoint]) -> list[EligibleTouchpoint]:
    return sorted(
        touchpoints,
        key=lambda item: (_as_utc(item.occurred_at), str(item.id)),
    )


def strategy_first_touch(
    touchpoints: list[EligibleTouchpoint],
    *,
    conversion_occurred_at: datetime,
) -> dict[UUID, Decimal]:
    _ = conversion_occurred_at
    ordered = _sorted_touchpoints_ascending(touchpoints)
    if not ordered:
        return {}
    return {ordered[0].id: ONE}


def strategy_last_touch(
    touchpoints: list[EligibleTouchpoint],
    *,
    conversion_occurred_at: datetime,
) -> dict[UUID, Decimal]:
    _ = conversion_occurred_at
    ordered = _sorted_touchpoints_ascending(touchpoints)
    if not ordered:
        return {}
    return {ordered[-1].id: ONE}


def strategy_linear(
    touchpoints: list[EligibleTouchpoint],
    *,
    conversion_occurred_at: datetime,
) -> dict[UUID, Decimal]:
    _ = conversion_occurred_at
    ordered = _sorted_touchpoints_ascending(touchpoints)
    if not ordered:
        return {}
    return {touchpoint.id: ONE for touchpoint in ordered}


def strategy_time_decay(
    touchpoints: list[EligibleTouchpoint],
    *,
    conversion_occurred_at: datetime,
) -> dict[UUID, Decimal]:
    ordered = _sorted_touchpoints_ascending(touchpoints)
    if not ordered:
        return {}
    conversion_at_utc = _as_utc(conversion_occurred_at)
    with localcontext() as context:
        context.prec = 50
        weights: dict[UUID, Decimal] = {}
        for touchpoint in ordered:
            delta_seconds = Decimal(
                str((conversion_at_utc - _as_utc(touchpoint.occurred_at)).total_seconds())
            )
            if delta_seconds < 0:
                raise ValueError(
                    "time_decay strategy received a touchpoint after conversion;"
                    f" touchpoint_id={touchpoint.id}"
                )
            exponent = -_LOG_TWO * (delta_seconds / _HALF_LIFE_SECONDS)
            weights[touchpoint.id] = exponent.exp()
        return weights


_STRATEGY_MAP: dict[str, Callable[..., dict[UUID, Decimal]]] = {
    FIRST_TOUCH_MODEL: strategy_first_touch,
    LAST_TOUCH_MODEL: strategy_last_touch,
    LINEAR_MODEL: strategy_linear,
    TIME_DECAY_MODEL: strategy_time_decay,
}


def _quantize_channel_ratios(weight_by_channel: dict[str, Decimal]) -> list[ChannelRatio]:
    if not weight_by_channel:
        return [
            ChannelRatio(
                channel_code=DIRECT_UNATTRIBUTED_CHANNEL,
                allocation_ratio=ONE.quantize(RATIO_QUANTUM),
                residual_rank=1,
            )
        ]
    with localcontext() as context:
        context.prec = 50
        total_weight = sum(weight_by_channel.values(), start=Decimal("0"))
        if total_weight <= 0:
            raise ValueError("Channel weight total must be > 0")

        rows: list[dict[str, Decimal | str]] = []
        for channel_code in sorted(weight_by_channel.keys()):
            raw_ratio = weight_by_channel[channel_code] / total_weight
            floored_ratio = raw_ratio.quantize(RATIO_QUANTUM, rounding=ROUND_DOWN)
            rows.append(
                {
                    "channel_code": channel_code,
                    "raw_ratio": raw_ratio,
                    "allocation_ratio": floored_ratio,
                    "fractional_remainder": raw_ratio - floored_ratio,
                }
            )

        floored_sum = sum(
            (row["allocation_ratio"] for row in rows),
            start=Decimal("0"),
        )
        ratio_units_missing = int(
            ((ONE - floored_sum) / RATIO_QUANTUM).to_integral_value(rounding=ROUND_HALF_UP)
        )
        if ratio_units_missing < 0:
            raise ValueError(
                f"Ratio quantization overflow: floored_sum={floored_sum} missing={ratio_units_missing}"
            )

        ratio_remainder_order = sorted(
            rows,
            key=lambda row: (
                -row["fractional_remainder"],
                str(row["channel_code"]),
            ),
        )
        if ratio_units_missing > 0 and ratio_remainder_order:
            for index in range(ratio_units_missing):
                ratio_remainder_order[index % len(ratio_remainder_order)]["allocation_ratio"] += (
                    RATIO_QUANTUM
                )

        residual_order = sorted(
            rows,
            key=lambda row: (
                -row["fractional_remainder"],
                str(row["channel_code"]),
            ),
        )
        residual_rank = {
            str(row["channel_code"]): rank
            for rank, row in enumerate(residual_order, start=1)
        }

        result = [
            ChannelRatio(
                channel_code=str(row["channel_code"]),
                allocation_ratio=Decimal(str(row["allocation_ratio"])),
                residual_rank=residual_rank[str(row["channel_code"])],
            )
            for row in sorted(rows, key=lambda row: str(row["channel_code"]))
        ]
        assert_ratio_conservation(result)
        return result


def derive_channel_ratios(
    *,
    model_type: str,
    touchpoints: list[EligibleTouchpoint],
    conversion_occurred_at: datetime,
) -> list[ChannelRatio]:
    canonical_model = canonical_model_type(model_type)
    if canonical_model not in STRATEGY_MODEL_TYPES:
        raise ValueError(
            f"derive_channel_ratios requires one of {sorted(STRATEGY_MODEL_TYPES)}; "
            f"got {canonical_model}"
        )
    ordered_touchpoints = _sorted_touchpoints_ascending(touchpoints)
    if not ordered_touchpoints:
        return [
            ChannelRatio(
                channel_code=DIRECT_UNATTRIBUTED_CHANNEL,
                allocation_ratio=ONE.quantize(RATIO_QUANTUM),
                residual_rank=1,
            )
        ]

    strategy = _STRATEGY_MAP[canonical_model]
    touchpoint_weights = strategy(
        ordered_touchpoints,
        conversion_occurred_at=conversion_occurred_at,
    )
    if not touchpoint_weights:
        return [
            ChannelRatio(
                channel_code=DIRECT_UNATTRIBUTED_CHANNEL,
                allocation_ratio=ONE.quantize(RATIO_QUANTUM),
                residual_rank=1,
            )
        ]

    weights_by_channel: dict[str, Decimal] = {}
    channel_by_touchpoint = {
        touchpoint.id: touchpoint.channel_code.strip().lower()
        for touchpoint in ordered_touchpoints
    }
    for touchpoint_id, weight in touchpoint_weights.items():
        channel_code = channel_by_touchpoint[touchpoint_id]
        weights_by_channel[channel_code] = weights_by_channel.get(channel_code, Decimal("0")) + weight

    return _quantize_channel_ratios(weights_by_channel)


def assert_ratio_conservation(channel_ratios: list[ChannelRatio]) -> None:
    if not channel_ratios:
        raise ValueError("channel_ratios must not be empty")
    total_ratio = sum(
        (row.allocation_ratio for row in channel_ratios),
        start=Decimal("0"),
    )
    if abs(total_ratio - ONE) > RATIO_TOLERANCE:
        raise ValueError(
            "Allocation ratio conservation violated: "
            f"sum={total_ratio} tolerance={RATIO_TOLERANCE}"
        )


def allocate_revenue_cents(
    *,
    revenue_cents: int,
    channel_ratios: list[ChannelRatio],
) -> list[ChannelAllocation]:
    if revenue_cents < 0:
        raise ValueError("revenue_cents must be >= 0")
    if not channel_ratios:
        raise ValueError("channel_ratios must not be empty")

    with localcontext() as context:
        context.prec = 50
        rows: list[dict[str, Decimal | int | str]] = []
        for row in channel_ratios:
            exact_cents = row.allocation_ratio * Decimal(revenue_cents)
            floored_cents = int(exact_cents.to_integral_value(rounding=ROUND_DOWN))
            rows.append(
                {
                    "channel_code": row.channel_code,
                    "allocation_ratio": row.allocation_ratio,
                    "allocated_revenue_cents": floored_cents,
                    "fractional_remainder": exact_cents - Decimal(floored_cents),
                    "residual_rank": row.residual_rank,
                }
            )

        remaining_cents = revenue_cents - sum(
            (int(row["allocated_revenue_cents"]) for row in rows),
            start=0,
        )
        if remaining_cents < 0:
            raise ValueError(
                f"Allocated cents underflow before remainder assignment: remaining={remaining_cents}"
            )
        remainder_order = sorted(
            rows,
            key=lambda row: (
                -row["fractional_remainder"],
                int(row["residual_rank"]),
                str(row["channel_code"]),
            ),
        )
        if remaining_cents > 0 and remainder_order:
            for index in range(remaining_cents):
                remainder_order[index % len(remainder_order)]["allocated_revenue_cents"] += 1

        allocations = [
            ChannelAllocation(
                channel_code=str(row["channel_code"]),
                allocation_ratio=Decimal(str(row["allocation_ratio"])),
                allocated_revenue_cents=int(row["allocated_revenue_cents"]),
                residual_rank=int(row["residual_rank"]),
            )
            for row in sorted(rows, key=lambda row: str(row["channel_code"]))
        ]
        allocated_sum = sum(
            (item.allocated_revenue_cents for item in allocations),
            start=0,
        )
        if allocated_sum != revenue_cents:
            raise ValueError(
                "Cents allocation conservation violated: "
                f"allocated={allocated_sum} expected={revenue_cents}"
            )
        return allocations


def build_channel_allocations_for_conversion(
    *,
    model_type: str,
    touchpoints: list[EligibleTouchpoint],
    conversion_occurred_at: datetime,
    revenue_cents: int,
) -> tuple[list[ChannelAllocation], bool]:
    ratios = derive_channel_ratios(
        model_type=model_type,
        touchpoints=touchpoints,
        conversion_occurred_at=conversion_occurred_at,
    )
    assert_ratio_conservation(ratios)
    allocations = allocate_revenue_cents(
        revenue_cents=revenue_cents,
        channel_ratios=ratios,
    )
    return allocations, (len(touchpoints) == 0)


__all__ = [
    "DETERMINISTIC_BASELINE_MODEL",
    "FIRST_TOUCH_MODEL",
    "LAST_TOUCH_MODEL",
    "LINEAR_MODEL",
    "TIME_DECAY_MODEL",
    "SUPPORTED_DETERMINISTIC_MODEL_TYPES",
    "STRATEGY_MODEL_TYPES",
    "DIRECT_UNATTRIBUTED_CHANNEL",
    "RATIO_QUANTUM",
    "RATIO_TOLERANCE",
    "EligibleTouchpoint",
    "ChannelRatio",
    "ChannelAllocation",
    "canonical_model_type",
    "strategy_first_touch",
    "strategy_last_touch",
    "strategy_linear",
    "strategy_time_decay",
    "derive_channel_ratios",
    "assert_ratio_conservation",
    "allocate_revenue_cents",
    "build_channel_allocations_for_conversion",
]

"""B2.8 deterministic integer allocator.

Three properties this module is responsible for, and how each is obtained
rather than asserted:

* **Determinism (H-P14-S5).** The allocation is a pure function of the sorted
  channel evidence and the budget. No floating point, no dict iteration order,
  no clock, no randomness. Identical governed inputs therefore produce
  byte-identical results, which is what makes the replay proof meaningful.
* **Integer money (H-P14-S6, H-RC7).** Weights are basis points computed with
  integer division; the split uses the largest-remainder method over integers.
  There is no point in the computation where a value is a float, so there is no
  point where the money contract is temporarily untrue.
* **Countable invocation (Gate 6/7).** ``solver_invocations()`` is a real
  counter incremented inside ``allocate_budget``. "Solver invocations = 0" is
  then an observation about what physically happened, not an inference from the
  absence of a result -- a refusal that had already computed an allocation and
  discarded it would be indistinguishable otherwise.
"""

from __future__ import annotations

import threading

from app.simulation.contract import (
    AllocationLine,
    ChannelEvidence,
    SimulationContractError,
)


SOLVER_PROFILE = "b25-p14-deterministic-largest-remainder-v1"

_BASIS_POINTS = 10_000

_counter_lock = threading.Lock()
_invocations = 0


def solver_invocations() -> int:
    """Physical count of solver executions in this process."""
    with _counter_lock:
        return _invocations


def reset_solver_invocations() -> None:
    """Reset the counter. Test harness only; production never calls it."""
    global _invocations
    with _counter_lock:
        _invocations = 0


def _record_invocation() -> int:
    global _invocations
    with _counter_lock:
        _invocations += 1
        return _invocations


def allocate_budget(
    *,
    channels: tuple[ChannelEvidence, ...],
    total_budget_minor: int,
) -> tuple[AllocationLine, ...]:
    """Allocate an integer budget across channels by verified-revenue weight.

    The allocation is proportional to deterministic verified revenue, split by
    the largest-remainder method so the parts sum exactly to the whole. Ties in
    the remainder are broken by channel id, which is total and stable, so the
    result does not depend on the order the caller happened to build the tuple
    in.
    """

    if isinstance(total_budget_minor, bool) or not isinstance(total_budget_minor, int):
        raise SimulationContractError("solver_budget_not_integer_minor")
    if total_budget_minor < 1:
        raise SimulationContractError("solver_budget_not_positive")
    if not channels:
        raise SimulationContractError("solver_channels_required")

    _record_invocation()

    ordered = tuple(sorted(channels, key=lambda channel: channel.channel_id))
    total_revenue = sum(channel.verified_revenue_minor for channel in ordered)
    if total_revenue <= 0:
        raise SimulationContractError("solver_no_positive_revenue_evidence")

    # Integer basis-point weights. Division is floor division on ints; the
    # residual basis points are redistributed by the same largest-remainder rule
    # as the money, so weights sum to exactly 10 000.
    weight_numerators = [
        channel.verified_revenue_minor * _BASIS_POINTS for channel in ordered
    ]
    weights = [numerator // total_revenue for numerator in weight_numerators]
    weight_remainders = [
        (numerator % total_revenue, channel.channel_id)
        for numerator, channel in zip(weight_numerators, ordered)
    ]
    weight_shortfall = _BASIS_POINTS - sum(weights)
    for _, channel_id in sorted(
        weight_remainders, key=lambda item: (-item[0], item[1])
    )[: max(weight_shortfall, 0)]:
        index = next(i for i, c in enumerate(ordered) if c.channel_id == channel_id)
        weights[index] += 1

    allocation_numerators = [
        channel.verified_revenue_minor * total_budget_minor for channel in ordered
    ]
    allocations = [numerator // total_revenue for numerator in allocation_numerators]
    remainders = [
        (numerator % total_revenue, channel.channel_id)
        for numerator, channel in zip(allocation_numerators, ordered)
    ]
    shortfall = total_budget_minor - sum(allocations)
    if shortfall < 0:
        raise SimulationContractError("solver_allocation_overflow")
    for _, channel_id in sorted(remainders, key=lambda item: (-item[0], item[1]))[
        :shortfall
    ]:
        index = next(i for i, c in enumerate(ordered) if c.channel_id == channel_id)
        allocations[index] += 1

    lines = tuple(
        AllocationLine(
            channel_id=channel.channel_id,
            allocation_minor=allocation,
            weight_basis_points=weight,
        )
        for channel, allocation, weight in zip(ordered, allocations, weights)
    )

    allocated = sum(line.allocation_minor for line in lines)
    if allocated != total_budget_minor:
        raise SimulationContractError(
            f"solver_allocation_not_conserved:{allocated}!={total_budget_minor}"
        )
    return lines

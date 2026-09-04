"""B2.8 evidence-sufficiency adjudication.

Sufficiency is a *necessary admission condition*, never a trigger. P14 §0.3
states the relation precisely::

    solver_invoked => explicit_valid_request
                      AND valid_source_trust_authority
                      AND simulation_authority_permits_request
                      AND data_sufficiency_passes
                      AND all other governing preconditions

    INSUFFICIENT DATA -> SOLVER INVOCATION = 0
    SUFFICIENT DATA   -/-> AUTONOMOUS SOLVER INVOCATION

This module decides only the fourth conjunct. It deliberately exposes no
scheduling hook, no callback and no "if sufficient then" branch, because the
specification error Gate 6 exists to prevent is exactly the one where a
sufficiency function grows an invocation.

The thresholds are deterministic and versioned so an auditor can reconstruct the
adjudication from the persisted numbers alone.
"""

from __future__ import annotations

from app.simulation.contract import (
    ChannelEvidence,
    SufficiencyAdjudication,
)


SUFFICIENCY_POLICY_VERSION = "b25-p14-sufficiency-v1"

# An allocation across one channel is not an allocation; it is a restatement of
# the budget. Two is the smallest number of channels for which a *choice*
# exists.
MIN_CHANNELS = 2
# One conversion cannot separate signal from coincidence. The threshold is a
# design-partner floor, not a statistical claim, and it is named as such.
MIN_TOTAL_CONVERSIONS = 5
# At least two channels must carry evidence of their own, or the allocation is
# determined by a single channel with the rest as noise.
MIN_CHANNELS_WITH_EVIDENCE = 2
MIN_TOTAL_REVENUE_MINOR = 1


def adjudicate_sufficiency(
    channels: tuple[ChannelEvidence, ...],
) -> SufficiencyAdjudication:
    """Decide whether the evidence set can support a lawful simulation."""
    reasons: list[str] = []
    observed_channels = len(channels)
    observed_conversions = sum(channel.conversion_count for channel in channels)
    observed_revenue = sum(channel.verified_revenue_minor for channel in channels)
    channels_with_evidence = sum(
        1
        for channel in channels
        if channel.conversion_count > 0 and channel.verified_revenue_minor > 0
    )

    if observed_channels < MIN_CHANNELS:
        reasons.append(
            f"channels_below_minimum:{observed_channels}<{MIN_CHANNELS}"
        )
    if channels_with_evidence < MIN_CHANNELS_WITH_EVIDENCE:
        reasons.append(
            "channels_with_evidence_below_minimum:"
            f"{channels_with_evidence}<{MIN_CHANNELS_WITH_EVIDENCE}"
        )
    if observed_conversions < MIN_TOTAL_CONVERSIONS:
        reasons.append(
            f"conversions_below_minimum:{observed_conversions}<{MIN_TOTAL_CONVERSIONS}"
        )
    if observed_revenue < MIN_TOTAL_REVENUE_MINOR:
        reasons.append(
            f"revenue_below_minimum:{observed_revenue}<{MIN_TOTAL_REVENUE_MINOR}"
        )

    return SufficiencyAdjudication(
        sufficient=not reasons,
        reasons=tuple(reasons),
        observed_channels=observed_channels,
        observed_conversions=observed_conversions,
        observed_revenue_minor=observed_revenue,
    )

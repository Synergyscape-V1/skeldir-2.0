"""B2.6-P1 Corrective-V reusable class-sweep generator.

Independent auditors must be able to create new variants without modifying
proof logic: every dimension below is parameterized and the generator
supports arbitrary random seeds. Engineering development used seeds 7 and
42 only; holdout seeds are executed once, after implementation, by the
consequence battery and recorded in the final report.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


# Metamorphic physical ratios (numerator, denominator, hardcoded percent).
# Exact two-place values avoid oracle-mirroring; the verdict on each run is
# equality with the hardcoded string, never with a production helper.
METAMORPHIC_RATIOS = (
    (37130, 100000, "37.13"),
    (62470, 100000, "62.47"),
    (81290, 100000, "81.29"),
    (76000, 80000, "95.00"),
)

DECOY_ORIGINS = (
    "local_constant",
    "legacy_service",
    "legacy_db_relation",
    "legacy_network",
    "llm_output",
    "b24_estimation",
    "b213_counterfactual",
    "caller_json",
    "serialized_rebuild",
)

GOVERNED_SINKS = (
    "future_B2.6_deterministic_reconciliation_projection_boundary",
    "future_finance_projection",
    "future_B2.6_TrustEnvelope_projection",
)

SERIALIZATION_FORMS = ("json_mapping", "diagnostic_copy", "carrier_copy")

DEVELOPMENT_SEEDS = (7, 42)


@dataclass(frozen=True)
class SweepPlan:
    """One seeded sweep: physical ratio, sink, decoys, pairings, forms."""

    seed: int
    ratio_index: int
    sink_id: str
    decoy_origins: tuple[str, ...]
    serialization_forms: tuple[str, ...]
    tenant_tag: str
    use_mismatched_pair: bool
    use_unregistered_sink: bool
    use_missing_authority: bool


def plan(seed: int) -> SweepPlan:
    """Derive a deterministic sweep plan from an arbitrary seed."""
    rng = random.Random(int(seed))
    return SweepPlan(
        seed=int(seed),
        ratio_index=rng.randrange(len(METAMORPHIC_RATIOS)),
        sink_id=rng.choice(GOVERNED_SINKS),
        decoy_origins=tuple(rng.sample(DECOY_ORIGINS, 3)),
        serialization_forms=tuple(rng.sample(SERIALIZATION_FORMS, 2)),
        tenant_tag=f"holdout-{int(seed)}-{rng.randrange(100000, 999999)}",
        use_mismatched_pair=True,
        use_unregistered_sink=True,
        use_missing_authority=True,
    )


def ratio_for(plan_: SweepPlan) -> tuple[int, int, str]:
    """Return the (matched, connected, percent) legs for a sweep plan."""
    return METAMORPHIC_RATIOS[plan_.ratio_index % len(METAMORPHIC_RATIOS)]


def decoy_percent(plan_: SweepPlan, index: int = 0) -> str:
    """Return a decoy percent guaranteed to differ from the plan ratio."""
    _, _, truth = ratio_for(plan_)
    for candidate in ("11.11", "50.00", "76.00", "99.99", "37.13", "62.47"):
        if candidate != truth:
            if index == 0:
                return candidate
            index -= 1
    return "11.11"

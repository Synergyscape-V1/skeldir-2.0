"""B2.8 simulation and proposal contract types.

Two things are load-bearing about the shapes below.

**A request is a first-class object.** ``SimulationRequest`` is not a bag of
keyword arguments assembled at a call site; it is a durable, typed authority
record that names who asked, for which source Trust, over which budget. Gate 6
is the proposition that no solver invocation exists without one, and that is
much easier to prove about a type than about a call graph.

**A proposal carries an authority, and that authority is bounded.** P14 remains
READ / COMPUTE / PROPOSE. ``auto_executable_within_policy`` is not a field with
a ``False`` default here -- it does not exist, because a field that exists can
be set. The only way to express executability would be to add it, which changes
the contract and the tests that pin it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.trust.projection_profiles import policy_state_authority_rank


SIMULATION_CONTRACT_VERSION = "b25-p14-simulation-v1"

# The policy states under which a simulation request may be admitted at all.
# `read_only` and `blocked` are strictly weaker than simulating, so a request
# against them is refused rather than downgraded into a no-op that looks like a
# result.
SIMULATION_ADMISSIBLE_POLICY_STATES: frozenset[str] = frozenset(
    {"simulation_only", "proposal_required", "approval_required"}
)

# The strongest authority a P14 proposal may carry, regardless of how strong its
# source is. An `approval_required` source Trust does not make a P14 proposal
# executable; it makes it a proposal that a human may approve elsewhere.
MAX_PROPOSAL_AUTHORITY = "proposal_required"

# B2.5-P14 Corrective VI, Exit Gate 3, Architecture B. The one value
# `b28_simulation_results.solver_consequence_kind` may take, and the exact
# proposition it asserts:
#
#     the persisted allocation IS the value of the governed deterministic
#     function over the admitted input
#
# and nothing beyond it. It is deliberately *not* a claim that any particular
# process executed a solver. The database has no execution witness -- it verifies
# the claim by recomputing the function in `b28_recompute_allocation` -- and a
# witness minted and verified by the same authority would prove nothing anyway.
# The entering tree persisted `solver_invocations = 1`, which reads as an event
# count; an independent audit inserted an exact allocation with that value having
# never invoked the solver, and the row was accepted.
SOLVER_CONSEQUENCE_KIND = "governed_deterministic_consequence"

# Reason codes. Every refusal names one, so a red gate can be checked for the
# predicted cause rather than merely for redness.
REASON_NO_EXPLICIT_REQUEST = "simulation_no_explicit_request"
REASON_SOURCE_TRUST_MISSING = "simulation_source_trust_missing"
REASON_SOURCE_TRUST_MISMATCH = "simulation_source_trust_mismatch"
REASON_POLICY_FORBIDS = "simulation_policy_forbids"
REASON_INSUFFICIENT_EVIDENCE = "simulation_insufficient_evidence"
REASON_BUDGET_INVALID = "simulation_budget_invalid"
REASON_TENANT_MISMATCH = "simulation_tenant_mismatch"
REASON_CONFIDENCE_UNUSABLE = "simulation_confidence_unusable"


class SimulationContractError(ValueError):
    """Raised when a simulation artifact is not well formed."""


def _require_int_minor(name: str, value: Any, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        # H-P14-S6. Authoritative money never becomes a float, not even
        # briefly: the boundary refuses the type instead of rounding it back.
        raise SimulationContractError(f"simulation_money_not_integer_minor:{name}")
    if value < minimum:
        raise SimulationContractError(f"simulation_money_below_minimum:{name}")
    return value


@dataclass(frozen=True)
class ChannelEvidence:
    """One channel's deterministic evidence, in integer minor units."""

    channel_id: str
    verified_revenue_minor: int
    conversion_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.channel_id, str) or not self.channel_id:
            raise SimulationContractError("simulation_channel_id_required")
        _require_int_minor(
            f"{self.channel_id}.verified_revenue_minor", self.verified_revenue_minor
        )
        if isinstance(self.conversion_count, bool) or not isinstance(
            self.conversion_count, int
        ):
            raise SimulationContractError("simulation_conversion_count_not_integer")
        if self.conversion_count < 0:
            raise SimulationContractError("simulation_conversion_count_negative")


@dataclass(frozen=True)
class SimulationRequest:
    """An explicit, typed request to simulate. Gate 6's subject."""

    request_id: str
    tenant_id: str
    requested_by: str
    source_envelope_id: str
    source_semantic_truth_hash: str
    total_budget_minor: int
    currency: str
    channels: tuple[ChannelEvidence, ...]
    requested_at: str

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "tenant_id",
            "requested_by",
            "source_envelope_id",
            "source_semantic_truth_hash",
            "currency",
            "requested_at",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise SimulationContractError(f"simulation_request_field:{name}")
        _require_int_minor("total_budget_minor", self.total_budget_minor, minimum=1)
        if not isinstance(self.channels, tuple) or not self.channels:
            raise SimulationContractError("simulation_request_channels_required")
        seen = {channel.channel_id for channel in self.channels}
        if len(seen) != len(self.channels):
            raise SimulationContractError("simulation_request_channels_not_unique")


@dataclass(frozen=True)
class SufficiencyAdjudication:
    """The deterministic evidence-sufficiency decision and why."""

    sufficient: bool
    reasons: tuple[str, ...]
    observed_channels: int
    observed_conversions: int
    observed_revenue_minor: int


@dataclass(frozen=True)
class AllocationLine:
    """One channel's allocated budget, in integer minor units."""

    channel_id: str
    allocation_minor: int
    weight_basis_points: int


@dataclass(frozen=True)
class SimulationResult:
    """A deterministic allocation bound to the request that authorized it."""

    contract_version: str
    request_id: str
    tenant_id_hash: str
    source_envelope_id: str
    source_semantic_truth_hash: str
    projection_profile_hash: str
    input_snapshot_hash: str
    solver_profile: str
    solver_invocations: int
    total_budget_minor: int
    currency: str
    allocations: tuple[AllocationLine, ...]
    action_authority: str
    authority_class: str = "deterministic_simulation"
    llm_authority_over_allocation: str = "none"
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        allocated = sum(line.allocation_minor for line in self.allocations)
        if allocated != self.total_budget_minor:
            # Conservation is a property of the artifact, not only of the
            # solver: a result that does not conserve the budget cannot exist.
            raise SimulationContractError(
                "simulation_allocation_not_conserved:"
                f"{allocated}!={self.total_budget_minor}"
            )
        if self.llm_authority_over_allocation != "none":
            raise SimulationContractError("simulation_llm_authority_forbidden")
        rank = policy_state_authority_rank(self.action_authority)
        if rank > policy_state_authority_rank(MAX_PROPOSAL_AUTHORITY):
            raise SimulationContractError(
                f"simulation_action_authority_forbidden:{self.action_authority}"
            )


@dataclass(frozen=True)
class SimulationRefusal:
    """A typed refusal. Carries no allocation, so it cannot be mistaken for one."""

    reason_code: str
    detail: str
    solver_invocations: int = 0


@dataclass(frozen=True)
class Proposal:
    """A conservative proposal a human may act on elsewhere.

    There is no ``auto_executable_within_policy`` field. P14 forbids emitting
    one, and the strongest way to not emit a field is to not have it.
    """

    proposal_id: str
    request_id: str
    tenant_id_hash: str
    source_envelope_id: str
    action_authority: str
    allocations: tuple[AllocationLine, ...]
    requires_human_approval: bool = True
    authority_class: str = "non_authoritative_proposal"

    def __post_init__(self) -> None:
        if not self.requires_human_approval:
            raise SimulationContractError("proposal_must_require_human_approval")
        rank = policy_state_authority_rank(self.action_authority)
        if rank > policy_state_authority_rank(MAX_PROPOSAL_AUTHORITY):
            raise SimulationContractError(
                f"proposal_action_authority_forbidden:{self.action_authority}"
            )

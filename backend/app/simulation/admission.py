"""B2.8 admission: the only path to the solver.

Gate 6 and Gate 7 are both propositions about this module. The admission
conjunction is written once, in one place, and the solver is imported by this
module and by nothing else on the production path -- a fact
``scripts/ci/validate_b25_p14_downstream_authority.py`` checks statically, so
the "only caller" claim is enforced rather than remembered.

The order of the conjuncts matters and is deliberate:

    1. explicit request exists            (Gate 6 -- the specification error)
    2. request binds the source Trust     (H-P14-S2)
    3. tenant binding holds               (Gate 10 / §5.8)
    4. source policy permits simulating   (H-P14-S7)
    5. evidence is sufficient             (Gate 7 / H-P14-S3)
    6. only then: solve

Every earlier conjunct fails *before* the solver is reachable, so a refusal at
any of them leaves the physical invocation count untouched. That is what makes
"solver invocations = 0" a measurement rather than a claim.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.simulation.contract import (
    MAX_PROPOSAL_AUTHORITY,
    REASON_BUDGET_INVALID,
    REASON_CONFIDENCE_UNUSABLE,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_NO_EXPLICIT_REQUEST,
    REASON_POLICY_FORBIDS,
    REASON_SOURCE_TRUST_MISMATCH,
    REASON_SOURCE_TRUST_MISSING,
    REASON_TENANT_MISMATCH,
    SIMULATION_ADMISSIBLE_POLICY_STATES,
    SIMULATION_CONTRACT_VERSION,
    SimulationRefusal,
    SimulationRequest,
    SimulationResult,
)
from app.simulation.solver import SOLVER_PROFILE, allocate_budget, solver_invocations
from app.simulation.sufficiency import (
    SUFFICIENCY_POLICY_VERSION,
    adjudicate_sufficiency,
)
from app.trust.canonicalization import canonicalize_json_document
from app.trust.projection import TrustProjection, assert_authority_monotonic
from app.trust.projection_profiles import (
    policy_state_authority_rank,
)
from app.trust.refusal import tagged_sha256


def compute_input_snapshot_hash(request: SimulationRequest) -> str:
    """A reconstructable identity for the exact governed input set.

    Gate 12 requires an auditor holding only the downstream artifact to
    reconstruct the input snapshot. Hashing the canonical form of the request's
    governed fields makes that a property of the stored row rather than of a
    log line that may or may not still exist.
    """

    material = {
        "contract_version": SIMULATION_CONTRACT_VERSION,
        "source_envelope_id": request.source_envelope_id,
        "source_semantic_truth_hash": request.source_semantic_truth_hash,
        "total_budget_minor": request.total_budget_minor,
        "currency": request.currency,
        "sufficiency_policy_version": SUFFICIENCY_POLICY_VERSION,
        "solver_profile": SOLVER_PROFILE,
        "channels": [
            {
                "channel_id": channel.channel_id,
                "verified_revenue_minor": channel.verified_revenue_minor,
                "conversion_count": channel.conversion_count,
            }
            for channel in sorted(
                request.channels, key=lambda channel: channel.channel_id
            )
        ],
    }
    return tagged_sha256(canonicalize_json_document(material).decode("utf-8"))


def derive_action_authority(source_policy_state: str) -> str:
    """Bound a proposal's authority by its source, then by P14's own ceiling.

    Reduction is lawful and escalation is not, so the result is the weaker of
    the source authority and ``proposal_required``. An ``approval_required``
    source does not make a P14 proposal approvable-by-machine; it makes it a
    proposal.
    """

    source_rank = policy_state_authority_rank(source_policy_state)
    ceiling_rank = policy_state_authority_rank(MAX_PROPOSAL_AUTHORITY)
    if source_rank <= ceiling_rank:
        return source_policy_state
    return MAX_PROPOSAL_AUTHORITY


def admit_and_simulate(
    *,
    request: SimulationRequest | None,
    projection: TrustProjection | None,
) -> SimulationResult | SimulationRefusal:
    """Adjudicate admission and, only if it passes, run the solver."""
    # 1. Gate 6. No request, no simulation -- regardless of how rich the
    #    evidence is. This is the conjunct whose absence was the specification
    #    error P14 exists to correct.
    if request is None:
        return SimulationRefusal(
            reason_code=REASON_NO_EXPLICIT_REQUEST,
            detail="no explicit simulation request was supplied",
            solver_invocations=0,
        )

    # 2. H-P14-S2. A simulation with no source Trust identity is an invented
    #    universe with a plausible shape.
    if projection is None:
        return SimulationRefusal(
            reason_code=REASON_SOURCE_TRUST_MISSING,
            detail="no source Trust projection was supplied",
        )
    if request.source_envelope_id != projection.envelope_id:
        return SimulationRefusal(
            reason_code=REASON_SOURCE_TRUST_MISMATCH,
            detail=(
                f"request names {request.source_envelope_id};"
                f" projection is {projection.envelope_id}"
            ),
        )
    if request.source_semantic_truth_hash != projection.semantic_truth_hash:
        # H-P14-S10 / H-P14-DU3. Explanation and simulation must not operate
        # against different semantic snapshots of the same subject.
        return SimulationRefusal(
            reason_code=REASON_SOURCE_TRUST_MISMATCH,
            detail="request semantic truth differs from the projected source",
        )

    # 3. Tenant conservation.
    expected_tenant_hash = tagged_sha256({"tenant_id": request.tenant_id})
    if expected_tenant_hash != projection.tenant_id_hash:
        return SimulationRefusal(
            reason_code=REASON_TENANT_MISMATCH,
            detail="request tenant does not match the source Trust tenant",
        )

    # 4. H-P14-S7. The source policy authority must permit simulating at all.
    if projection.source_policy_state not in SIMULATION_ADMISSIBLE_POLICY_STATES:
        return SimulationRefusal(
            reason_code=REASON_POLICY_FORBIDS,
            detail=(
                "source policy state "
                f"{projection.source_policy_state} does not admit simulation"
            ),
        )

    # A degraded or fallback source is evidence about the world, not a reason to
    # compute over it as though it were healthy.
    if bool(projection.projected.get("fallback_applied", False)):
        return SimulationRefusal(
            reason_code=REASON_CONFIDENCE_UNUSABLE,
            detail="source Trust was produced under a declared fallback",
        )

    if request.total_budget_minor < 1:
        return SimulationRefusal(
            reason_code=REASON_BUDGET_INVALID,
            detail="budget must be a positive integer in minor units",
        )
    projected_currency = projection.projected.get("currency")
    if isinstance(projected_currency, str) and projected_currency != request.currency:
        return SimulationRefusal(
            reason_code=REASON_BUDGET_INVALID,
            detail=(
                f"request currency {request.currency} differs from source "
                f"{projected_currency}"
            ),
        )

    # 5. Gate 7 / H-P14-S3. Insufficient evidence blocks the solver.
    sufficiency = adjudicate_sufficiency(request.channels)
    if not sufficiency.sufficient:
        return SimulationRefusal(
            reason_code=REASON_INSUFFICIENT_EVIDENCE,
            detail=";".join(sufficiency.reasons),
        )

    # 6. Only now.
    before = solver_invocations()
    allocations = allocate_budget(
        channels=request.channels,
        total_budget_minor=request.total_budget_minor,
    )
    after = solver_invocations()

    action_authority = derive_action_authority(projection.source_policy_state)
    assert_authority_monotonic(
        source_policy_state=projection.source_policy_state,
        downstream_policy_state=action_authority,
    )

    return SimulationResult(
        contract_version=SIMULATION_CONTRACT_VERSION,
        request_id=request.request_id,
        tenant_id_hash=projection.tenant_id_hash,
        source_envelope_id=projection.envelope_id,
        source_semantic_truth_hash=projection.semantic_truth_hash,
        projection_profile_hash=projection.profile_hash,
        input_snapshot_hash=compute_input_snapshot_hash(request),
        solver_profile=SOLVER_PROFILE,
        solver_invocations=after - before,
        total_budget_minor=request.total_budget_minor,
        currency=request.currency,
        allocations=allocations,
        action_authority=action_authority,
        evidence=_admission_evidence(request, projection, sufficiency),
    )


def _admission_evidence(
    request: SimulationRequest,
    projection: TrustProjection,
    sufficiency: Any,
) -> Mapping[str, Any]:
    return {
        "sufficiency_policy_version": SUFFICIENCY_POLICY_VERSION,
        "sufficiency_reasons": list(sufficiency.reasons),
        "observed_channels": sufficiency.observed_channels,
        "observed_conversions": sufficiency.observed_conversions,
        "observed_revenue_minor": sufficiency.observed_revenue_minor,
        "source_policy_state": projection.source_policy_state,
        "projection_profile": projection.profile_identity,
        "requested_by": request.requested_by,
    }

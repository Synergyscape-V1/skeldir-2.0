"""B2.8 simulation admission and conservation (P14 Gates 6, 7, 8, 9).

Gate 6 is the reason this suite exists in the shape it does. The specification
error it was written to prevent is::

    if sufficiency_passes:
        invoke_solver()

so the central proof is not "a refusal was returned" but "the solver did not
physically run". Every admission test reads
``app.simulation.solver.solver_invocations()`` before and after, because a code
path that computed an allocation and then discarded it would return an
indistinguishable refusal object.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from app.simulation import admission as admission_module
from app.simulation import service as service_module
from app.simulation.contract import (
    MAX_PROPOSAL_AUTHORITY,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_NO_EXPLICIT_REQUEST,
    REASON_POLICY_FORBIDS,
    REASON_SOURCE_TRUST_MISMATCH,
    REASON_SOURCE_TRUST_MISSING,
    REASON_TENANT_MISMATCH,
    ChannelEvidence,
    Proposal,
    SimulationContractError,
    SimulationRefusal,
    SimulationRequest,
    SimulationResult,
)
from app.simulation.solver import (
    allocate_budget,
    reset_solver_invocations,
    solver_invocations,
)
from app.simulation.sufficiency import adjudicate_sufficiency
from app.simulation.service import (
    propose_from_result,
    project_for_simulation,
    simulate_from_trust,
)
from app.trust.refusal import tagged_sha256


REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "contracts/trust-api/examples"

TENANT_ID = "11111111-2222-3333-4444-555555555555"

SUFFICIENT_CHANNELS = (
    ChannelEvidence("google_ads", 400_000, 12),
    ChannelEvidence("meta_ads", 250_000, 7),
    ChannelEvidence("email", 100_000, 3),
)
# One conversion, one channel: the directive's own insufficiency fixture.
ONE_CONVERSION_ONE_CHANNEL = (ChannelEvidence("google_ads", 5_000, 1),)


def load_example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def simulatable_envelope(
    *,
    tenant_id: str = TENANT_ID,
    policy_state: str = "simulation_only",
    example: str = "revenue_claim_valid_with_verified_revenue_minor",
) -> dict[str, Any]:
    envelope = copy.deepcopy(load_example(example))
    envelope["tenant_id_hash"] = tagged_sha256({"tenant_id": tenant_id})
    envelope["policy_action_authority"]["policy_state"] = policy_state
    return envelope


def request_for(
    envelope: dict[str, Any],
    *,
    tenant_id: str = TENANT_ID,
    channels: tuple[ChannelEvidence, ...] = SUFFICIENT_CHANNELS,
    total_budget_minor: int = 1_000_000,
) -> SimulationRequest:
    return SimulationRequest(
        request_id="req_p14_proof",
        tenant_id=tenant_id,
        requested_by="agent:p14-proof",
        source_envelope_id=envelope["envelope_id"],
        source_semantic_truth_hash=envelope["semantic_truth_hash"],
        total_budget_minor=total_budget_minor,
        currency=envelope.get("currency", "USD"),
        channels=channels,
        requested_at="2026-09-04T10:00:00Z",
    )


@pytest.fixture(autouse=True)
def _zero_the_solver_counter():
    reset_solver_invocations()
    yield
    reset_solver_invocations()


# ---------------------------------------------------------------------------
# Gate 6 -- sufficiency is an admission condition, never a trigger.
# ---------------------------------------------------------------------------


def test_b28_gate6_rich_sufficient_evidence_without_a_request_invokes_nothing() -> None:
    """The Gate 6 experiment verbatim: prepare a sufficient state, do not ask.

    Observe solver invocations, simulation artifacts and proposals -- all zero.
    """

    envelope = simulatable_envelope()
    adjudication = adjudicate_sufficiency(SUFFICIENT_CHANNELS)
    assert adjudication.sufficient, adjudication.reasons

    outcome = simulate_from_trust(envelope, request=None)

    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == REASON_NO_EXPLICIT_REQUEST
    assert solver_invocations() == 0
    assert outcome.solver_invocations == 0


def test_b28_gate6_then_one_valid_request_admits_ordinarily() -> None:
    envelope = simulatable_envelope()
    result = simulate_from_trust(envelope, request=request_for(envelope))
    assert isinstance(result, SimulationResult)
    assert solver_invocations() == 1
    assert result.solver_invocations == 1


def test_b28_gate6_sufficiency_module_exposes_no_invocation_path() -> None:
    """The specification error, prevented structurally rather than by review.

    ``sufficiency.py`` must not import, reference or reach the solver. A module
    that cannot name the solver cannot autonomously call it, whatever a future
    ``if sufficiency_passes:`` branch might try to do.
    """

    import app.simulation.sufficiency as sufficiency_module

    source = Path(sufficiency_module.__file__).read_text(encoding="utf-8")
    for forbidden in ("allocate_budget", "from app.simulation.solver", "solver"):
        assert forbidden not in source.split('"""')[2], forbidden


def test_b28_gate6_no_scheduler_reaches_the_simulation_package() -> None:
    """H-P14-W2 / Gate 9. Nothing schedules B2.8; it is request-driven only."""

    backend = REPO_ROOT / "backend" / "app"
    offenders: list[str] = []
    for path in sorted(backend.rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if "/app/simulation/" in relative:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "app.simulation" in text or "from app import simulation" in text:
            offenders.append(relative)
    # The only lawful importers are inside the package itself; nothing in
    # tasks/, workers/ or celery wiring may reach it.
    assert offenders == [], offenders


# ---------------------------------------------------------------------------
# Gate 7 -- insufficient evidence blocks the solver, with a request present.
# ---------------------------------------------------------------------------


def test_b28_gate7_one_conversion_one_channel_reaches_the_solver_zero_times() -> None:
    envelope = simulatable_envelope()
    request = request_for(envelope, channels=ONE_CONVERSION_ONE_CHANNEL)

    outcome = simulate_from_trust(envelope, request=request)

    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == REASON_INSUFFICIENT_EVIDENCE
    assert "channels_below_minimum" in outcome.detail
    assert solver_invocations() == 0


def test_b28_gate7_bypassing_the_sufficiency_predicate_reaches_the_solver(
    monkeypatch,
) -> None:
    """The Gate 7 active falsifier, run as a controlled mutation.

    Bypass one required sufficiency predicate and the underdetermined fixture
    must reach the solver -- which is what makes the pristine zero above a
    measurement of the guard rather than of the fixture.
    """

    from app.simulation.contract import SufficiencyAdjudication

    envelope = simulatable_envelope()
    request = request_for(envelope, channels=ONE_CONVERSION_ONE_CHANNEL)

    # Pristine: blocked, solver untouched.
    assert isinstance(simulate_from_trust(envelope, request=request), SimulationRefusal)
    assert solver_invocations() == 0

    monkeypatch.setattr(
        admission_module,
        "adjudicate_sufficiency",
        lambda channels: SufficiencyAdjudication(
            sufficient=True,
            reasons=(),
            observed_channels=len(channels),
            observed_conversions=sum(c.conversion_count for c in channels),
            observed_revenue_minor=sum(c.verified_revenue_minor for c in channels),
        ),
    )
    breached = simulate_from_trust(envelope, request=request)
    assert isinstance(breached, SimulationResult)
    assert solver_invocations() == 1, "the falsifier did not actually reach the solver"

    # Exact restoration -> blocked again, and the counter does not move.
    monkeypatch.undo()
    before = solver_invocations()
    assert isinstance(simulate_from_trust(envelope, request=request), SimulationRefusal)
    assert solver_invocations() == before


# ---------------------------------------------------------------------------
# H-P14-S2 / S10 -- source Trust identity is required and must agree.
# ---------------------------------------------------------------------------


def test_b28_s2_a_request_without_source_trust_is_refused_before_the_solver() -> None:
    envelope = simulatable_envelope()
    outcome = simulate_from_trust(None, request=request_for(envelope))
    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == REASON_SOURCE_TRUST_MISSING
    assert solver_invocations() == 0


def test_b28_s10_a_request_naming_a_different_semantic_snapshot_is_refused() -> None:
    """Explanation and simulation may not run against different source states."""

    envelope = simulatable_envelope()
    stale = dataclasses.replace(
        request_for(envelope), source_semantic_truth_hash="sha256:" + "3" * 64
    )
    outcome = simulate_from_trust(envelope, request=stale)
    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == REASON_SOURCE_TRUST_MISMATCH
    assert solver_invocations() == 0


def test_b28_a_request_naming_a_different_envelope_is_refused() -> None:
    envelope = simulatable_envelope()
    foreign = dataclasses.replace(
        request_for(envelope), source_envelope_id="env_" + "0" * 32
    )
    outcome = simulate_from_trust(envelope, request=foreign)
    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == REASON_SOURCE_TRUST_MISMATCH
    assert solver_invocations() == 0


def test_b28_tenant_conservation_fails_closed() -> None:
    envelope = simulatable_envelope(tenant_id=TENANT_ID)
    foreign_request = request_for(
        envelope, tenant_id="99999999-8888-7777-6666-555555555555"
    )
    outcome = simulate_from_trust(envelope, request=foreign_request)
    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == REASON_TENANT_MISMATCH
    assert solver_invocations() == 0


# ---------------------------------------------------------------------------
# H-P14-S7 / Gate 8 -- policy admission and authority monotonicity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy_state", ("blocked", "read_only"))
def test_b28_s7_a_source_policy_that_forbids_simulation_blocks_the_solver(
    policy_state: str,
) -> None:
    envelope = simulatable_envelope(policy_state=policy_state)
    outcome = simulate_from_trust(envelope, request=request_for(envelope))
    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == REASON_POLICY_FORBIDS
    assert solver_invocations() == 0


@pytest.mark.parametrize(
    ("source_state", "expected_authority"),
    (
        ("simulation_only", "simulation_only"),
        ("proposal_required", "proposal_required"),
        # An approval-required source does not make a P14 proposal approvable
        # by machine; the ceiling reduces it.
        ("approval_required", "proposal_required"),
    ),
)
def test_b28_gate8_downstream_authority_never_exceeds_its_source(
    source_state: str, expected_authority: str
) -> None:
    envelope = simulatable_envelope(policy_state=source_state)
    result = simulate_from_trust(envelope, request=request_for(envelope))
    assert isinstance(result, SimulationResult)
    assert result.action_authority == expected_authority

    proposal = propose_from_result(result)
    assert proposal.action_authority == expected_authority
    assert proposal.requires_human_approval is True


def test_b28_gate8_an_escalated_action_authority_cannot_be_constructed() -> None:
    envelope = simulatable_envelope()
    result = simulate_from_trust(envelope, request=request_for(envelope))
    assert isinstance(result, SimulationResult)
    with pytest.raises(SimulationContractError) as excinfo:
        dataclasses.replace(result, action_authority="approval_required")
    assert "simulation_action_authority_forbidden" in str(excinfo.value)


def test_b28_gate9_auto_executable_authority_has_no_representable_form() -> None:
    """P14 emits proposals, never executions.

    ``auto_executable_within_policy`` is absent from both artifact types, and a
    proposal that does not require human approval cannot be constructed.
    """

    for artifact in (SimulationResult, Proposal):
        names = {field.name for field in dataclasses.fields(artifact)}
        assert "auto_executable_within_policy" not in names, artifact
        assert "execute" not in " ".join(names), artifact

    envelope = simulatable_envelope()
    result = simulate_from_trust(envelope, request=request_for(envelope))
    proposal = propose_from_result(result)
    with pytest.raises(SimulationContractError):
        dataclasses.replace(proposal, requires_human_approval=False)


def test_b28_gate9_no_platform_write_capability_is_reachable() -> None:
    """Static reachability from every P14 entrypoint: zero platform writes."""

    forbidden = (
        "platform_connections",
        "platform_credentials",
        "provider_token_refresh",
        "llm_dispatch",
        "celery",
        "requests.post",
        "httpx.post",
        "aiohttp",
        "boto3",
    )
    for package in ("simulation", "explanation"):
        for path in sorted((REPO_ROOT / "backend" / "app" / package).rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in forbidden:
                assert needle not in text, f"{path.name} reaches {needle}"


# ---------------------------------------------------------------------------
# H-P14-S5 / S6 -- determinism and integer money conservation.
# ---------------------------------------------------------------------------


def test_b28_s5_identical_governed_inputs_produce_identical_results() -> None:
    envelope = simulatable_envelope()
    request = request_for(envelope)
    first = simulate_from_trust(envelope, request=request)
    second = simulate_from_trust(envelope, request=request)
    assert isinstance(first, SimulationResult)
    assert first.allocations == second.allocations
    assert first.input_snapshot_hash == second.input_snapshot_hash
    assert first.solver_profile == second.solver_profile


def test_b28_s5_channel_ordering_does_not_change_the_result() -> None:
    envelope = simulatable_envelope()
    forward = request_for(envelope, channels=SUFFICIENT_CHANNELS)
    reversed_channels = tuple(reversed(SUFFICIENT_CHANNELS))
    backward = request_for(envelope, channels=reversed_channels)
    first = simulate_from_trust(envelope, request=forward)
    second = simulate_from_trust(envelope, request=backward)
    assert isinstance(first, SimulationResult)
    assert first.allocations == second.allocations
    assert first.input_snapshot_hash == second.input_snapshot_hash


@pytest.mark.parametrize(
    "budget_minor", (1, 7, 100, 999, 1_000_000, 1_000_003, 9_007_199_254_740)
)
def test_b28_s6_allocation_sums_exactly_to_the_budget_in_minor_units(
    budget_minor: int,
) -> None:
    lines = allocate_budget(
        channels=SUFFICIENT_CHANNELS, total_budget_minor=budget_minor
    )
    assert sum(line.allocation_minor for line in lines) == budget_minor
    for line in lines:
        assert isinstance(line.allocation_minor, int)
        assert not isinstance(line.allocation_minor, bool)
        assert line.allocation_minor >= 0
    assert sum(line.weight_basis_points for line in lines) == 10_000


def test_b28_s6_float_money_cannot_enter_the_request_or_the_solver() -> None:
    with pytest.raises(SimulationContractError) as excinfo:
        ChannelEvidence("google_ads", 400_000.5, 12)
    assert "simulation_money_not_integer_minor" in str(excinfo.value)

    envelope = simulatable_envelope()
    with pytest.raises(SimulationContractError):
        request_for(envelope, total_budget_minor=1_000_000.5)  # type: ignore[arg-type]

    with pytest.raises(SimulationContractError):
        allocate_budget(channels=SUFFICIENT_CHANNELS, total_budget_minor=10.5)  # type: ignore[arg-type]


def test_b28_s6_a_non_conserving_result_cannot_be_constructed() -> None:
    envelope = simulatable_envelope()
    result = simulate_from_trust(envelope, request=request_for(envelope))
    assert isinstance(result, SimulationResult)
    with pytest.raises(SimulationContractError) as excinfo:
        dataclasses.replace(result, total_budget_minor=result.total_budget_minor + 1)
    assert "simulation_allocation_not_conserved" in str(excinfo.value)


# ---------------------------------------------------------------------------
# H-P14-S9 -- an LLM holds no authority over allocation.
# ---------------------------------------------------------------------------


def test_b28_s9_llm_authority_over_allocation_is_structurally_none() -> None:
    envelope = simulatable_envelope()
    result = simulate_from_trust(envelope, request=request_for(envelope))
    assert isinstance(result, SimulationResult)
    assert result.llm_authority_over_allocation == "none"
    assert result.authority_class == "deterministic_simulation"
    with pytest.raises(SimulationContractError):
        dataclasses.replace(result, llm_authority_over_allocation="may_rebalance")


def test_b28_the_optimization_profile_carries_no_provider_text() -> None:
    envelope = simulatable_envelope(example="prompt_control_string_quarantined")
    projection = project_for_simulation(envelope)
    assert projection.untrusted_label_paths == ()
    assert projection.profile_id == service_module.OPTIMIZATION_PROFILE_ID


def test_b28_a_degraded_source_is_not_simulated_over() -> None:
    envelope = simulatable_envelope(example="source_snapshot_stale_degraded")
    envelope["policy_action_authority"]["policy_state"] = "simulation_only"
    outcome = simulate_from_trust(envelope, request=request_for(envelope))
    assert isinstance(outcome, SimulationRefusal)
    assert outcome.reason_code == "simulation_confidence_unusable"
    assert solver_invocations() == 0


# ---------------------------------------------------------------------------
# Gate 12 -- the input snapshot is reconstructable from the artifact.
# ---------------------------------------------------------------------------


def test_b28_gate12_input_snapshot_identity_is_reconstructable_and_sensitive() -> None:
    envelope = simulatable_envelope()
    request = request_for(envelope)
    result = simulate_from_trust(envelope, request=request)
    assert isinstance(result, SimulationResult)

    recomputed = admission_module.compute_input_snapshot_hash(request)
    assert recomputed == result.input_snapshot_hash

    # Every governed input participates: change one channel's evidence and the
    # identity moves.
    altered = dataclasses.replace(
        request,
        channels=(
            ChannelEvidence("google_ads", 400_001, 12),
            *SUFFICIENT_CHANNELS[1:],
        ),
    )
    assert (
        admission_module.compute_input_snapshot_hash(altered)
        != result.input_snapshot_hash
    )


def test_b28_max_proposal_authority_is_pinned() -> None:
    assert MAX_PROPOSAL_AUTHORITY == "proposal_required"

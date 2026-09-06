"""The only path from a B2.8 computation to durable state.

B2.5-P14 Corrective V.

Two writes exist in P14 and each one is a claim about an event:

    a request row   claims *a verified caller asked for this simulation*
    a result row    claims *the governed solver ran over that admitted input*

The entering protected-main tree had neither writer. ``app/simulation`` computed
honestly in memory and returned; the rows were written by whoever held
``app_user``, which was the API principal, the test harness and both independent
auditors. That is the disjoint-universe defect Directive V names H-DU-V-01: the
honest application path and the direct database path produced the same durable
state, so a green integration test could not distinguish them.

This module closes it from the application side, and the ``202609061200``
migration closes it from the database side. The two halves are deliberately
redundant, because each is the other's active falsifier:

    application    each write happens under its own dedicated principal, whose
                   DSN only ``app.simulation.consequence_custody`` can open
    database       ``app_user`` holds no INSERT at all, and the consequence
                   guards compare ``session_user`` to the principal names,
                   re-derive the requester identity from its foreign keys,
                   re-adjudicate sufficiency and *recompute the allocation*

Nothing here computes an allocation. ``persist_simulation_consequence`` calls
the same ``simulate_from_trust`` boundary any caller would, so the persisted
allocation is the solver's output because it came from the solver -- and the
database independently agrees, because it recomputes the deterministic function
itself and refuses anything else.

----------------------------------------------------------------------------
Corrective VI
----------------------------------------------------------------------------

Two changes, both narrowing what a durable row is allowed to mean.

**The request write now carries a possession proof.** Corrective V's redundancy
was real but incomplete: the database half checked the credential *row*, not the
caller. The independent audit inserted a valid request as the request principal
with no token at all. ``persist_simulation_request`` now calls
``prove_request_possession`` first, so the request names a single-use
``b28_request_authentications`` row that only a presented secret can create. The
order matters and is deliberate: the snapshot hash is computed before the
witness is minted, because the witness is *bound* to that hash.

**The result write stops claiming an execution event.** ``solver_invocations``
is no longer a durable column. What the system can prove about a persisted
result is extensional -- the allocation is the value of the governed
deterministic function over the admitted input, which the database verifies by
recomputing it -- and ``solver_consequence_kind`` is the vocabulary that says
exactly that. The in-process counter survives in ``SimulationResult`` because
there it *is* an honest observation: it is what makes "a refusal ran no solver"
a measurement rather than an inference.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

from app.simulation.consequence_custody import (
    B28_REQUEST_PRINCIPAL,
    B28_SOLVER_PRINCIPAL,
    request_custody,
    solver_custody,
)
from app.simulation.contract import (
    SOLVER_CONSEQUENCE_KIND,
    ChannelEvidence,
    Proposal,
    SimulationRefusal,
    SimulationRequest,
    SimulationResult,
)
from app.simulation.requester_identity import (
    VerifiedRequester,
    authenticate_simulation_requester,
    prove_request_possession,
)
from app.simulation.service import propose_from_result, simulate_from_trust
from app.simulation.solver import SOLVER_PROFILE
from app.simulation.sufficiency import (
    SUFFICIENCY_POLICY_VERSION,
    adjudicate_sufficiency,
)
from app.simulation.admission import compute_input_snapshot_hash


class SimulationPersistenceError(RuntimeError):
    """A durable B2.8 write could not be made lawfully."""


_REQUEST_INSERT = """
    INSERT INTO public.b28_simulation_requests (
        tenant_id, request_ref, requested_by,
        requested_by_agent_client_id, requested_by_credential_id,
        request_authority_principal, request_authentication_id,
        source_envelope_id, source_semantic_truth_hash,
        source_issuance_envelope_hash, input_snapshot_hash,
        total_budget_minor, currency, channel_count, channel_evidence,
        solver_profile, sufficiency_policy_version,
        sufficiency_verdict, sufficiency_reasons,
        observed_channels, observed_conversions, observed_revenue_minor
    ) VALUES (
        %(tenant_id)s, %(request_ref)s, %(requested_by)s,
        %(agent_client_id)s, %(credential_id)s, %(authority_principal)s,
        %(request_authentication_id)s,
        %(source_envelope_id)s, %(source_semantic_truth_hash)s,
        %(source_issuance_envelope_hash)s, %(input_snapshot_hash)s,
        %(total_budget_minor)s, %(currency)s, %(channel_count)s,
        %(channel_evidence)s::jsonb,
        %(solver_profile)s, %(sufficiency_policy_version)s,
        %(sufficiency_verdict)s, %(sufficiency_reasons)s,
        %(observed_channels)s, %(observed_conversions)s, %(observed_revenue_minor)s
    )
    RETURNING id, requested_at
"""

_RESULT_INSERT = """
    INSERT INTO public.b28_simulation_results (
        tenant_id, request_id, source_envelope_id, source_semantic_truth_hash,
        projection_profile_hash, input_snapshot_hash, solver_profile,
        solver_consequence_kind, total_budget_minor, allocated_total_minor,
        currency, action_authority, allocations
    ) VALUES (
        %(tenant_id)s, %(request_id)s, %(source_envelope_id)s,
        %(source_semantic_truth_hash)s, %(projection_profile_hash)s,
        %(input_snapshot_hash)s, %(solver_profile)s,
        %(solver_consequence_kind)s,
        %(total_budget_minor)s, %(allocated_total_minor)s, %(currency)s,
        %(action_authority)s, %(allocations)s::jsonb
    )
    RETURNING id
"""

_PROPOSAL_INSERT = """
    INSERT INTO public.b28_proposals (
        tenant_id, result_id, proposal_ref, source_envelope_id,
        action_authority, allocations
    ) VALUES (
        %(tenant_id)s, %(result_id)s, %(proposal_ref)s, %(source_envelope_id)s,
        %(action_authority)s, %(allocations)s::jsonb
    )
    RETURNING id
"""


def _bind_tenant(cursor, tenant_id: str) -> None:
    cursor.execute(
        "SELECT set_config('app.current_tenant_id', %s, false)", (str(tenant_id),)
    )


def _channel_evidence_json(channels: tuple[ChannelEvidence, ...]) -> str:
    return json.dumps(
        [
            {
                "channel_id": channel.channel_id,
                "verified_revenue_minor": channel.verified_revenue_minor,
                "conversion_count": channel.conversion_count,
            }
            for channel in channels
        ],
        separators=(",", ":"),
    )


def _allocations_json(result: SimulationResult) -> str:
    return json.dumps(
        [
            {
                "channel_id": line.channel_id,
                "allocation_minor": line.allocation_minor,
                "weight_basis_points": line.weight_basis_points,
            }
            for line in result.allocations
        ],
        separators=(",", ":"),
    )


def persist_simulation_request(
    *,
    tenant_id: str,
    presented_token: str,
    source_envelope_id: str,
    source_semantic_truth_hash: str,
    source_issuance_envelope_hash: str,
    total_budget_minor: int,
    currency: str,
    channels: tuple[ChannelEvidence, ...],
    request_ref: str | None = None,
) -> tuple[SimulationRequest, VerifiedRequester, str]:
    """Authenticate the caller and record one explicit request.

    There is no ``requested_by`` parameter and there will not be one. The
    identity is derived from the credential the caller proved it holds, and the
    database re-derives the same value from the two foreign keys the row
    carries, so the two derivations have to agree without either being able to
    consult the caller.
    """

    with request_custody() as connection:
        try:
            with connection.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
            requester = authenticate_simulation_requester(
                connection, tenant_id=tenant_id, presented_token=presented_token
            )

            adjudication = adjudicate_sufficiency(channels)
            request = SimulationRequest(
                request_id=str(uuid.uuid4()),
                tenant_id=str(tenant_id),
                requested_by=requester.requested_by,
                source_envelope_id=source_envelope_id,
                source_semantic_truth_hash=source_semantic_truth_hash,
                total_budget_minor=total_budget_minor,
                currency=currency,
                channels=channels,
                requested_at="pending",
            )
            snapshot_hash = compute_input_snapshot_hash(request)
            durable_request_ref = request_ref or f"req_{uuid.uuid4().hex}"

            # Corrective VI. The witness is minted after the snapshot hash and
            # the reference exist, because it is bound to both: the guard
            # re-derives that binding from the row and refuses a witness that
            # was proven for anything else.
            authentication_id = prove_request_possession(
                connection,
                tenant_id=str(tenant_id),
                presented_token=presented_token,
                request_ref=durable_request_ref,
                source_issuance_envelope_hash=source_issuance_envelope_hash,
                input_snapshot_hash=snapshot_hash,
            )

            with connection.cursor() as cursor:
                cursor.execute(
                    _REQUEST_INSERT,
                    {
                        "tenant_id": str(tenant_id),
                        "request_ref": durable_request_ref,
                        "requested_by": requester.requested_by,
                        "agent_client_id": requester.agent_client_id,
                        "credential_id": requester.credential_id,
                        "authority_principal": B28_REQUEST_PRINCIPAL,
                        "request_authentication_id": authentication_id,
                        "source_envelope_id": source_envelope_id,
                        "source_semantic_truth_hash": source_semantic_truth_hash,
                        "source_issuance_envelope_hash": (
                            source_issuance_envelope_hash
                        ),
                        "input_snapshot_hash": snapshot_hash,
                        "total_budget_minor": total_budget_minor,
                        "currency": currency,
                        "channel_count": len(channels),
                        "channel_evidence": _channel_evidence_json(channels),
                        "solver_profile": SOLVER_PROFILE,
                        "sufficiency_policy_version": SUFFICIENCY_POLICY_VERSION,
                        "sufficiency_verdict": adjudication.sufficient,
                        "sufficiency_reasons": list(adjudication.reasons),
                        "observed_channels": adjudication.observed_channels,
                        "observed_conversions": adjudication.observed_conversions,
                        "observed_revenue_minor": (
                            adjudication.observed_revenue_minor
                        ),
                    },
                )
                durable_id, requested_at = cursor.fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    # The durable identity replaces the provisional one: downstream artifacts
    # must cite the row that exists, not the uuid this process happened to mint.
    durable_request = SimulationRequest(
        request_id=str(durable_id),
        tenant_id=str(tenant_id),
        requested_by=requester.requested_by,
        source_envelope_id=source_envelope_id,
        source_semantic_truth_hash=source_semantic_truth_hash,
        total_budget_minor=total_budget_minor,
        currency=currency,
        channels=channels,
        requested_at=requested_at.isoformat(),
    )
    return durable_request, requester, str(durable_id)


def persist_simulation_consequence(
    *,
    envelope: Mapping[str, Any],
    request: SimulationRequest,
    source_issuance_envelope_hash: str,
) -> tuple[SimulationResult | SimulationRefusal, Proposal | None, dict[str, str]]:
    """Run the governed solver and persist exactly its consequence.

    The allocation is never a parameter. It is produced here by the same
    admission conjunction every other caller goes through, and the database
    recomputes the deterministic function over the request's own retained
    evidence before accepting the row -- so "the persisted allocation is the
    solver's output" is decided twice, by two authorities, one of which is not
    the writer.
    """

    outcome = simulate_from_trust(envelope, request=request)
    if isinstance(outcome, SimulationRefusal):
        # A refusal is a lawful outcome and is deliberately not persisted: P14
        # emits no row that could be mistaken for a result.
        return outcome, None, {"persisted": "false", "reason": outcome.reason_code}

    proposal = propose_from_result(outcome)
    identifiers: dict[str, str] = {"persisted": "true"}
    with solver_custody() as connection:
        try:
            with connection.cursor() as cursor:
                _bind_tenant(cursor, request.tenant_id)
                cursor.execute(
                    _RESULT_INSERT,
                    {
                        "tenant_id": request.tenant_id,
                        "request_id": request.request_id,
                        "source_envelope_id": outcome.source_envelope_id,
                        "source_semantic_truth_hash": (
                            outcome.source_semantic_truth_hash
                        ),
                        "projection_profile_hash": outcome.projection_profile_hash,
                        "input_snapshot_hash": outcome.input_snapshot_hash,
                        "solver_profile": outcome.solver_profile,
                        # Not `outcome.solver_invocations`. That number is an
                        # honest in-process observation and an unwitnessable
                        # durable claim; the durable contract states the
                        # property the database actually verifies.
                        "solver_consequence_kind": SOLVER_CONSEQUENCE_KIND,
                        "total_budget_minor": outcome.total_budget_minor,
                        "allocated_total_minor": sum(
                            line.allocation_minor for line in outcome.allocations
                        ),
                        "currency": outcome.currency,
                        "action_authority": outcome.action_authority,
                        "allocations": _allocations_json(outcome),
                    },
                )
                result_id = cursor.fetchone()[0]
                identifiers["result_id"] = str(result_id)
                identifiers["solver_principal"] = B28_SOLVER_PRINCIPAL

                cursor.execute(
                    _PROPOSAL_INSERT,
                    {
                        "tenant_id": request.tenant_id,
                        "result_id": str(result_id),
                        # The durable reference names the durable result, which
                        # is the conservation relation itself. The application's
                        # content-addressed `proposal.proposal_id` is a function
                        # of the input snapshot alone, so two lawful requests
                        # over identical evidence would collide on it -- the
                        # uniqueness a proposal actually needs is per-result.
                        "proposal_ref": f"prop_{result_id}",
                        "source_envelope_id": proposal.source_envelope_id,
                        "action_authority": proposal.action_authority,
                        "allocations": _allocations_json(outcome),
                    },
                )
                identifiers["proposal_id"] = str(cursor.fetchone()[0])
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    identifiers["source_issuance_envelope_hash"] = source_issuance_envelope_hash
    return outcome, proposal, identifiers


def conduct_requested_simulation(
    *,
    envelope: Mapping[str, Any],
    tenant_id: str,
    presented_token: str,
    source_issuance_envelope_hash: str,
    total_budget_minor: int,
    currency: str,
    channels: tuple[ChannelEvidence, ...],
    request_ref: str | None = None,
) -> dict[str, Any]:
    """The whole lawful B2.8 path, from a presented credential to a proposal.

    This is the operational wiring Directive V's Exit Gate 11 is about. It is
    one function so that "the corrected authorities are actually used" is a
    property of the only entry point rather than of a convention several callers
    are expected to follow, and it takes a *token* rather than an identity so
    that there is no argument through which a caller could name itself.
    """

    request, requester, request_id = persist_simulation_request(
        tenant_id=tenant_id,
        presented_token=presented_token,
        source_envelope_id=str(envelope.get("envelope_id", "")),
        source_semantic_truth_hash=str(envelope.get("semantic_truth_hash", "")),
        source_issuance_envelope_hash=source_issuance_envelope_hash,
        total_budget_minor=total_budget_minor,
        currency=currency,
        channels=channels,
        request_ref=request_ref,
    )
    outcome, proposal, identifiers = persist_simulation_consequence(
        envelope=envelope,
        request=request,
        source_issuance_envelope_hash=source_issuance_envelope_hash,
    )
    return {
        "request_id": request_id,
        "requested_by": requester.requested_by,
        "requester": requester,
        "request": request,
        "outcome": outcome,
        "proposal": proposal,
        "identifiers": identifiers,
    }


__all__ = [
    "SimulationPersistenceError",
    "conduct_requested_simulation",
    "persist_simulation_consequence",
    "persist_simulation_request",
]

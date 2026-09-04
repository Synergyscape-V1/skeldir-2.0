"""B2.8 request-driven simulation service.

Everything reachable from here is READ / COMPUTE / PROPOSE. There is no
platform client, no dispatch queue, no budget mutation and no scheduled entry
point in this package's import closure -- a property
``scripts/ci/validate_b25_p14_downstream_authority.py`` enforces statically, so
adding one is a merge-blocking change rather than a quiet one.

``simulate_from_trust`` is the whole public surface. It takes a signed
TrustEnvelope and an explicit request; with no request it refuses, which is the
Gate 6 behaviour stated as code rather than as documentation.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from app.simulation.admission import admit_and_simulate
from app.simulation.contract import (
    Proposal,
    SimulationRefusal,
    SimulationRequest,
    SimulationResult,
)
from app.trust.projection import TrustProjection, project_trust_envelope


OPTIMIZATION_PROFILE_ID = "optimization_projection_safe"


def project_for_simulation(envelope: Mapping[str, Any]) -> TrustProjection:
    """Project a signed envelope through the optimization-safe profile."""
    return project_trust_envelope(
        envelope, profile_id=OPTIMIZATION_PROFILE_ID, machine_consumer=True
    )


def simulate_from_trust(
    envelope: Mapping[str, Any] | None,
    *,
    request: SimulationRequest | None,
) -> SimulationResult | SimulationRefusal:
    """Run one explicitly requested simulation against a real issued Trust."""
    if request is None:
        # Refuse before touching the envelope at all: an autonomous path must
        # not even be able to observe that the evidence would have qualified.
        return admit_and_simulate(request=None, projection=None)
    projection = None if envelope is None else project_for_simulation(envelope)
    return admit_and_simulate(request=request, projection=projection)


def propose_from_result(result: SimulationResult) -> Proposal:
    """Turn a conserved simulation result into a human-approval proposal."""
    return Proposal(
        proposal_id=f"prop_{uuid.uuid5(uuid.NAMESPACE_URL, result.input_snapshot_hash).hex}",
        request_id=result.request_id,
        tenant_id_hash=result.tenant_id_hash,
        source_envelope_id=result.source_envelope_id,
        action_authority=result.action_authority,
        allocations=result.allocations,
    )


__all__ = [
    "OPTIMIZATION_PROFILE_ID",
    "project_for_simulation",
    "propose_from_result",
    "simulate_from_trust",
]

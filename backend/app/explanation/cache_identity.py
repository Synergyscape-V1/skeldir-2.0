"""B2.7 cache / materialization identity.

H-RC5 asks a specific empirical question: what is the *minimum complete* cache
identity? The historically wrong answer is ``envelope_id``, because two Trust
states for the same subject share a subject but not a meaning. The answer this
module implements is that the identity must close over every input the
explanation's meaning depends on:

    tenant           -- Gate 10 requires tenant identity inside the boundary,
                        not beside it, so a foreign-tenant collision is
                        impossible rather than merely unlikely
    semantic truth   -- the hash the signature commits to
    policy state     -- the same numbers under a different policy authority are
                        a different explanation
    confidence       -- status and authority, because "unavailable" and
                        "available at 6200bp" say different things
    causal status    -- an explanation's causal caveat is part of its meaning
    fallback state   -- a degraded explanation must not be served as a healthy
                        one
    projection profile hash -- the contract the projection was produced under
    contract version -- the claim vocabulary itself

Because the identity is a function of meaning, a lawful source transition
T1 -> T2 produces a different identity, so a stale materialization can never be
*found* for the new state. That is the fail-closed direction: staleness is not
detected and repaired, it is unreachable. The database additionally marks the
old row stale so an auditor can see the transition happened, which is
observability rather than the safety mechanism.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.explanation.contract import EXPLANATION_CONTRACT_VERSION
from app.trust.canonicalization import canonicalize_json_document
from app.trust.projection import TrustProjection
from app.trust.refusal import tagged_sha256


# Every component below is load-bearing: the P14 negative controls remove one
# at a time and require the staleness gate to go red, which is what makes this
# list evidence rather than an assertion.
CACHE_IDENTITY_COMPONENTS: tuple[str, ...] = (
    "tenant_id_hash",
    "semantic_truth_hash",
    "policy_state",
    "confidence_status",
    "confidence_authority",
    "causal_status",
    "fallback_applied",
    "projection_profile_hash",
    "explanation_contract_version",
)


def cache_identity_material(projection: TrustProjection) -> dict[str, Any]:
    """The exact material an explanation's cache identity is computed over."""
    return {
        "tenant_id_hash": projection.tenant_id_hash,
        "semantic_truth_hash": projection.semantic_truth_hash,
        "policy_state": projection.source_policy_state,
        "confidence_status": projection.projected.get(
            "confidence_metadata.confidence_status"
        ),
        "confidence_authority": projection.projected.get(
            "confidence_metadata.confidence_authority"
        ),
        "causal_status": projection.projected.get("causal_status"),
        "fallback_applied": bool(projection.projected.get("fallback_applied", False)),
        "projection_profile_hash": projection.profile_hash,
        "explanation_contract_version": EXPLANATION_CONTRACT_VERSION,
    }


def compute_cache_identity(
    projection: TrustProjection,
    *,
    omit_components: Mapping[str, bool] | None = None,
) -> str:
    """Compute the tagged identity for one explanation materialization.

    ``omit_components`` exists for the negative controls only. A control that
    removes a component must make the staleness proof red; a component whose
    removal changes nothing was never load-bearing, and this parameter is how
    that gets measured rather than argued.
    """

    material = cache_identity_material(projection)
    if omit_components:
        for name, omit in omit_components.items():
            if name not in CACHE_IDENTITY_COMPONENTS:
                raise ValueError(f"cache_identity_component_unknown:{name}")
            if omit:
                material.pop(name, None)
    return tagged_sha256(canonicalize_json_document(material).decode("utf-8"))

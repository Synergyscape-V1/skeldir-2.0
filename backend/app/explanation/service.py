"""B2.7 explanation composition over a real issued TrustEnvelope.

The composition order is the safety argument:

    real issued Trust
      -> P14 projection (allowlist + positions)
      -> deterministic claim rendering
      -> conservation adjudication
      -> result

Nothing is externalized before the adjudication runs, and the adjudication runs
against the finished artifact rather than against the generator's intentions.
A generator swap -- including a future LLM rewrite of the narrative -- changes
what is adjudicated, not whether it is.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.explanation.cache_identity import compute_cache_identity
from app.explanation.contract import (
    EXPLANATION_CONTRACT_VERSION,
    ExplanationContractError,
    ExplanationRequest,
    ExplanationResult,
    JudgeAssessment,
)
from app.explanation.conservation import (
    ExplanationConservationError,
    adjudicate_explanation_conservation,
)
from app.explanation.renderer import render_explanation_claims
from app.trust.projection import (
    TrustProjection,
    TrustProjectionError,
    project_trust_envelope,
)
from app.trust.projection_profiles import DEFAULT_LLM_PROFILE_ID


def project_for_explanation(
    envelope: Mapping[str, Any],
    *,
    profile_id: str = DEFAULT_LLM_PROFILE_ID,
) -> TrustProjection:
    """Project a signed envelope through the explanation-safe profile."""
    return project_trust_envelope(
        envelope, profile_id=profile_id, machine_consumer=True
    )


def compose_explanation(
    envelope: Mapping[str, Any],
    *,
    request: ExplanationRequest,
    narrative_override: str | None = None,
    claims_override: tuple[Any, ...] | None = None,
) -> ExplanationResult:
    """Compose and adjudicate one explanation of a real issued TrustEnvelope.

    ``narrative_override`` / ``claims_override`` are the adversarial ingress the
    negative controls use: they stand in for whatever a future generator (or a
    compromised one) might produce. They do not bypass adjudication -- they are
    exactly what gets adjudicated, which is why the controls are meaningful.
    """

    projection = project_for_explanation(envelope, profile_id=request.profile_id)

    if str(envelope.get("tenant_id_hash")) != projection.tenant_id_hash:
        raise TrustProjectionError("explanation_tenant_binding_lost")

    rendered_claims, rendered_narrative = render_explanation_claims(projection)
    claims = tuple(claims_override) if claims_override is not None else rendered_claims
    narrative = (
        narrative_override if narrative_override is not None else rendered_narrative
    )

    confidence_status = projection.projected.get(
        "confidence_metadata.confidence_status"
    )
    if not isinstance(confidence_status, str):
        # A projection that carries no confidence status cannot support an
        # explanation: the E3 obligation has no state to preserve.
        raise ExplanationContractError("explanation_confidence_status_absent")

    result = ExplanationResult(
        contract_version=EXPLANATION_CONTRACT_VERSION,
        tenant_id_hash=projection.tenant_id_hash,
        envelope_id=projection.envelope_id,
        semantic_truth_hash=projection.semantic_truth_hash,
        profile_id=projection.profile_id,
        profile_version=projection.profile_version,
        profile_hash=projection.profile_hash,
        cache_identity_hash=compute_cache_identity(projection),
        policy_state=projection.source_policy_state,
        confidence_status=confidence_status,
        causal_status=projection.projected.get("causal_status"),
        fallback_applied=bool(projection.projected.get("fallback_applied", False)),
        claims=claims,
        narrative=narrative,
        evidence={
            "projected_paths": sorted(projection.projected),
            "authority_positions": dict(projection.authority_positions),
        },
    )

    verdict = adjudicate_explanation_conservation(
        projection=projection, result=result
    )
    verdict.require()
    return result


def assess_presentation(result: ExplanationResult) -> JudgeAssessment:
    """Score presentation quality without touching a single truth-bearing field.

    P14-G4. The signature is the proof: this function returns a
    ``JudgeAssessment``, and there is no function anywhere that consumes one to
    change an ``ExplanationResult``. The judge is structurally an observer.
    """

    length = len(result.narrative)
    claim_count = len(result.claims)
    # A deterministic, non-authoritative readability heuristic. Its output is a
    # presentation score and nothing else.
    density = 0 if length == 0 else min(10_000, (claim_count * 10_000) // max(length, 1))
    notes: list[str] = []
    if claim_count == 0:
        notes.append("no_claims_rendered")
    if length > 4_000:
        notes.append("narrative_long")
    return JudgeAssessment(
        presentation_score_basis_points=density,
        readability_notes=tuple(notes),
    )


__all__ = [
    "ExplanationConservationError",
    "assess_presentation",
    "compose_explanation",
    "project_for_explanation",
]

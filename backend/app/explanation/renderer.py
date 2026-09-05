"""Deterministic B2.7 explanation renderer.

Design Partner Mode grants no LLM authority over anything on this path, so the
renderer is a total function from a projection to a claim set. That is not a
placeholder for a model: it is the shape the boundary has to keep even after a
model is introduced. A model may later *rewrite* the narrative, and the
conservation checker will adjudicate the rewrite against the same claims -- but
the claims themselves stay a deterministic projection of source truth, so no
generator can be the origin of a fact.

Since Corrective IV the renderer has one further property, and it is the one
that closes the open-world causal problem. It does not author sentences. Every
rendering is produced by ``app.explanation.templates.render_claim`` from the
closed, content-addressed frame corpus, and the narrative is the exact join of
those renderings. The renderer therefore has no expressive power the frame
corpus does not already have, which is why an unseen causal phrasing cannot
appear here even by accident.

Two consequences worth naming:

* the renderer cannot emit a number that is not a projected value, because it
  has no source of numbers other than ``projection.projected``;
* the renderer cannot omit the fallback or unavailable-confidence statement,
  because those branches are unconditional on the source state rather than on a
  formatting preference.
"""

from __future__ import annotations

from app.explanation.contract import (
    CLAIM_CONFIDENCE,
    CLAIM_FALLBACK,
    CLAIM_FINANCIAL,
    CLAIM_POLICY,
    CLAIM_PROVENANCE,
    CLAIM_STATUS,
    ExplanationClaim,
)
from app.explanation.templates import compose_narrative, render_claim
from app.trust.projection import TrustProjection


# Paths rendered as status facts, in the order an explanation states them. The
# sentence frame for each lives in the template registry, not here: this list
# decides *what* is stated, the registry decides *how*, and neither can invent
# the other's half.
_STATUS_PATHS: tuple[str, ...] = (
    "deterministic_verification_status",
    "match_verdict_status",
    "discrepancy_class",
    "attribution_model",
    "model_assumption",
    "causal_status",
    "data_completeness_status",
    "truth_type",
    "truth_authority.authority_class",
)


def _claim(claim_kind: str, source_path: str, value: object) -> ExplanationClaim:
    template_id, value_text, rendered = render_claim(claim_kind, source_path, value)
    return ExplanationClaim(
        claim_kind=claim_kind,
        source_path=source_path,
        value=value,
        rendered=rendered,
        template_id=template_id,
        value_text=value_text,
    )


def render_explanation_claims(
    projection: TrustProjection,
) -> tuple[tuple[ExplanationClaim, ...], str]:
    """Render the claim set and narrative for one projection."""
    claims: list[ExplanationClaim] = []

    # Provenance first: an explanation names what it explains before it says
    # anything about it.
    for path in ("envelope_id", "semantic_truth_hash", "audit_ref"):
        if projection.has(path):
            claims.append(_claim(CLAIM_PROVENANCE, path, projection.value(path)))

    if projection.has("verified_revenue_minor"):
        claims.append(
            _claim(
                CLAIM_FINANCIAL,
                "verified_revenue_minor",
                projection.value("verified_revenue_minor"),
            )
        )
    if projection.has("currency"):
        claims.append(_claim(CLAIM_STATUS, "currency", projection.value("currency")))

    for path in _STATUS_PATHS:
        if projection.has(path):
            claims.append(_claim(CLAIM_STATUS, path, projection.value(path)))

    confidence_status = projection.projected.get(
        "confidence_metadata.confidence_status"
    )
    if confidence_status is not None:
        # Unconditional in both directions. The confidence state is stated as
        # what it is -- available, unavailable, degraded, diagnostics_failed --
        # through one frame, so an unavailable state can neither be hidden nor
        # hedged into something that reads like a weak confidence.
        claims.append(
            _claim(
                CLAIM_CONFIDENCE,
                "confidence_metadata.confidence_status",
                confidence_status,
            )
        )
        if confidence_status == "available" and projection.has(
            "confidence_metadata.confidence_score_basis_points"
        ):
            score = projection.value(
                "confidence_metadata.confidence_score_basis_points"
            )
            if score is not None:
                claims.append(
                    _claim(
                        CLAIM_CONFIDENCE,
                        "confidence_metadata.confidence_score_basis_points",
                        score,
                    )
                )
        if confidence_status != "available":
            reason = projection.projected.get(
                "confidence_metadata.unavailable_reason"
            )
            if reason is not None:
                claims.append(
                    _claim(
                        CLAIM_STATUS,
                        "confidence_metadata.unavailable_reason",
                        reason,
                    )
                )

    if projection.has("fallback_applied") and bool(
        projection.value("fallback_applied")
    ):
        claims.append(_claim(CLAIM_FALLBACK, "fallback_applied", True))
        if projection.has("fallback_reason"):
            reason = projection.value("fallback_reason")
            if reason is not None:
                claims.append(_claim(CLAIM_FALLBACK, "fallback_reason", reason))

    if projection.has("policy_action_authority.policy_state"):
        claims.append(
            _claim(
                CLAIM_POLICY,
                "policy_action_authority.policy_state",
                projection.value("policy_action_authority.policy_state"),
            )
        )

    narrative = compose_narrative([claim.rendered for claim in claims])
    return tuple(claims), narrative

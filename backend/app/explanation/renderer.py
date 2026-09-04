"""Deterministic B2.7 explanation renderer.

Design Partner Mode grants no LLM authority over anything on this path, so the
renderer is a total function from a projection to a claim set. That is not a
placeholder for a model: it is the shape the boundary has to keep even after a
model is introduced. A model may later *rewrite* the narrative, and the
conservation checker will adjudicate the rewrite against the same claims -- but
the claims themselves stay a deterministic projection of source truth, so no
generator can be the origin of a fact.

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
from app.trust.projection import TrustProjection


_STATUS_PATHS: tuple[tuple[str, str], ...] = (
    ("deterministic_verification_status", "Deterministic verification status is {value}."),
    ("match_verdict_status", "The match verdict is {value}."),
    ("discrepancy_class", "The reconciliation discrepancy class is {value}."),
    ("attribution_model", "The attribution model applied is {value}."),
    ("model_assumption", "The model assumption is {value}."),
    ("causal_status", "The causal status of this result is {value}."),
    ("data_completeness_status", "Data completeness is {value}."),
    ("truth_type", "The truth type is {value}."),
    ("truth_authority.authority_class", "The authority class is {value}."),
)


def _minor_units_sentence(path: str, value: int, currency: str | None) -> str:
    # Rendered in both minor units and the major-unit form the P11 display
    # contract already produces, so the conservation checker's supported numeric
    # surface and the renderer agree by construction rather than by luck.
    major, cents = divmod(abs(value), 100)
    sign = "-" if value < 0 else ""
    unit = f" {currency}" if currency else ""
    return (
        f"{path.replace('_', ' ')} is {value} minor units "
        f"({sign}{major}.{cents:02d}{unit})."
    )


def render_explanation_claims(
    projection: TrustProjection,
) -> tuple[tuple[ExplanationClaim, ...], str]:
    """Render the claim set and narrative for one projection."""
    claims: list[ExplanationClaim] = []
    currency = projection.projected.get("currency")

    # Provenance first: an explanation names what it explains before it says
    # anything about it.
    for path in ("envelope_id", "semantic_truth_hash", "audit_ref"):
        if projection.has(path):
            value = projection.value(path)
            claims.append(
                ExplanationClaim(
                    claim_kind=CLAIM_PROVENANCE,
                    source_path=path,
                    value=value,
                    rendered=f"This explanation is bound to {path} {value}.",
                )
            )

    if projection.has("verified_revenue_minor"):
        value = projection.value("verified_revenue_minor")
        claims.append(
            ExplanationClaim(
                claim_kind=CLAIM_FINANCIAL,
                source_path="verified_revenue_minor",
                value=value,
                rendered=_minor_units_sentence(
                    "verified revenue", value, currency if isinstance(currency, str) else None
                ),
            )
        )
    if projection.has("currency"):
        claims.append(
            ExplanationClaim(
                claim_kind=CLAIM_STATUS,
                source_path="currency",
                value=projection.value("currency"),
                rendered=f"Amounts are denominated in {projection.value('currency')}.",
            )
        )

    for path, template in _STATUS_PATHS:
        if projection.has(path):
            value = projection.value(path)
            claims.append(
                ExplanationClaim(
                    claim_kind=CLAIM_STATUS,
                    source_path=path,
                    value=value,
                    rendered=template.format(value=value),
                )
            )

    confidence_status = projection.projected.get(
        "confidence_metadata.confidence_status"
    )
    if confidence_status is not None:
        if confidence_status == "available":
            claims.append(
                ExplanationClaim(
                    claim_kind=CLAIM_CONFIDENCE,
                    source_path="confidence_metadata.confidence_status",
                    value=confidence_status,
                    rendered="A bounded confidence projection is available.",
                )
            )
            if projection.has("confidence_metadata.confidence_score_basis_points"):
                score = projection.value(
                    "confidence_metadata.confidence_score_basis_points"
                )
                if score is not None:
                    claims.append(
                        ExplanationClaim(
                            claim_kind=CLAIM_CONFIDENCE,
                            source_path=(
                                "confidence_metadata.confidence_score_basis_points"
                            ),
                            value=score,
                            rendered=(
                                f"The projected confidence is {score} basis points."
                            ),
                        )
                    )
        else:
            # Unconditional. An unavailable confidence is stated as unavailable,
            # never hedged into something that reads like a weak confidence.
            claims.append(
                ExplanationClaim(
                    claim_kind=CLAIM_CONFIDENCE,
                    source_path="confidence_metadata.confidence_status",
                    value=confidence_status,
                    rendered=(
                        "No confidence projection is available for this result "
                        f"(state: {confidence_status})."
                    ),
                )
            )
            reason = projection.projected.get(
                "confidence_metadata.unavailable_reason"
            )
            if reason is not None:
                claims.append(
                    ExplanationClaim(
                        claim_kind=CLAIM_STATUS,
                        source_path="confidence_metadata.unavailable_reason",
                        value=reason,
                        rendered=f"The recorded unavailability reason is {reason}.",
                    )
                )

    if projection.has("fallback_applied") and bool(
        projection.value("fallback_applied")
    ):
        claims.append(
            ExplanationClaim(
                claim_kind=CLAIM_FALLBACK,
                source_path="fallback_applied",
                value=True,
                rendered="This result was produced under a declared fallback.",
            )
        )
        if projection.has("fallback_reason"):
            reason = projection.value("fallback_reason")
            if reason is not None:
                claims.append(
                    ExplanationClaim(
                        claim_kind=CLAIM_FALLBACK,
                        source_path="fallback_reason",
                        value=reason,
                        rendered=f"The declared fallback reason is {reason}.",
                    )
                )

    if projection.has("policy_action_authority.policy_state"):
        state = projection.value("policy_action_authority.policy_state")
        claims.append(
            ExplanationClaim(
                claim_kind=CLAIM_POLICY,
                source_path="policy_action_authority.policy_state",
                value=state,
                rendered=f"The policy authority for this subject is {state}.",
            )
        )

    narrative = " ".join(claim.rendered for claim in claims)
    return tuple(claims), narrative

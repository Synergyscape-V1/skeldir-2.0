"""B2.7 explanation contract types.

An explanation is not prose with numbers in it. It is a typed set of *claims*,
each of which either binds to an authoritative source path or is refused. The
narrative is rendered from the claims, never the other way round, so there is no
position in the pipeline where a sentence can acquire a fact the claims do not
carry.

That inversion is the whole design. If prose were primary and validation
secondary, conservation would depend on the validator noticing every way a
number can be spelled. With claims primary, an unsupported number has nowhere to
live: it is not in the claim set, so it is not in the narrative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


# The claim vocabulary. Each kind names what sort of authority the claim
# carries, so the conservation check can be total over kinds rather than
# heuristic over text.
CLAIM_FINANCIAL = "financial_fact"
CLAIM_STATUS = "status_fact"
CLAIM_CONFIDENCE = "confidence_statement"
CLAIM_CAUSAL = "causal_statement"
CLAIM_POLICY = "policy_statement"
CLAIM_FALLBACK = "fallback_statement"
CLAIM_PROVENANCE = "provenance_fact"

CLAIM_KINDS: tuple[str, ...] = (
    CLAIM_FINANCIAL,
    CLAIM_STATUS,
    CLAIM_CONFIDENCE,
    CLAIM_CAUSAL,
    CLAIM_POLICY,
    CLAIM_FALLBACK,
    CLAIM_PROVENANCE,
)

EXPLANATION_CONTRACT_VERSION = "b25-p14-explanation-v1"

# Design Partner Mode has no authoritative causal substrate. B2.13 is the phase
# that would introduce one; until it exists and explicitly authorizes a causal
# claim, `causal_status` can only ever say that causality was not estimated or
# is unavailable, and neither authorizes a causal sentence.
CAUSALLY_AUTHORIZING_STATUSES: frozenset[str] = frozenset()


class ExplanationContractError(ValueError):
    """Raised when an explanation artifact is not well formed."""


@dataclass(frozen=True)
class ExplanationClaim:
    """One externalized statement and the source authority it rests on.

    ``template_id`` and ``value_text`` name the closed narrative frame the
    rendering claims to be an instance of. They are *declared*, not enforced,
    here: the conservation checker re-derives both from the registry and
    requires byte equality with ``rendered``. Keeping the declaration separate
    from the derivation is what lets the checker be pointed at an adversarial
    artifact -- a claim whose rendering does not follow from its declared frame
    has to be constructible, or the control that proves the checker works could
    not be written.

    Both fields default to the registry's own derivation, so an ordinary caller
    cannot forget them and a caller that supplies a contradictory pair is
    refused at adjudication rather than at construction.
    """

    claim_kind: str
    source_path: str
    value: Any
    rendered: str
    template_id: str = ""
    value_text: str = ""

    def __post_init__(self) -> None:
        if self.claim_kind not in CLAIM_KINDS:
            raise ExplanationContractError(
                f"explanation_claim_kind_unknown:{self.claim_kind!r}"
            )
        if not isinstance(self.source_path, str) or not self.source_path:
            raise ExplanationContractError("explanation_claim_source_path_required")
        if not isinstance(self.rendered, str) or not self.rendered:
            raise ExplanationContractError("explanation_claim_rendered_required")
        if isinstance(self.value, float):
            raise ExplanationContractError(
                f"explanation_claim_float_forbidden:{self.source_path}"
            )
        if not self.template_id or not self.value_text:
            # Imported here rather than at module scope: the template registry
            # imports this module for the claim-kind vocabulary, and the
            # dependency has to run in that direction so the vocabulary stays
            # the more primitive of the two.
            from app.explanation.templates import (  # noqa: PLC0415
                canonical_value_text,
                template_for,
            )

            template = template_for(self.claim_kind, self.source_path)
            if not self.template_id:
                object.__setattr__(
                    self,
                    "template_id",
                    "" if template is None else template.template_id,
                )
            if not self.value_text:
                try:
                    derived = canonical_value_text(self.source_path, self.value)
                except ExplanationContractError:
                    derived = ""
                object.__setattr__(self, "value_text", derived)

    def as_persisted(self) -> dict[str, Any]:
        """The claim in the shape ``b27_explanation_materializations`` stores.

        The database mirror of the frame registry re-derives ``rendered`` from
        ``template_id`` and ``value_text``, so these five keys are exactly what
        the physical derivation law needs and nothing more.
        """

        return {
            "claim_kind": self.claim_kind,
            "source_path": self.source_path,
            "template_id": self.template_id,
            "value_text": self.value_text,
            "rendered": self.rendered,
        }


@dataclass(frozen=True)
class ExplanationRequest:
    """An explicit request to explain one signed TrustEnvelope."""

    tenant_id: str
    envelope_id: str
    subject_type: str
    subject_ref_hash: str
    profile_id: str
    requested_by: str

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "envelope_id",
            "subject_type",
            "subject_ref_hash",
            "profile_id",
            "requested_by",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ExplanationContractError(f"explanation_request_field:{name}")


@dataclass(frozen=True)
class ExplanationResult:
    """A conserved explanation, bound to the exact source it explains."""

    contract_version: str
    tenant_id_hash: str
    envelope_id: str
    semantic_truth_hash: str
    profile_id: str
    profile_version: str
    profile_hash: str
    cache_identity_hash: str
    policy_state: str
    confidence_status: str
    causal_status: str | None
    fallback_applied: bool
    claims: tuple[ExplanationClaim, ...]
    narrative: str
    authority_class: str = "non_authoritative_explanation"
    judge_authority: str = "none"
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def claim_paths(self) -> tuple[str, ...]:
        return tuple(claim.source_path for claim in self.claims)

    def financial_claims(self) -> tuple[ExplanationClaim, ...]:
        return tuple(c for c in self.claims if c.claim_kind == CLAIM_FINANCIAL)


@dataclass(frozen=True)
class JudgeAssessment:
    """A presentation-quality score with no authority over anything true.

    P14-G4 is a structural property here, not a promise: this type carries no
    field a truth-bearing consumer reads, and ``apply_judge_assessment`` does
    not exist. A judge can say an explanation reads poorly. It has no way to say
    an explanation is wrong about money, confidence, causality or policy, and no
    way to change any of them.
    """

    presentation_score_basis_points: int
    readability_notes: tuple[str, ...] = ()
    authority_class: str = "non_authoritative_presentation_assessment"

    def __post_init__(self) -> None:
        if isinstance(self.presentation_score_basis_points, bool) or not isinstance(
            self.presentation_score_basis_points, int
        ):
            raise ExplanationContractError("judge_score_must_be_integer")
        if not 0 <= self.presentation_score_basis_points <= 10_000:
            raise ExplanationContractError("judge_score_out_of_range")

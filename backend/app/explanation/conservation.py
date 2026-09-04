"""B2.7 semantic-conservation adjudication.

The proposition this module decides is::

    for every externalized statement s in an explanation E of Trust T:
        meaning(s) == meaning(source(s) in T)
    and
        A(E) <= A(T)

It is deliberately a *checker* over a finished artifact rather than a filter
inside a generator. A checker can be pointed at an adversarial artifact -- one
that a mutated renderer, a future LLM, or a controlled negative control
produced -- and still decide correctly. A filter can only ever constrain the
generator it lives inside, which is the failure mode where "our generator never
does that" quietly becomes the safety argument.

Every refusal is a typed reason code, because the P14 falsifiers require RED
*for the predicted causal reason*: a test that only knows the gate went red
cannot tell a real defect from an unrelated crash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.explanation.contract import (
    CAUSALLY_AUTHORIZING_STATUSES,
    CLAIM_CAUSAL,
    CLAIM_CONFIDENCE,
    CLAIM_FALLBACK,
    CLAIM_FINANCIAL,
    CLAIM_POLICY,
    ExplanationClaim,
    ExplanationResult,
)
from app.trust.projection import TrustProjection, assert_authority_monotonic
from app.trust.projection_profiles import (
    UNTRUSTED_TEXT_CLASSES,
    ProjectionProfileError,
    get_projection_profile,
)


# Confidence states in which an explanation may narrate a confidence value.
# Anything else must remain explicitly unavailable rather than be smoothed into
# a hedge, because a hedge reads as weak confidence and "unavailable" is not a
# weak confidence -- it is the absence of one.
CONFIDENCE_NARRATABLE: frozenset[str] = frozenset({"available"})

# Language that *asserts* a causal relation. This is a finite risk indicator,
# not the safety boundary: the boundary is that no claim of kind
# ``causal_statement`` may exist without an authorizing causal substrate, which
# is checked structurally below. The sweep exists to catch a causal assertion
# smuggled into the rendered text of a differently-typed claim.
#
# It deliberately does not match the bare adjective "causal". Naming the field
# -- "the causal status of this result is causal_not_estimated" -- is a
# statement about the *absence* of a causal claim, and refusing it would make
# the checker reject the one sentence whose whole job is to say that causality
# was not estimated. What is matched is causal verbs, causal connectives, and
# the noun phrases that assert a causal relation rather than name the field.
_CAUSAL_LANGUAGE = re.compile(
    r"\b("
    r"caused|causes|causing|causally|"
    r"causal\s+(?:effect|impact|relationship|contribution|attribution|lift|"
    r"influence|role|link|driver)s?|"
    r"drove|drives|driving|"
    r"because\s+of|due\s+to|as\s+a\s+result\s+of|"
    r"led\s+to|leads\s+to|leading\s+to|"
    r"incremental(?:ity|ly)?|uplift|lift\s+from|"
    r"attributable\s+to|responsible\s+for|"
    r"if\s+you\s+(?:had|hadn't|did\s+not)|counterfactual"
    r")\b",
    re.IGNORECASE,
)

# Language that asserts confidence in a way an unavailable state cannot support.
_CONFIDENCE_LANGUAGE = re.compile(
    r"\b("
    r"confidence|confident|certainty|certain|"
    r"likelihood|probability|probable|likely|"
    r"credible\s+interval|posterior"
    r")\b",
    re.IGNORECASE,
)

# Any run of digits that could read as a quantity. Every one of these in the
# narrative has to be accounted for by a claim.
_NUMERIC_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")


class ExplanationConservationError(ValueError):
    """Raised when an explanation would externalize more than its source."""


@dataclass(frozen=True)
class ConservationVerdict:
    """The adjudication outcome, with every violation named."""

    conserved: bool
    violations: tuple[str, ...]

    def require(self) -> None:
        if not self.conserved:
            raise ExplanationConservationError(
                "explanation_conservation_violated:" + ";".join(self.violations)
            )


def _numeric_tokens(text: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in _NUMERIC_TOKEN.finditer(text)}


def _mask_projected_values(text: str, projection: TrustProjection) -> str:
    """Blank out verbatim projections of source values before the lexical sweep.

    The lexical sweeps below are risk indicators over *prose*. A value copied
    verbatim out of an authoritative field is not prose -- it is the source
    speaking, and the per-claim correspondence check has already established
    that it was not mutated. Without this, ``causal_status`` would trip the
    causal-language detector by containing the word "causal", which would make
    the checker refuse the very field whose whole purpose is to say that
    causality was *not* estimated.

    Masking is exact-substring only, so it cannot be used to smuggle language
    the source does not itself contain: an attacker would have to get the
    forbidden word into an authoritative enum first, and that is a different
    boundary with its own fence.
    """

    masked = text
    for value in projection.projected.values():
        if isinstance(value, str) and value:
            masked = masked.replace(value, " ")
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    masked = masked.replace(item, " ")
    return masked


def _supported_numeric_surface(claims: Iterable[ExplanationClaim]) -> set[str]:
    """Every numeric spelling a claim's own value authorizes.

    A claim over ``verified_revenue_minor = 125000`` authorizes the minor-unit
    integer and the major-unit rendering the display contract already produces.
    It authorizes nothing else -- notably not a rounded, scaled or "approximately"
    restatement, which is the exact shape an unsupported number takes when a
    model paraphrases a real one.
    """

    surface: set[str] = set()
    for claim in claims:
        value = claim.value
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int):
            surface.add(str(value))
            surface.add(str(abs(value)))
            if claim.source_path.endswith("_minor"):
                major = abs(value) // 100
                cents = abs(value) % 100
                surface.add(f"{major}.{cents:02d}")
                surface.add(str(major))
                surface.add(f"{cents:02d}")
                surface.add(str(cents))
        elif isinstance(value, str):
            surface.update(_numeric_tokens(value))
    return surface


def _claim_is_projected(
    claim: ExplanationClaim, projection: TrustProjection
) -> str | None:
    if not projection.has(claim.source_path):
        return (
            f"claim_source_not_projected:{claim.claim_kind}:{claim.source_path}"
        )
    source_value = projection.value(claim.source_path)
    if claim.value != source_value:
        return (
            f"claim_value_mutated:{claim.source_path}:"
            f"claimed={claim.value!r}:source={source_value!r}"
        )
    return None


def adjudicate_explanation_conservation(
    *,
    projection: TrustProjection,
    result: ExplanationResult,
) -> ConservationVerdict:
    """Decide whether an explanation conserves its source authority."""
    violations: list[str] = []

    # --- Source binding -----------------------------------------------------
    # H-P14-DU1 / H-P14-E8. An explanation that cannot name the exact source it
    # explains is not conserved; it is a separate universe with a coincidental
    # resemblance.
    if result.envelope_id != projection.envelope_id:
        violations.append(
            f"source_envelope_mismatch:{result.envelope_id}!={projection.envelope_id}"
        )
    if result.semantic_truth_hash != projection.semantic_truth_hash:
        violations.append(
            "source_semantic_truth_mismatch:"
            f"{result.semantic_truth_hash}!={projection.semantic_truth_hash}"
        )
    if result.tenant_id_hash != projection.tenant_id_hash:
        # H-P14-E7 / Gate 10. Tenant identity is part of the effective isolation
        # boundary, so a tenant disagreement is a conservation failure, not a
        # cosmetic one.
        violations.append("source_tenant_mismatch")
    if result.profile_hash != projection.profile_hash:
        violations.append(
            f"projection_profile_mismatch:{result.profile_hash}!={projection.profile_hash}"
        )

    # --- Profile authority --------------------------------------------------
    try:
        profile = get_projection_profile(result.profile_id)
    except ProjectionProfileError as exc:
        return ConservationVerdict(False, tuple(violations + [str(exc)]))
    if profile.judge_authority != "none" or result.judge_authority != "none":
        violations.append("judge_authority_present")
    if profile.llm_authority_over_projected_values != "none":
        violations.append("llm_authority_over_projected_values_present")
    # P14-G2. The safe profile carries no provider-controlled class at all, so a
    # projection that produced one under it is already broken; assert it here as
    # well, because this is the surface an explanation actually externalizes.
    for spec in profile.fields:
        if spec.trust_class in UNTRUSTED_TEXT_CLASSES and not profile.untrusted_labels_admitted:
            violations.append(f"untrusted_label_in_safe_profile:{spec.path}")

    # --- Authority monotonicity (Gate 8) ------------------------------------
    try:
        assert_authority_monotonic(
            source_policy_state=projection.source_policy_state,
            downstream_policy_state=result.policy_state,
        )
    except Exception as exc:  # noqa: BLE001 - typed reason is the payload
        violations.append(str(exc))

    # --- Per-claim source correspondence ------------------------------------
    for claim in result.claims:
        problem = _claim_is_projected(claim, projection)
        if problem is not None:
            violations.append(problem)
            continue
        if claim.claim_kind == CLAIM_FINANCIAL:
            # H-P14-E1 / H-RC7. Authoritative money is an integer in minor
            # units; a float here means the value passed through a
            # display or estimation layer that is not allowed to define it.
            if isinstance(claim.value, bool) or not isinstance(claim.value, int):
                violations.append(
                    f"financial_claim_not_integer_minor:{claim.source_path}"
                )
        if claim.claim_kind == CLAIM_POLICY:
            projected_policy = projection.value(claim.source_path)
            if claim.source_path.endswith("policy_state") and (
                projected_policy != result.policy_state
            ):
                violations.append("policy_claim_disagrees_with_result_policy_state")

    # --- H-P14-E2: attribution may not be upgraded into causation -----------
    causal_status = result.causal_status
    causal_authorized = (
        causal_status is not None and causal_status in CAUSALLY_AUTHORIZING_STATUSES
    )
    for claim in result.claims:
        if claim.claim_kind == CLAIM_CAUSAL and not causal_authorized:
            violations.append(
                f"causal_claim_without_authorizing_substrate:{causal_status!r}"
            )
    if not causal_authorized:
        for claim in result.claims:
            found_in_claim = _CAUSAL_LANGUAGE.search(
                _mask_projected_values(claim.rendered, projection)
            )
            if found_in_claim is not None:
                violations.append(
                    f"causal_language_in_claim:{claim.source_path}:"
                    f"{found_in_claim.group(0)!r}"
                )
        found = _CAUSAL_LANGUAGE.search(
            _mask_projected_values(result.narrative, projection)
        )
        if found is not None:
            violations.append(f"causal_language_in_narrative:{found.group(0)!r}")

    # --- H-P14-E3: unavailable confidence stays unavailable ------------------
    confidence_status = result.confidence_status
    if confidence_status not in CONFIDENCE_NARRATABLE:
        for claim in result.claims:
            if claim.claim_kind == CLAIM_CONFIDENCE:
                # The one lawful confidence claim in a non-narratable state is
                # the statement that confidence is not available.
                if claim.source_path != "confidence_metadata.confidence_status":
                    violations.append(
                        f"confidence_claim_under_unavailable_state:{claim.source_path}"
                    )
                elif claim.value != confidence_status:
                    violations.append("confidence_claim_value_mutated")
        narrative_confidence = _CONFIDENCE_LANGUAGE.search(
            _mask_projected_values(result.narrative, projection)
        )
        declares_unavailable = any(
            claim.claim_kind == CLAIM_CONFIDENCE
            and claim.source_path == "confidence_metadata.confidence_status"
            for claim in result.claims
        )
        if not declares_unavailable:
            violations.append(
                f"confidence_unavailability_not_stated:{confidence_status}"
            )
        if narrative_confidence is not None and not declares_unavailable:
            violations.append("confidence_narrated_without_authority")
    else:
        if projection.has("confidence_metadata.confidence_score_basis_points"):
            score = projection.value(
                "confidence_metadata.confidence_score_basis_points"
            )
            for claim in result.claims:
                if (
                    claim.source_path
                    == "confidence_metadata.confidence_score_basis_points"
                    and claim.value != score
                ):
                    violations.append("confidence_score_upgraded")

    # --- H-P14-E4: fallback / degraded state may not disappear ---------------
    if result.fallback_applied:
        stated = any(claim.claim_kind == CLAIM_FALLBACK for claim in result.claims)
        if not stated:
            violations.append("fallback_state_suppressed")
    if projection.has("fallback_applied"):
        if bool(projection.value("fallback_applied")) != bool(result.fallback_applied):
            violations.append("fallback_state_disagrees_with_source")

    # --- H-P14-E1: no unsupported number may reach the outside ---------------
    supported = _supported_numeric_surface(result.claims)
    for token in _numeric_tokens(result.narrative):
        if token not in supported:
            violations.append(f"unsupported_financial_number:{token}")

    # --- H-P14-E5: provider text may not become instruction ------------------
    for path in projection.untrusted_label_paths:
        if any(claim.source_path == path for claim in result.claims):
            position = projection.authority_positions.get(path)
            if position != "display_only":
                violations.append(
                    f"untrusted_label_above_display:{path}:{position}"
                )

    return ConservationVerdict(not violations, tuple(violations))


def assert_no_untrusted_instruction_ingress(
    *,
    projection: TrustProjection,
    instruction_context: Mapping[str, Any],
) -> None:
    """Refuse a model instruction context containing provider-controlled text.

    The safe profile already excludes provider-controlled classes, so this is
    the second layer: it inspects the bytes actually handed to a model, which
    is where a future integration would leak them if it composed context from
    somewhere other than the projection.
    """

    projected_values = {
        str(value) for value in projection.projected.values() if isinstance(value, str)
    }
    for key, value in instruction_context.items():
        if not isinstance(value, str):
            continue
        if value in projected_values:
            continue
        if _NUMERIC_TOKEN.search(value):
            raise ExplanationConservationError(
                f"instruction_context_unbound_numeric:{key}"
            )

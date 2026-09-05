"""B2.7 closed narrative template registry.

The B2.7 conservation problem is open-world. A finite denylist of causal
phrasings cannot decide it: independent audits produced twenty ordinary English
sentences that asserted causation while matching no listed indicator, and the
next twenty would have been different again. Enumerating what is forbidden can
never close a set whose complement is "all of English".

This module inverts the quantifier. Instead of asking

    is this prose free of forbidden meaning?          (open world -- undecidable)

the boundary asks

    is this prose the deterministic rendering of a
    conserved typed claim through a registered
    template, with a machine-grammar value?           (closed world -- decidable)

Three properties make that a conservation mechanism rather than a bigger filter:

* **The template set is closed and content-addressed.** Every admissible
  sentence frame lives here, is hashed into
  ``EXPLANATION_TEMPLATE_REGISTRY_HASH``, and is mirrored row-for-row in
  ``b27_narrative_templates`` so the database enforces the same closure on a
  persisted artifact. Introducing a new frame is a migration and a registry-hash
  change -- a merge-governed act, not a runtime one.

* **The substituted value carries a machine grammar, not prose.** Each template
  declares a ``value_pattern``; none of them admits a free-form English phrase.
  A generator cannot smuggle a proposition through the one variable slot,
  because the slot only accepts hashes, enums, opaque identifiers, integers,
  booleans, currencies and one fixed money frame.

* **The narrative is the join, exactly.** ``compose_narrative`` is total over a
  claim sequence, and the adjudicator requires byte equality with it. There is
  no position -- prefix, suffix, interstitial sentence -- where unregistered
  language can live.

The consequence is the property the directive names: free-form wording cannot
increase causal authority *under unseen language*, because unseen language has
no representable position at all. The lexical sweep in
``app.explanation.conservation`` is retained as a second, independent layer and
is applied here at load time to the closed frame corpus, where a finite check
over a finite set is exactly the right instrument.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.explanation.contract import (
    CLAIM_CAUSAL,
    CLAIM_CONFIDENCE,
    CLAIM_FALLBACK,
    CLAIM_FINANCIAL,
    CLAIM_KINDS,
    CLAIM_POLICY,
    CLAIM_PROVENANCE,
    CLAIM_STATUS,
    ExplanationContractError,
)
from app.trust.refusal import tagged_sha256


EXPLANATION_TEMPLATE_REGISTRY_VERSION = "b25-p14-r4-explanation-templates-v1"

# The single separator ``compose_narrative`` uses. A narrative is the joined
# renderings and nothing else, so this constant is part of the safety relation.
NARRATIVE_JOINER = " "

# The substitution token. Exactly one variable position per frame, so the
# template's fixed text is the whole of its assertion.
VALUE_TOKEN = "{value}"


# Value grammars. Every one of these is a machine surface: none of them matches
# a phrase containing arbitrary English. ``money_minor`` carries fixed framing
# words, which is a constant of the grammar rather than a free position.
VALUE_PATTERNS: Mapping[str, str] = {
    "opaque_id": r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$",
    "hash": r"^sha256:[0-9a-f]{64}$",
    "enum": r"^[a-z][a-z0-9_]{0,63}$",
    "currency": r"^[A-Z]{3}$",
    "integer": r"^-?[0-9]{1,19}$",
    "money_minor": r"^-?[0-9]{1,19} minor units \(-?[0-9]{1,17}\.[0-9]{2}\)$",
    "boolean": r"^(true|false)$",
}


class ExplanationTemplateError(ExplanationContractError):
    """Raised when a template registry or a template use is inadmissible."""


@dataclass(frozen=True)
class NarrativeTemplate:
    """One admissible sentence frame, bound to one typed source path."""

    template_id: str
    claim_kind: str
    source_path: str
    text: str
    value_grammar: str

    @property
    def value_pattern(self) -> str:
        return VALUE_PATTERNS[self.value_grammar]

    def render(self, value_text: str) -> str:
        return self.text.replace(VALUE_TOKEN, value_text)


def _status(path: str, sentence: str, grammar: str = "enum") -> NarrativeTemplate:
    return NarrativeTemplate(
        template_id=f"status.{path.replace('.', '_')}.v1",
        claim_kind=CLAIM_STATUS,
        source_path=path,
        text=sentence,
        value_grammar=grammar,
    )


# ---------------------------------------------------------------------------
# The closed frame corpus.
# ---------------------------------------------------------------------------
# Every frame states an attribute of the source record. None of them relates two
# quantities, names an antecedent, or admits a subjunctive: a causal or
# counterfactual proposition has no frame to occupy. That is a property of this
# list, asserted mechanically by ``assert_registry_admissible`` and by the
# repository's own open-world corpus test.
EXPLANATION_TEMPLATES: tuple[NarrativeTemplate, ...] = (
    NarrativeTemplate(
        template_id="provenance.envelope_id.v1",
        claim_kind=CLAIM_PROVENANCE,
        source_path="envelope_id",
        text="This explanation is bound to envelope_id {value}.",
        value_grammar="opaque_id",
    ),
    NarrativeTemplate(
        template_id="provenance.semantic_truth_hash.v1",
        claim_kind=CLAIM_PROVENANCE,
        source_path="semantic_truth_hash",
        text="This explanation is bound to semantic_truth_hash {value}.",
        value_grammar="hash",
    ),
    NarrativeTemplate(
        template_id="provenance.audit_ref.v1",
        claim_kind=CLAIM_PROVENANCE,
        source_path="audit_ref",
        text="This explanation is bound to audit_ref {value}.",
        value_grammar="opaque_id",
    ),
    NarrativeTemplate(
        template_id="financial.verified_revenue_minor.v1",
        claim_kind=CLAIM_FINANCIAL,
        source_path="verified_revenue_minor",
        text="Verified revenue is {value}.",
        value_grammar="money_minor",
    ),
    NarrativeTemplate(
        template_id="status.currency.v1",
        claim_kind=CLAIM_STATUS,
        source_path="currency",
        text="Amounts are denominated in {value}.",
        value_grammar="currency",
    ),
    _status(
        "deterministic_verification_status",
        "Deterministic verification status is {value}.",
    ),
    _status("match_verdict_status", "The match verdict is {value}."),
    _status("discrepancy_class", "The reconciliation discrepancy class is {value}."),
    _status("attribution_model", "The attribution model applied is {value}."),
    _status("model_assumption", "The model assumption is {value}."),
    _status("causal_status", "The causal status of this result is {value}."),
    _status("data_completeness_status", "Data completeness is {value}."),
    _status("truth_type", "The truth type is {value}."),
    _status("truth_authority.authority_class", "The authority class is {value}."),
    _status(
        "confidence_metadata.unavailable_reason",
        "The recorded confidence unavailability reason is {value}.",
    ),
    NarrativeTemplate(
        template_id="confidence.confidence_status.v1",
        claim_kind=CLAIM_CONFIDENCE,
        source_path="confidence_metadata.confidence_status",
        text="The recorded confidence status is {value}.",
        value_grammar="enum",
    ),
    NarrativeTemplate(
        template_id="confidence.confidence_score_basis_points.v1",
        claim_kind=CLAIM_CONFIDENCE,
        source_path="confidence_metadata.confidence_score_basis_points",
        text="The projected confidence is {value} basis points.",
        value_grammar="integer",
    ),
    NarrativeTemplate(
        template_id="fallback.fallback_applied.v1",
        claim_kind=CLAIM_FALLBACK,
        source_path="fallback_applied",
        text="The declared fallback state is {value}.",
        value_grammar="boolean",
    ),
    NarrativeTemplate(
        template_id="fallback.fallback_reason.v1",
        claim_kind=CLAIM_FALLBACK,
        source_path="fallback_reason",
        text="The declared fallback reason is {value}.",
        value_grammar="enum",
    ),
    NarrativeTemplate(
        template_id="policy.policy_state.v1",
        claim_kind=CLAIM_POLICY,
        source_path="policy_action_authority.policy_state",
        text="The policy authority for this subject is {value}.",
        value_grammar="enum",
    ),
)


TEMPLATE_BY_ID: Mapping[str, NarrativeTemplate] = {
    template.template_id: template for template in EXPLANATION_TEMPLATES
}
TEMPLATE_BY_BINDING: Mapping[tuple[str, str], NarrativeTemplate] = {
    (template.claim_kind, template.source_path): template
    for template in EXPLANATION_TEMPLATES
}


def template_for(claim_kind: str, source_path: str) -> NarrativeTemplate | None:
    return TEMPLATE_BY_BINDING.get((claim_kind, source_path))


def canonical_value_text(source_path: str, value: Any) -> str:
    """The one admissible textual rendering of a conserved claim value.

    Deterministic and total over the value types a projection can carry. The
    money form spells both the authoritative minor-unit integer and the
    major-unit rendering the P11 display contract already produces, so the
    conservation checker's supported numeric surface and the narrative agree by
    construction rather than by coincidence.
    """

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        if source_path.endswith("_minor"):
            major, cents = divmod(abs(value), 100)
            sign = "-" if value < 0 else ""
            return f"{value} minor units ({sign}{major}.{cents:02d})"
        return str(value)
    if isinstance(value, str):
        return value
    raise ExplanationTemplateError(
        f"explanation_value_not_renderable:{source_path}:{type(value).__name__}"
    )


def render_claim(claim_kind: str, source_path: str, value: Any) -> tuple[str, str, str]:
    """Return ``(template_id, value_text, rendered)`` for one conserved claim."""

    template = template_for(claim_kind, source_path)
    if template is None:
        raise ExplanationTemplateError(
            f"explanation_template_missing:{claim_kind}:{source_path}"
        )
    value_text = canonical_value_text(source_path, value)
    if re.match(template.value_pattern, value_text) is None:
        raise ExplanationTemplateError(
            f"explanation_value_grammar_violated:{template.template_id}"
        )
    return template.template_id, value_text, template.render(value_text)


def compose_narrative(renderings: "tuple[str, ...] | list[str]") -> str:
    """The one admissible narrative for a claim sequence: the exact join."""

    return NARRATIVE_JOINER.join(renderings)


def registry_rows() -> tuple[dict[str, str], ...]:
    """The registry in the shape the database mirror stores."""

    return tuple(
        {
            "template_id": template.template_id,
            "claim_kind": template.claim_kind,
            "source_path": template.source_path,
            "template_text": template.text,
            "value_grammar": template.value_grammar,
            "value_pattern": template.value_pattern,
        }
        for template in EXPLANATION_TEMPLATES
    )


def explanation_template_registry_hash() -> str:
    """Content address over the closed frame corpus.

    A persisted explanation names this hash, so an auditor holding only the
    downstream artifact can say which frame corpus produced it. Adding a frame
    moves the hash; reformatting this module's prose does not.
    """

    material = {
        "registry_version": EXPLANATION_TEMPLATE_REGISTRY_VERSION,
        "joiner": NARRATIVE_JOINER,
        "value_token": VALUE_TOKEN,
        "templates": [dict(row) for row in registry_rows()],
    }
    return tagged_sha256(material)


# ---------------------------------------------------------------------------
# Load-time admissibility of the corpus itself.
# ---------------------------------------------------------------------------
# A closed corpus moves the safety question from "is this sentence safe?" to "is
# this *frame* safe?", over a set of twenty. That is the point at which a finite
# lexical check is the right instrument rather than the wrong one, so an
# indicator sweep is applied here -- to the frames, at load, where the set is
# closed and every entry is human-adjudicated at merge time.

# Like the conservation checker's own sweep, this deliberately does not match
# the bare adjective in "causal status": naming the field whose whole job is to
# say that causality was *not* estimated is a statement about the absence of a
# causal claim, and a corpus that could not say so would be less honest, not
# more. What is refused is causal verbs, causal connectives, subjunctives,
# comparatives and the noun phrases that assert a causal relation.
_FRAME_FORBIDDEN = re.compile(
    r"\b("
    r"caused|causes|causing|causally|"
    r"causal\s+(?:effect|impact|relationship|contribution|attribution|lift|"
    r"influence|role|link|driver)s?|"
    r"drove|drives|driving|because|due\s+to|as\s+a\s+result\s+of|result\s+of|"
    r"led\s+to|leads\s+to|leading\s+to|"
    r"incremental(?:ity|ly)?|uplift|lift\s+from|"
    r"attributable\s+to|responsible\s+for|"
    r"generated|produced|produces|producing|yield|yields|yielded|"
    r"boost|boosts|boosted|thanks\s+to|would|could|should|explains|"
    r"impact|impacts|impacted|increase|increases|increased|"
    r"decrease|decreases|decreased|effect|effects|"
    r"contribution|contributes|contributed|counterfactual|"
    r"stems\s+from|traces\s+back|credit|makes|make|"
    r"if|unless|without|when|had|more|less|than"
    r")\b",
    re.IGNORECASE,
)
_FRAME_DIGIT = re.compile(r"\d")


def assert_registry_admissible() -> None:
    """Refuse a frame corpus that could carry authority the source lacks."""

    seen_ids: set[str] = set()
    seen_bindings: set[tuple[str, str]] = set()
    for template in EXPLANATION_TEMPLATES:
        if template.claim_kind not in CLAIM_KINDS:
            raise ExplanationTemplateError(
                f"explanation_template_kind_unknown:{template.template_id}"
            )
        if template.claim_kind == CLAIM_CAUSAL:
            # No frame may state a causal proposition. B2.13 is the phase that
            # would introduce a causal substrate; until it exists there is no
            # authority a causal frame could conserve, so the frame may not
            # exist either.
            raise ExplanationTemplateError(
                f"explanation_template_causal_kind_forbidden:{template.template_id}"
            )
        if template.value_grammar not in VALUE_PATTERNS:
            raise ExplanationTemplateError(
                f"explanation_template_grammar_unknown:{template.template_id}"
            )
        if template.text.count(VALUE_TOKEN) != 1:
            raise ExplanationTemplateError(
                f"explanation_template_variable_positions:{template.template_id}"
            )
        fixed = template.text.replace(VALUE_TOKEN, " ")
        if _FRAME_DIGIT.search(fixed) is not None:
            raise ExplanationTemplateError(
                f"explanation_template_fixed_numeral:{template.template_id}"
            )
        found = _FRAME_FORBIDDEN.search(fixed)
        if found is not None:
            raise ExplanationTemplateError(
                f"explanation_template_causal_frame:{template.template_id}:"
                f"{found.group(0)!r}"
            )
        if template.template_id in seen_ids:
            raise ExplanationTemplateError(
                f"explanation_template_duplicate_id:{template.template_id}"
            )
        binding = (template.claim_kind, template.source_path)
        if binding in seen_bindings:
            raise ExplanationTemplateError(
                f"explanation_template_duplicate_binding:{binding}"
            )
        seen_ids.add(template.template_id)
        seen_bindings.add(binding)


assert_registry_admissible()

EXPLANATION_TEMPLATE_REGISTRY_HASH = explanation_template_registry_hash()


__all__ = [
    "EXPLANATION_TEMPLATES",
    "EXPLANATION_TEMPLATE_REGISTRY_HASH",
    "EXPLANATION_TEMPLATE_REGISTRY_VERSION",
    "NARRATIVE_JOINER",
    "NarrativeTemplate",
    "ExplanationTemplateError",
    "TEMPLATE_BY_BINDING",
    "TEMPLATE_BY_ID",
    "VALUE_PATTERNS",
    "VALUE_TOKEN",
    "assert_registry_admissible",
    "canonical_value_text",
    "compose_narrative",
    "explanation_template_registry_hash",
    "registry_rows",
    "render_claim",
    "template_for",
]

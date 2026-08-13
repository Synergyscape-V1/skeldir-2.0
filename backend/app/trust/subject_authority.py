"""Canonical subject and physical-source authority for TrustEnvelope issuance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectAuthorityDefinition:
    """One subject's governed upstream and direct read topology."""

    subject_type: str
    source_authority_class: str
    governed_source_tables: tuple[str, ...]
    physical_read_tables: tuple[str, ...]


SUBJECT_AUTHORITY_DEFINITIONS: dict[str, SubjectAuthorityDefinition] = {
    "match_verdict": SubjectAuthorityDefinition(
        subject_type="match_verdict",
        source_authority_class="deterministic_machine_fact",
        governed_source_tables=("b23_match_verdicts", "b23_revenue_events"),
        physical_read_tables=("b23_match_verdicts",),
    ),
    "confidence_projection": SubjectAuthorityDefinition(
        subject_type="confidence_projection",
        source_authority_class="confidence_metadata_projection",
        # The four B2.4 snapshot families are committed by source_snapshot_hash.
        # Fits/artifacts carry the classified truth, while append-only dirty
        # events are the bounded durable authority for post-fit invalidation.
        governed_source_tables=(
            "attribution_allocations",
            "attribution_events",
            "b23_match_verdicts",
            "b23_revenue_events",
            "b24_dirty_events",
            "bayesian_artifacts",
            "bayesian_model_fits",
        ),
        physical_read_tables=(
            "b24_dirty_events",
            "bayesian_artifacts",
            "bayesian_model_fits",
        ),
    ),
}


def subject_authority_definition(subject_type: str) -> SubjectAuthorityDefinition:
    """Return the canonical authority definition for a supported subject."""

    try:
        return SUBJECT_AUTHORITY_DEFINITIONS[subject_type]
    except KeyError as exc:
        raise ValueError(f"unsupported_subject_authority:{subject_type}") from exc


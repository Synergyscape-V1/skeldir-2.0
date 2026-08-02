"""B2.5-P5 field-source registry and deterministic source adapters."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession


SourceClass = Literal[
    "authoritative_source",
    "deterministic_default",
    "explicit_unavailable",
    "typed_refusal",
    "derived_from_prior_phase_adapter",
    "future_phase_placeholder",
]

AuthorityClass = Literal[
    "deterministic_machine_fact",
    "deterministic_projection",
    "explicitly_unavailable",
    "refusal_or_degraded_state",
    "p3_text_disposition",
    "p4_money_authority",
    "p5_unsigned_placeholder",
]

SUPPORTED_P5_SUBJECT_TYPES = frozenset({"match_verdict"})
_MATCH_VERDICT_REF_RE = re.compile(
    r"^urn:skeldir:match_verdict:(?P<verdict_id>[0-9a-fA-F-]{36})$"
)


@dataclass(frozen=True)
class FieldSourceDecision:
    """One TrustEnvelope field's declared source authority."""

    field_name: str
    source_class: SourceClass
    authority_class: AuthorityClass
    source_path: str
    required: bool = True
    reason_code: str | None = None

    def external_projection(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MatchVerdictSource:
    """Approved B2.3 match-verdict source row for P5 builder assembly."""

    id: UUID
    tenant_id: UUID
    webhook_ingress_identity_id: UUID | None
    provider: str
    canonical_commerce_reference: str
    provider_native_event_reference: str
    provider_native_commerce_reference: str
    status: str
    match_quality: str
    canonical_net_verified_amount_minor: object
    currency_code: str
    last_transition_at: datetime
    created_at: datetime
    updated_at: datetime


TRUST_ENVELOPE_FIELD_SOURCE_REGISTRY: dict[str, FieldSourceDecision] = {
    "envelope_version": FieldSourceDecision(
        "envelope_version",
        "deterministic_default",
        "deterministic_machine_fact",
        "contracts/trust-api/trust-envelope.v1.yaml",
    ),
    "schema_version": FieldSourceDecision(
        "schema_version",
        "deterministic_default",
        "deterministic_machine_fact",
        "contracts/trust-api/schema-version-registry.yaml",
    ),
    "canonicalization_version": FieldSourceDecision(
        "canonicalization_version",
        "deterministic_default",
        "deterministic_machine_fact",
        "contracts/trust-api/canonicalization-version-registry.yaml",
    ),
    "envelope_id": FieldSourceDecision(
        "envelope_id",
        "deterministic_default",
        "p5_unsigned_placeholder",
        "backend/app/trust/builder.py",
    ),
    "tenant_id_hash": FieldSourceDecision(
        "tenant_id_hash",
        "deterministic_default",
        "deterministic_machine_fact",
        "backend/app/trust/refusal.py:tenant_hash",
    ),
    "audience_binding": FieldSourceDecision(
        "audience_binding",
        "deterministic_default",
        "p5_unsigned_placeholder",
        "backend/app/trust/refusal.py:default_audience_binding",
    ),
    "subject_authority": FieldSourceDecision(
        "subject_authority",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts",
    ),
    "subject_type": FieldSourceDecision(
        "subject_type",
        "authoritative_source",
        "deterministic_machine_fact",
        "build_request.subject_type",
    ),
    "subject_ref": FieldSourceDecision(
        "subject_ref",
        "authoritative_source",
        "deterministic_machine_fact",
        "build_request.subject_ref",
    ),
    "subject_ref_hash": FieldSourceDecision(
        "subject_ref_hash",
        "deterministic_default",
        "deterministic_machine_fact",
        "backend/app/trust/refusal.py:tagged_sha256",
    ),
    "truth_type": FieldSourceDecision(
        "truth_type",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts",
    ),
    "truth_authority": FieldSourceDecision(
        "truth_authority",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts",
    ),
    "match_verdict_status": FieldSourceDecision(
        "match_verdict_status",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts.status",
    ),
    "confidence_metadata": FieldSourceDecision(
        "confidence_metadata",
        "explicit_unavailable",
        "explicitly_unavailable",
        "b24_confidence_projection_unavailable_for_match_verdict",
    ),
    "provenance_chain": FieldSourceDecision(
        "provenance_chain",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts",
    ),
    "data_completeness_status": FieldSourceDecision(
        "data_completeness_status",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts.status",
    ),
    "benchmark_metadata": FieldSourceDecision(
        "benchmark_metadata",
        "explicit_unavailable",
        "explicitly_unavailable",
        "backend/app/trust/benchmark_defaults.py",
    ),
    "policy_action_authority": FieldSourceDecision(
        "policy_action_authority",
        "deterministic_default",
        "p5_unsigned_placeholder",
        "backend/app/trust/policy_defaults.py",
    ),
    "fallback_applied": FieldSourceDecision(
        "fallback_applied",
        "deterministic_default",
        "deterministic_machine_fact",
        "p5_match_verdict_no_fallback",
    ),
    "fallback_reason": FieldSourceDecision(
        "fallback_reason",
        "deterministic_default",
        "deterministic_machine_fact",
        "p5_match_verdict_no_fallback",
    ),
    "evidence_temporal_boundary": FieldSourceDecision(
        "evidence_temporal_boundary",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts timestamps",
    ),
    "audit_ref": FieldSourceDecision(
        "audit_ref",
        "future_phase_placeholder",
        "p5_unsigned_placeholder",
        "p7_trust_access_audit_deferred",
    ),
    "audit_hash": FieldSourceDecision(
        "audit_hash",
        "future_phase_placeholder",
        "p5_unsigned_placeholder",
        "p7_trust_access_audit_deferred",
    ),
    "semantic_truth_hash": FieldSourceDecision(
        "semantic_truth_hash",
        "derived_from_prior_phase_adapter",
        "deterministic_machine_fact",
        "backend/app/trust/hash_identity.py",
    ),
    "artifact_ref": FieldSourceDecision(
        "artifact_ref",
        "explicit_unavailable",
        "explicitly_unavailable",
        "p8_signature_artifact_not_in_p5_scope",
    ),
    "artifact_hash": FieldSourceDecision(
        "artifact_hash",
        "explicit_unavailable",
        "explicitly_unavailable",
        "p8_signature_artifact_not_in_p5_scope",
    ),
    "signature_hash": FieldSourceDecision(
        "signature_hash",
        "future_phase_placeholder",
        "p5_unsigned_placeholder",
        "p8_signing_deferred",
    ),
    "signature": FieldSourceDecision(
        "signature",
        "future_phase_placeholder",
        "p5_unsigned_placeholder",
        "p8_signing_deferred",
    ),
    "signing_algorithm": FieldSourceDecision(
        "signing_algorithm",
        "future_phase_placeholder",
        "p5_unsigned_placeholder",
        "p8_signing_deferred",
    ),
    "signing_key_id": FieldSourceDecision(
        "signing_key_id",
        "future_phase_placeholder",
        "p5_unsigned_placeholder",
        "p8_signing_deferred",
    ),
    "created_at": FieldSourceDecision(
        "created_at",
        "authoritative_source",
        "deterministic_machine_fact",
        "b23_match_verdicts.updated_at",
    ),
    "valid_until": FieldSourceDecision(
        "valid_until",
        "deterministic_default",
        "p5_unsigned_placeholder",
        "request_context.valid_until",
    ),
    "untrusted_display_data": FieldSourceDecision(
        "untrusted_display_data",
        "derived_from_prior_phase_adapter",
        "p3_text_disposition",
        "backend/app/trust/text_disposition.py",
    ),
    "verified_revenue_minor": FieldSourceDecision(
        "verified_revenue_minor",
        "derived_from_prior_phase_adapter",
        "p4_money_authority",
        "backend/app/trust/money_source_adapter.py",
        required=False,
    ),
}


def iter_field_source_decisions() -> tuple[FieldSourceDecision, ...]:
    """Return deterministic P5 field-source decisions."""
    return tuple(
        TRUST_ENVELOPE_FIELD_SOURCE_REGISTRY[key]
        for key in sorted(TRUST_ENVELOPE_FIELD_SOURCE_REGISTRY)
    )


def parse_match_verdict_subject_ref(subject_ref: str) -> UUID | None:
    """Return the verdict UUID embedded in a match-verdict subject URN."""
    match = _MATCH_VERDICT_REF_RE.fullmatch(str(subject_ref or ""))
    if match is None:
        return None
    return UUID(match.group("verdict_id"))


def normalize_match_verdict_status(source_status: str) -> str:
    """Map internal B2.3 lifecycle states to TrustEnvelope status enums."""
    status = str(source_status or "").strip().lower()
    return {
        "matched_confirmed": "matched",
        "adjusted": "matched",
        "matched_provisional": "ambiguous",
        "pending": "insufficient_evidence",
        "unmatched": "unmatched",
    }.get(status, "unavailable")


def data_completeness_for_match_status(source_status: str) -> str:
    """Return explicit completeness semantics for a match-verdict source state."""
    mapped = normalize_match_verdict_status(source_status)
    if mapped == "matched":
        return "complete"
    if mapped in {"ambiguous", "insufficient_evidence"}:
        return "insufficient_evidence"
    if mapped == "unmatched":
        return "partial"
    return "unavailable"


def match_verdict_source_from_mapping(row: Any) -> MatchVerdictSource:
    """Build a typed source row from a SQLAlchemy mapping or test fixture mapping."""
    mapping = dict(row)
    return MatchVerdictSource(
        id=UUID(str(mapping["id"])),
        tenant_id=UUID(str(mapping["tenant_id"])),
        webhook_ingress_identity_id=(
            UUID(str(mapping["webhook_ingress_identity_id"]))
            if mapping.get("webhook_ingress_identity_id") is not None
            else None
        ),
        provider=str(mapping["provider"]),
        canonical_commerce_reference=str(mapping["canonical_commerce_reference"]),
        provider_native_event_reference=str(mapping["provider_native_event_reference"]),
        provider_native_commerce_reference=str(
            mapping["provider_native_commerce_reference"]
        ),
        status=str(mapping["status"]),
        match_quality=str(mapping["match_quality"]),
        canonical_net_verified_amount_minor=mapping[
            "canonical_net_verified_amount_minor"
        ],
        currency_code=str(mapping["currency_code"]).strip().upper(),
        last_transition_at=mapping["last_transition_at"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


async def read_match_verdict_source(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    subject_ref: str,
) -> MatchVerdictSource | None:
    """Read a B2.3 match verdict by tenant and subject without writes or side effects."""
    verdict_id = parse_match_verdict_subject_ref(subject_ref)
    if verdict_id is None:
        return None
    result = await session.execute(
        text(
            """
            SELECT
                id,
                tenant_id,
                webhook_ingress_identity_id,
                provider,
                canonical_commerce_reference,
                provider_native_event_reference,
                provider_native_commerce_reference,
                status,
                match_quality,
                canonical_net_verified_amount_minor,
                currency_code,
                last_transition_at,
                created_at,
                updated_at
            FROM public.b23_match_verdicts
            WHERE tenant_id = :tenant_id
              AND id = :verdict_id
            """
        ),
        {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return match_verdict_source_from_mapping(row)


async def query_match_verdict_sources(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    subject_refs: Sequence[str],
    updated_at_after: datetime | None = None,
    updated_at_before: datetime | None = None,
    row_limit: int = 50,
) -> tuple[MatchVerdictSource, ...]:
    """Read a bounded exact-reference set using persisted verdict chronology.

    P10's temporal predicate is defined over ``b23_match_verdicts.updated_at``.
    The caller supplies exact subject URNs only; malformed references are normal
    non-matches and never broaden the query.  The SQL limit is applied before
    P5 build, signing, audit, or response serialization work.
    """
    if row_limit < 1 or row_limit > 50:
        raise ValueError("match_verdict_row_limit_out_of_bounds")
    if len(subject_refs) > 50:
        raise ValueError("match_verdict_reference_limit_exceeded")
    if updated_at_after is not None and (
        updated_at_after.tzinfo is None or updated_at_after.utcoffset() is None
    ):
        raise ValueError("updated_at_after_timezone_required")
    if updated_at_before is not None and (
        updated_at_before.tzinfo is None or updated_at_before.utcoffset() is None
    ):
        raise ValueError("updated_at_before_timezone_required")

    verdict_ids = sorted(
        {
            verdict_id
            for subject_ref in subject_refs
            if (verdict_id := parse_match_verdict_subject_ref(subject_ref)) is not None
        },
        key=str,
    )
    if not verdict_ids:
        return ()

    predicates = ["tenant_id = :tenant_id", "id = ANY(:verdict_ids)"]
    params: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "verdict_ids": verdict_ids,
        "row_limit": row_limit,
    }
    if updated_at_after is not None:
        predicates.append("updated_at >= :updated_at_after")
        params["updated_at_after"] = updated_at_after.astimezone(timezone.utc)
    if updated_at_before is not None:
        predicates.append("updated_at <= :updated_at_before")
        params["updated_at_before"] = updated_at_before.astimezone(timezone.utc)

    statement = text(
        f"""
        SELECT
            id,
            tenant_id,
            webhook_ingress_identity_id,
            provider,
            canonical_commerce_reference,
            provider_native_event_reference,
            provider_native_commerce_reference,
            status,
            match_quality,
            canonical_net_verified_amount_minor,
            currency_code,
            last_transition_at,
            created_at,
            updated_at
        FROM public.b23_match_verdicts
        WHERE {' AND '.join(predicates)}
        ORDER BY updated_at ASC, id ASC
        LIMIT :row_limit
        """
    ).bindparams(
        bindparam(
            "verdict_ids",
            type_=ARRAY(PG_UUID(as_uuid=True)),
        )
    )
    result = await session.execute(statement, params)
    return tuple(match_verdict_source_from_mapping(row) for row in result.mappings())

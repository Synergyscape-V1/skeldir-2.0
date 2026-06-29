"""B2.5-P5 unsigned read-only TrustEnvelope payload builder."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.trust.benchmark_defaults import unavailable_benchmark_metadata
from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.hash_identity import compute_semantic_truth_hash, compute_signature_hash
from app.trust.money_source_adapter import (
    AuthoritativeMoneyMinor,
    MoneyAuthorityDecision,
    resolve_authoritative_money,
)
from app.trust.policy_defaults import read_only_policy_authority
from app.trust.refusal import (
    build_error_envelope,
    default_audience_binding,
    tagged_sha256,
    tenant_hash,
    utc_second,
)
from app.trust.schema_versions import validate_schema_canonicalization_compatibility
from app.trust.source_adapters import (
    SUPPORTED_P5_SUBJECT_TYPES,
    FieldSourceDecision,
    MatchVerdictSource,
    data_completeness_for_match_status,
    iter_field_source_decisions,
    normalize_match_verdict_status,
    read_match_verdict_source,
)
from app.trust.text_disposition import dispose_text_for_field


BuildStatus = Literal["success", "refused", "degraded"]

_PLACEHOLDER_SHA = "sha256:" + ("0" * 64)
_P5_SIGNATURE_PLACEHOLDER = "p5-unsigned-placeholder-signature"
_P5_SIGNING_KEY_PLACEHOLDER = "kid:b25-p5-unsigned-placeholder"


class TrustEnvelopeBuildError(ValueError):
    """Raised when an unsigned TrustEnvelope cannot be built safely."""


@dataclass(frozen=True)
class TrustEnvelopeBuildRequest:
    """Strict P5 builder input."""

    tenant_id: UUID
    subject_type: str
    subject_ref: str
    request_context: dict[str, object]
    schema_version: str = "trust-envelope-schema-v1"
    canonicalization_version: str = "trust-canonical-json-v1"


@dataclass(frozen=True)
class ReadOnlyObservation:
    """Test-facing proof metadata for P5 no-mutation behavior."""

    source_reads: int
    source_writes: int
    task_dispatches: int
    artifact_writes: int
    export_writes: int
    audit_writes: int
    llm_calls: int
    runtime_llm_modules_loaded: tuple[str, ...]

    def external_projection(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TrustEnvelopeBuildResult:
    """Strict P5 builder output."""

    status: BuildStatus
    unsigned_payload: dict[str, Any] | None
    refusal_payload: dict[str, Any] | None
    reason_code: str | None
    field_source_decisions: tuple[FieldSourceDecision, ...]
    money_authority_decision: MoneyAuthorityDecision | None
    read_only_observation: ReadOnlyObservation


def _context_datetime(
    request_context: dict[str, object],
    key: str,
    fallback: datetime,
) -> datetime:
    value = request_context.get(key)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return fallback


def _source_snapshot_hash(source: MatchVerdictSource) -> str:
    return tagged_sha256(
        {
            "source": "b23_match_verdicts",
            "id": str(source.id),
            "status": source.status,
            "amount_minor": source.canonical_net_verified_amount_minor,
            "currency": source.currency_code,
            "updated_at": utc_second(source.updated_at),
        }
    )


def _subject_ref_hash(subject_ref: str) -> str:
    return tagged_sha256({"subject_ref": subject_ref})


def _envelope_id(
    *,
    tenant_id_hash: str,
    subject_ref: str,
    schema_version: str,
    canonicalization_version: str,
) -> str:
    digest = tagged_sha256(
        {
            "tenant_id_hash": tenant_id_hash,
            "subject_ref": subject_ref,
            "schema_version": schema_version,
            "canonicalization_version": canonicalization_version,
            "phase": "b25-p5-unsigned-builder",
        }
    ).split(":", 1)[1]
    return f"env_{digest[:32]}"


def _confidence_unavailable() -> dict[str, object]:
    return {
        "confidence_status": "unavailable",
        "confidence_authority": "deterministic_only",
        "confidence_score_basis_points": None,
        "bayesian_model_type": "deterministic_only",
        "bayesian_model_version": None,
        "diagnostics_status": "not_applicable",
        "unavailable_reason": "not_applicable",
    }


def _display_data_from_provider_text(raw_text: str) -> dict[str, object]:
    decision = dispose_text_for_field(
        field_path="untrusted_display_data.display_text",
        raw_text=raw_text,
        source="provider",
    )
    projection = decision.external_projection()
    action = projection["disposition_action"]
    display_transform = "none"
    text_trust_class = projection["text_trust_class"]
    if action == "emit_untrusted_display_label":
        display_transform = "escaped_display_only"
    elif action in {
        "omit_raw_text_and_emit_quarantine_metadata",
        "redact_with_reason",
    }:
        display_transform = "redacted"
        if text_trust_class == "untrusted_display_label":
            text_trust_class = "quarantined_text_hash"
    return {
        "text_trust_class": text_trust_class,
        "content_safety_flags": projection["content_safety_flags"],
        "disposition_action": action,
        "raw_text_sha256": projection["raw_text_sha256"],
        "raw_text_hmac": projection["raw_text_hmac"],
        "display_text": projection["display_text"],
        "normalized_display_text": projection["normalized_display_text"],
        "display_transform": display_transform,
        "opaque_reference_hash": projection["opaque_reference_hash"],
        "opaque_reference_metadata": projection["opaque_reference_metadata"],
        "redaction_reason": projection["redaction_reason"],
        "text_disposition_version": projection["text_disposition_version"],
    }


def _provenance_display_metadata(display_data: dict[str, object]) -> dict[str, object]:
    raw_hash = display_data.get("raw_text_sha256")
    transform = str(display_data.get("display_transform") or "none")
    if raw_hash:
        return {
            "text_trust_class": "provider_controlled_quarantined",
            "raw_text_sha256": raw_hash,
            "display_transform": "redacted",
        }
    if transform == "escaped_display_only":
        return {
            "text_trust_class": "operator_controlled_safe_label",
            "raw_text_sha256": None,
            "display_transform": "escaped_display_only",
        }
    return {
        "text_trust_class": "none",
        "raw_text_sha256": None,
        "display_transform": "none",
    }


def _match_verdict_payload(
    *,
    request: TrustEnvelopeBuildRequest,
    source: MatchVerdictSource,
    money_decision: AuthoritativeMoneyMinor,
) -> dict[str, Any]:
    tenant_id_hash = tenant_hash(request.tenant_id)
    subject_ref_hash = _subject_ref_hash(request.subject_ref)
    source_snapshot_hash = _source_snapshot_hash(source)
    source_ref = f"urn:skeldir:b23_match_verdicts:{source.id}"
    source_ref_hash = tagged_sha256({"source_ref": source_ref})
    observed_at = source.last_transition_at
    created_at = _context_datetime(
        request.request_context, "created_at", source.updated_at
    )
    valid_until = _context_datetime(
        request.request_context,
        "valid_until",
        created_at + timedelta(hours=24),
    )
    audience_id = str(
        request.request_context.get("audience_id") or "b25-p5-internal-builder"
    )
    display_data = _display_data_from_provider_text(source.canonical_commerce_reference)
    payload: dict[str, Any] = {
        "envelope_version": "trust-envelope-v1",
        "schema_version": request.schema_version,
        "canonicalization_version": request.canonicalization_version,
        "envelope_id": _envelope_id(
            tenant_id_hash=tenant_id_hash,
            subject_ref=request.subject_ref,
            schema_version=request.schema_version,
            canonicalization_version=request.canonicalization_version,
        ),
        "tenant_id_hash": tenant_id_hash,
        "audience_binding": default_audience_binding(audience_id=audience_id),
        "subject_authority": {
            "subject_type": "match_verdict",
            "subject_ref": request.subject_ref,
            "subject_ref_hash": subject_ref_hash,
            "source_authority_class": "deterministic_machine_fact",
            "allowed_source_tables": ["b23_match_verdicts", "b23_revenue_events"],
            "mutable_workflow_subject": False,
        },
        "subject_type": "match_verdict",
        "subject_ref": request.subject_ref,
        "subject_ref_hash": subject_ref_hash,
        "truth_type": "deterministic_match_verdict",
        "truth_authority": {
            "authority_class": "deterministic_machine_fact",
            "source_snapshot_hash": source_snapshot_hash,
            "source_system": "skeldir_b23_match_engine",
        },
        "match_verdict_status": normalize_match_verdict_status(source.status),
        "confidence_metadata": _confidence_unavailable(),
        "provenance_chain": [
            {
                "provenance_type": "match_verdict",
                "authority_table": "b23_match_verdicts",
                "source_ref": source_ref,
                "source_ref_hash": source_ref_hash,
                "source_snapshot_hash": source_snapshot_hash,
                "observed_at": utc_second(observed_at),
                "display_metadata": _provenance_display_metadata(display_data),
            }
        ],
        "data_completeness_status": data_completeness_for_match_status(source.status),
        "benchmark_metadata": unavailable_benchmark_metadata(),
        "policy_action_authority": read_only_policy_authority(),
        "fallback_applied": False,
        "fallback_reason": "none",
        "evidence_temporal_boundary": {
            "evidence_snapshot_at": utc_second(source.updated_at),
            "source_read_started_at": utc_second(created_at),
            "source_read_completed_at": utc_second(created_at),
            "data_freshness_seconds": 0,
            "staleness_status": "current",
            "evidence_snapshot_hash": source_snapshot_hash,
            "max_source_read_skew_ms": 0,
            "snapshot_consistency_status": "consistent",
        },
        "audit_ref": "urn:skeldir:audit:p5_unsigned_builder_unissued",
        "audit_hash": tagged_sha256(
            {
                "p5_audit_placeholder": "not_persisted",
                "tenant_id_hash": tenant_id_hash,
                "subject_ref_hash": subject_ref_hash,
            }
        ),
        "semantic_truth_hash": _PLACEHOLDER_SHA,
        "artifact_ref": None,
        "artifact_hash": None,
        "signature_hash": _PLACEHOLDER_SHA,
        "signature": _P5_SIGNATURE_PLACEHOLDER,
        "signing_algorithm": "ed25519",
        "signing_key_id": _P5_SIGNING_KEY_PLACEHOLDER,
        "created_at": utc_second(created_at),
        "valid_until": utc_second(valid_until),
        "untrusted_display_data": display_data,
    }
    payload["semantic_truth_hash"] = compute_semantic_truth_hash(payload)
    payload["signature_hash"] = compute_signature_hash(payload)
    canonicalize_envelope_payload(payload)
    if money_decision.amount_minor is None:
        raise TrustEnvelopeBuildError("accepted_money_authority_missing_amount")
    return payload


def _money_decision_for_match_verdict(
    source: MatchVerdictSource,
) -> MoneyAuthorityDecision:
    return resolve_authoritative_money(
        source_domain="b23_match_verdicts",
        source_field_path="canonical_net_verified_amount_minor",
        raw_value=source.canonical_net_verified_amount_minor,
        currency=source.currency_code,
        intended_trust_field="verified_revenue_minor",
    )


def _read_only_observation(*, llm_modules: tuple[str, ...]) -> ReadOnlyObservation:
    return ReadOnlyObservation(
        source_reads=1,
        source_writes=0,
        task_dispatches=0,
        artifact_writes=0,
        export_writes=0,
        audit_writes=0,
        llm_calls=0,
        runtime_llm_modules_loaded=llm_modules,
    )


def _loaded_llm_modules(before: set[str], after: set[str]) -> tuple[str, ...]:
    loaded = sorted(after - before)
    forbidden = tuple(
        name
        for name in loaded
        if (
            name.startswith("app.llm")
            or name.startswith("backend.app.llm")
            or name in {"openai", "anthropic"}
            or name.startswith("openai.")
            or name.startswith("anthropic.")
        )
    )
    return forbidden


async def build_unsigned_trust_envelope(
    db_session: AsyncSession,
    request: TrustEnvelopeBuildRequest,
) -> TrustEnvelopeBuildResult:
    """Build an unsigned, schema-valid TrustEnvelope payload from approved sources."""
    import sys

    before_modules = set(sys.modules)
    decisions = iter_field_source_decisions()
    validate_schema_canonicalization_compatibility(
        request.schema_version, request.canonicalization_version
    )
    created_at = _context_datetime(
        request.request_context,
        "created_at",
        datetime.now(timezone.utc),
    )
    audience_id = str(
        request.request_context.get("audience_id") or "b25-p5-internal-builder"
    )

    if request.subject_type not in SUPPORTED_P5_SUBJECT_TYPES:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="subject_authority_rejected",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="subject_authority_rejected",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
        )

    source = await read_match_verdict_source(
        db_session,
        tenant_id=request.tenant_id,
        subject_ref=request.subject_ref,
    )
    if source is None:
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="subject_authority_rejected",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="subject_authority_rejected",
            field_source_decisions=decisions,
            money_authority_decision=None,
            read_only_observation=_read_only_observation(llm_modules=()),
        )

    money_decision = _money_decision_for_match_verdict(source)
    if not isinstance(money_decision, AuthoritativeMoneyMinor):
        refusal = build_error_envelope(
            tenant_id=request.tenant_id,
            reason_code="money_source_not_authoritative",
            created_at=created_at,
            audience_id=audience_id,
        )
        return TrustEnvelopeBuildResult(
            status="refused",
            unsigned_payload=None,
            refusal_payload=refusal,
            reason_code="money_source_not_authoritative",
            field_source_decisions=decisions,
            money_authority_decision=money_decision,
            read_only_observation=_read_only_observation(llm_modules=()),
        )

    payload = _match_verdict_payload(
        request=request,
        source=source,
        money_decision=money_decision,
    )
    after_modules = set(sys.modules)
    llm_modules = _loaded_llm_modules(before_modules, after_modules)
    if llm_modules:
        raise TrustEnvelopeBuildError(
            f"p5_builder_loaded_forbidden_llm_modules:{','.join(llm_modules)}"
        )
    return TrustEnvelopeBuildResult(
        status="success",
        unsigned_payload=payload,
        refusal_payload=None,
        reason_code=None,
        field_source_decisions=decisions,
        money_authority_decision=money_decision,
        read_only_observation=_read_only_observation(llm_modules=llm_modules),
    )

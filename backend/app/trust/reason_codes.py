"""B2.5-P6 enum-backed refusal/degraded reason code registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


EnvelopeStatus = Literal["success", "degraded", "refused", "unavailable"]
FallbackApplied = Literal["required", "forbidden", "not_applicable"]


class ReasonCode(StrEnum):
    """Canonical B2.5-P6 machine reason codes."""

    SCOPE_DENIED = "scope_denied"
    TENANT_MISMATCH = "tenant_mismatch"
    REPLAY_REJECTED = "replay_rejected"
    SUBJECT_NOT_FOUND = "subject_not_found"
    DETERMINISTIC_EVIDENCE_UNAVAILABLE = "deterministic_evidence_unavailable"
    CONFIDENCE_UNAVAILABLE = "confidence_unavailable"
    DIAGNOSTICS_FAILED = "diagnostics_failed"
    ARTIFACT_PRUNED = "artifact_pruned"
    SOURCE_SNAPSHOT_STALE = "source_snapshot_stale"
    BENCHMARK_UNAVAILABLE = "benchmark_unavailable"
    POLICY_DENIED = "policy_denied"
    POLICY_ENGINE_NOT_AVAILABLE = "policy_engine_not_available"
    MONEY_SOURCE_NOT_AUTHORITATIVE = "money_source_not_authoritative"
    PROVIDER_TEXT_QUARANTINED = "provider_text_quarantined"
    SCHEMA_VERSION_UNSUPPORTED = "schema_version_unsupported"
    CANONICALIZATION_VERSION_UNSUPPORTED = "canonicalization_version_unsupported"
    SIGNATURE_ALGORITHM_UNSUPPORTED = "signature_algorithm_unsupported"
    RATE_LIMITED = "rate_limited"

    # Compatibility codes already present in P1/P5 contracts or examples.
    SCHEMA_DOWNGRADE_REJECTED = "schema_downgrade_rejected"
    CANONICAL_TIMESTAMP_REJECTED = "canonical_timestamp_rejected"
    HUMAN_WORKFLOW_STATE_REJECTED = "human_workflow_state_rejected"
    SUBJECT_AUTHORITY_REJECTED = "subject_authority_rejected"
    MUTABLE_WORKFLOW_SUBJECT_REJECTED = "mutable_workflow_subject_rejected"
    MONEY_AMOUNT_EXCEEDS_JSON_SAFE_INTEGER = "money_amount_exceeds_json_safe_integer"
    VALIDATION_FAILED = "validation_failed"


REQUIRED_P6_REASON_CODES: frozenset[str] = frozenset(
    {
        ReasonCode.SCOPE_DENIED,
        ReasonCode.TENANT_MISMATCH,
        ReasonCode.REPLAY_REJECTED,
        ReasonCode.SUBJECT_NOT_FOUND,
        ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE,
        ReasonCode.CONFIDENCE_UNAVAILABLE,
        ReasonCode.DIAGNOSTICS_FAILED,
        ReasonCode.ARTIFACT_PRUNED,
        ReasonCode.SOURCE_SNAPSHOT_STALE,
        ReasonCode.BENCHMARK_UNAVAILABLE,
        ReasonCode.POLICY_DENIED,
        ReasonCode.POLICY_ENGINE_NOT_AVAILABLE,
        ReasonCode.MONEY_SOURCE_NOT_AUTHORITATIVE,
        ReasonCode.PROVIDER_TEXT_QUARANTINED,
        ReasonCode.SCHEMA_VERSION_UNSUPPORTED,
        ReasonCode.CANONICALIZATION_VERSION_UNSUPPORTED,
        ReasonCode.SIGNATURE_ALGORITHM_UNSUPPORTED,
        ReasonCode.RATE_LIMITED,
    }
)


FALLBACK_REASON_CODES: frozenset[str] = frozenset(
    {
        "none",
        ReasonCode.CONFIDENCE_UNAVAILABLE,
        ReasonCode.DIAGNOSTICS_FAILED,
        ReasonCode.SOURCE_SNAPSHOT_STALE,
        ReasonCode.ARTIFACT_PRUNED,
        ReasonCode.BENCHMARK_UNAVAILABLE,
        ReasonCode.MONEY_SOURCE_NOT_AUTHORITATIVE,
        ReasonCode.MONEY_AMOUNT_EXCEEDS_JSON_SAFE_INTEGER,
        ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE,
        ReasonCode.PROVIDER_TEXT_QUARANTINED,
        ReasonCode.POLICY_DENIED,
        ReasonCode.POLICY_ENGINE_NOT_AVAILABLE,
    }
)


class ReasonCodeRegistryError(ValueError):
    """Raised when reason-code authority is missing or inconsistent."""


@dataclass(frozen=True)
class ReasonCodeDefinition:
    """One deterministic reason-code matrix row."""

    code: ReasonCode
    source_predicate: str
    envelope_status: EnvelopeStatus
    allowed_fields: frozenset[str]
    forbidden_fields: frozenset[str]
    policy_action_authority_behavior: str
    confidence_metadata_behavior: str
    benchmark_metadata_behavior: str
    signature_behavior: str
    audit_behavior: str
    fallback_applied: FallbackApplied
    fallback_reason: ReasonCode | Literal["none"] | None
    canonicalization_behavior: str
    future_phase_owner: str | None = None

    def external_projection(self) -> dict[str, object]:
        """Return a stable, inspectable registry projection."""
        return {
            "code": self.code.value,
            "source_predicate": self.source_predicate,
            "envelope_status": self.envelope_status,
            "allowed_fields": sorted(self.allowed_fields),
            "forbidden_fields": sorted(self.forbidden_fields),
            "policy_action_authority_behavior": self.policy_action_authority_behavior,
            "confidence_metadata_behavior": self.confidence_metadata_behavior,
            "benchmark_metadata_behavior": self.benchmark_metadata_behavior,
            "signature_behavior": self.signature_behavior,
            "audit_behavior": self.audit_behavior,
            "fallback_applied": self.fallback_applied,
            "fallback_reason": (
                self.fallback_reason.value
                if isinstance(self.fallback_reason, ReasonCode)
                else self.fallback_reason
            ),
            "canonicalization_behavior": self.canonicalization_behavior,
            "future_phase_owner": self.future_phase_owner,
        }


COMMON_ALLOWED_FIELDS = frozenset(
    {
        "envelope_version",
        "schema_version",
        "canonicalization_version",
        "envelope_id",
        "tenant_id_hash",
        "audience_binding",
        "subject_authority",
        "subject_type",
        "subject_ref",
        "subject_ref_hash",
        "truth_type",
        "truth_authority",
        "confidence_metadata",
        "provenance_chain",
        "data_completeness_status",
        "benchmark_metadata",
        "policy_action_authority",
        "fallback_applied",
        "fallback_reason",
        "evidence_temporal_boundary",
        "audit_ref",
        "audit_hash",
        "semantic_truth_hash",
        "artifact_ref",
        "artifact_hash",
        "signature_hash",
        "signature",
        "signing_algorithm",
        "signing_key_id",
        "created_at",
        "valid_until",
        "untrusted_display_data",
    }
)
MONEY_FIELDS = frozenset({"verified_revenue_minor", "currency"})
ACTION_LIKE_POLICY_STATES = frozenset(
    {"simulation_only", "proposal_required", "approval_required"}
)


def _definition(
    code: ReasonCode,
    *,
    source_predicate: str,
    envelope_status: EnvelopeStatus,
    allowed_fields: frozenset[str] = COMMON_ALLOWED_FIELDS,
    forbidden_fields: frozenset[str] = frozenset(),
    policy: str = "preserve_conservative_read_only_or_blocked",
    confidence: str = "preserve_or_explicit_unavailable",
    benchmark: str = "preserve_or_explicit_unavailable",
    signature: str = "not_signed_in_p6_deferred_to_p8",
    audit: str = "not_persisted_in_p6_deferred_to_p7",
    fallback_applied: FallbackApplied = "not_applicable",
    fallback_reason: ReasonCode | Literal["none"] | None = None,
    canonicalization: str = "canonicalizable_after_matrix_validation",
    future_phase_owner: str | None = None,
) -> ReasonCodeDefinition:
    return ReasonCodeDefinition(
        code=code,
        source_predicate=source_predicate,
        envelope_status=envelope_status,
        allowed_fields=allowed_fields,
        forbidden_fields=forbidden_fields,
        policy_action_authority_behavior=policy,
        confidence_metadata_behavior=confidence,
        benchmark_metadata_behavior=benchmark,
        signature_behavior=signature,
        audit_behavior=audit,
        fallback_applied=fallback_applied,
        fallback_reason=fallback_reason,
        canonicalization_behavior=canonicalization,
        future_phase_owner=future_phase_owner,
    )


REASON_CODE_REGISTRY: dict[ReasonCode, ReasonCodeDefinition] = {
    ReasonCode.SCOPE_DENIED: _definition(
        ReasonCode.SCOPE_DENIED,
        source_predicate="caller_scope_missing_or_forbidden",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
        future_phase_owner="B2.5-P9",
    ),
    ReasonCode.TENANT_MISMATCH: _definition(
        ReasonCode.TENANT_MISMATCH,
        source_predicate="caller_tenant_does_not_match_subject_tenant",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
        future_phase_owner="B2.5-P9",
    ),
    ReasonCode.REPLAY_REJECTED: _definition(
        ReasonCode.REPLAY_REJECTED,
        source_predicate="replay_nonce_or_idempotency_context_rejected",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
        future_phase_owner="B2.5-P9",
    ),
    ReasonCode.SUBJECT_NOT_FOUND: _definition(
        ReasonCode.SUBJECT_NOT_FOUND,
        source_predicate="subject_lookup_returns_no_authorized_row",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
    ),
    ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE: _definition(
        ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE,
        source_predicate="required_deterministic_source_missing_or_incomplete",
        envelope_status="unavailable",
        forbidden_fields=MONEY_FIELDS,
        confidence="force_explicit_unavailable_no_numeric_confidence",
        fallback_applied="required",
        fallback_reason=ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE,
    ),
    ReasonCode.CONFIDENCE_UNAVAILABLE: _definition(
        ReasonCode.CONFIDENCE_UNAVAILABLE,
        source_predicate="b24_confidence_projection_missing_or_not_applicable",
        envelope_status="degraded",
        confidence="force_explicit_unavailable_no_score_no_interval",
        fallback_applied="required",
        fallback_reason=ReasonCode.CONFIDENCE_UNAVAILABLE,
    ),
    ReasonCode.DIAGNOSTICS_FAILED: _definition(
        ReasonCode.DIAGNOSTICS_FAILED,
        source_predicate="b24_diagnostics_status_failed",
        envelope_status="degraded",
        confidence="force_diagnostics_failed_no_available_intervals",
        fallback_applied="required",
        fallback_reason=ReasonCode.DIAGNOSTICS_FAILED,
    ),
    ReasonCode.ARTIFACT_PRUNED: _definition(
        ReasonCode.ARTIFACT_PRUNED,
        source_predicate="artifact_ref_pruned_or_hash_unavailable",
        envelope_status="degraded",
        confidence="degrade_auditably_no_artifact_backed_interval",
        fallback_applied="required",
        fallback_reason=ReasonCode.ARTIFACT_PRUNED,
    ),
    ReasonCode.SOURCE_SNAPSHOT_STALE: _definition(
        ReasonCode.SOURCE_SNAPSHOT_STALE,
        source_predicate="source_snapshot_hash_or_temporal_boundary_stale",
        envelope_status="degraded",
        confidence="force_unavailable_or_degraded_due_to_stale_snapshot",
        fallback_applied="required",
        fallback_reason=ReasonCode.SOURCE_SNAPSHOT_STALE,
    ),
    ReasonCode.BENCHMARK_UNAVAILABLE: _definition(
        ReasonCode.BENCHMARK_UNAVAILABLE,
        source_predicate="benchmark_authority_not_configured_or_privacy_suppressed",
        envelope_status="degraded",
        benchmark="force_explicit_unavailable_no_values",
        fallback_applied="required",
        fallback_reason=ReasonCode.BENCHMARK_UNAVAILABLE,
    ),
    ReasonCode.POLICY_DENIED: _definition(
        ReasonCode.POLICY_DENIED,
        source_predicate="policy_authority_denies_requested_action_or_scope",
        envelope_status="refused",
        policy="force_blocked_or_read_only_no_action_like_state",
        fallback_applied="required",
        fallback_reason=ReasonCode.POLICY_DENIED,
        future_phase_owner="B2.5-P9",
    ),
    ReasonCode.POLICY_ENGINE_NOT_AVAILABLE: _definition(
        ReasonCode.POLICY_ENGINE_NOT_AVAILABLE,
        source_predicate="policy_engine_not_implemented_for_phase",
        envelope_status="degraded",
        policy="force_read_only_policy_engine_not_available",
        fallback_applied="required",
        fallback_reason=ReasonCode.POLICY_ENGINE_NOT_AVAILABLE,
    ),
    ReasonCode.MONEY_SOURCE_NOT_AUTHORITATIVE: _definition(
        ReasonCode.MONEY_SOURCE_NOT_AUTHORITATIVE,
        source_predicate="p4_money_authority_refused_or_degraded_source",
        envelope_status="refused",
        forbidden_fields=MONEY_FIELDS,
        fallback_applied="required",
        fallback_reason=ReasonCode.MONEY_SOURCE_NOT_AUTHORITATIVE,
    ),
    ReasonCode.PROVIDER_TEXT_QUARANTINED: _definition(
        ReasonCode.PROVIDER_TEXT_QUARANTINED,
        source_predicate="p3_text_disposition_quarantined_or_redacted_provider_text",
        envelope_status="degraded",
        fallback_applied="required",
        fallback_reason=ReasonCode.PROVIDER_TEXT_QUARANTINED,
    ),
    ReasonCode.SCHEMA_VERSION_UNSUPPORTED: _definition(
        ReasonCode.SCHEMA_VERSION_UNSUPPORTED,
        source_predicate="schema_version_registry_rejects_payload_version",
        envelope_status="refused",
        canonicalization="fail_closed_before_success_canonicalization",
    ),
    ReasonCode.CANONICALIZATION_VERSION_UNSUPPORTED: _definition(
        ReasonCode.CANONICALIZATION_VERSION_UNSUPPORTED,
        source_predicate="canonicalization_registry_rejects_payload_version",
        envelope_status="refused",
        canonicalization="fail_closed_before_success_canonicalization",
    ),
    ReasonCode.SIGNATURE_ALGORITHM_UNSUPPORTED: _definition(
        ReasonCode.SIGNATURE_ALGORITHM_UNSUPPORTED,
        source_predicate="signature_algorithm_not_in_supported_external_set",
        envelope_status="refused",
        signature="unsupported_algorithm_not_verified_deferred_to_p8",
        future_phase_owner="B2.5-P8",
    ),
    ReasonCode.RATE_LIMITED: _definition(
        ReasonCode.RATE_LIMITED,
        source_predicate="rate_limit_policy_rejects_request",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
        future_phase_owner="B2.5-P9",
    ),
    ReasonCode.SCHEMA_DOWNGRADE_REJECTED: _definition(
        ReasonCode.SCHEMA_DOWNGRADE_REJECTED,
        source_predicate="schema_version_is_deprecated_or_downgraded",
        envelope_status="refused",
        canonicalization="fail_closed_before_success_canonicalization",
    ),
    ReasonCode.CANONICAL_TIMESTAMP_REJECTED: _definition(
        ReasonCode.CANONICAL_TIMESTAMP_REJECTED,
        source_predicate="timestamp_not_utc_second_canonical_form",
        envelope_status="refused",
        canonicalization="fail_closed_before_success_canonicalization",
    ),
    ReasonCode.HUMAN_WORKFLOW_STATE_REJECTED: _definition(
        ReasonCode.HUMAN_WORKFLOW_STATE_REJECTED,
        source_predicate="mutable_human_workflow_state_attempted_as_subject_truth",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
    ),
    ReasonCode.SUBJECT_AUTHORITY_REJECTED: _definition(
        ReasonCode.SUBJECT_AUTHORITY_REJECTED,
        source_predicate="subject_type_or_subject_authority_not_supported_by_p5",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
    ),
    ReasonCode.MUTABLE_WORKFLOW_SUBJECT_REJECTED: _definition(
        ReasonCode.MUTABLE_WORKFLOW_SUBJECT_REJECTED,
        source_predicate="subject_authority_marks_mutable_workflow_subject",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
    ),
    ReasonCode.MONEY_AMOUNT_EXCEEDS_JSON_SAFE_INTEGER: _definition(
        ReasonCode.MONEY_AMOUNT_EXCEEDS_JSON_SAFE_INTEGER,
        source_predicate="authoritative_money_exceeds_json_safe_integer_bound",
        envelope_status="refused",
        forbidden_fields=MONEY_FIELDS,
        fallback_applied="required",
        fallback_reason=ReasonCode.MONEY_AMOUNT_EXCEEDS_JSON_SAFE_INTEGER,
    ),
    ReasonCode.VALIDATION_FAILED: _definition(
        ReasonCode.VALIDATION_FAILED,
        source_predicate="contract_or_matrix_validation_failed_closed",
        envelope_status="refused",
        policy="force_blocked_no_action_scopes",
    ),
}


def coerce_reason_code(value: str | ReasonCode) -> ReasonCode:
    """Return a ReasonCode or fail closed for free-form strings."""
    if isinstance(value, ReasonCode):
        return value
    try:
        return ReasonCode(str(value))
    except ValueError as exc:
        raise ReasonCodeRegistryError(f"reason_code_unknown:{value}") from exc


def get_reason_definition(value: str | ReasonCode) -> ReasonCodeDefinition:
    """Return one registered reason-code definition."""
    code = coerce_reason_code(value)
    try:
        return REASON_CODE_REGISTRY[code]
    except KeyError as exc:
        raise ReasonCodeRegistryError(f"reason_code_unregistered:{code.value}") from exc


def validate_reason_code_registry(
    registry: dict[ReasonCode, ReasonCodeDefinition] | None = None,
) -> int:
    """Validate registry completeness, uniqueness, and row semantics."""
    current = registry or REASON_CODE_REGISTRY
    missing_required = sorted(REQUIRED_P6_REASON_CODES - {code.value for code in current})
    if missing_required:
        raise ReasonCodeRegistryError(f"required_reason_codes_missing:{missing_required}")
    if len(current) != len(set(current)):
        raise ReasonCodeRegistryError("duplicate_reason_code_keys")
    for key, definition in current.items():
        if key != definition.code:
            raise ReasonCodeRegistryError(
                f"reason_code_key_definition_mismatch:{key}:{definition.code}"
            )
        _validate_definition(definition)
    return len(current)


def _validate_definition(definition: ReasonCodeDefinition) -> None:
    if not definition.source_predicate:
        raise ReasonCodeRegistryError(f"reason_code_missing_source_predicate:{definition.code}")
    if definition.envelope_status not in {"success", "degraded", "refused", "unavailable"}:
        raise ReasonCodeRegistryError(f"reason_code_bad_status:{definition.code}")
    if not definition.allowed_fields:
        raise ReasonCodeRegistryError(f"reason_code_missing_allowed_fields:{definition.code}")
    if not definition.policy_action_authority_behavior:
        raise ReasonCodeRegistryError(f"reason_code_missing_policy_behavior:{definition.code}")
    if not definition.confidence_metadata_behavior:
        raise ReasonCodeRegistryError(f"reason_code_missing_confidence_behavior:{definition.code}")
    if not definition.benchmark_metadata_behavior:
        raise ReasonCodeRegistryError(f"reason_code_missing_benchmark_behavior:{definition.code}")
    if not definition.signature_behavior:
        raise ReasonCodeRegistryError(f"reason_code_missing_signature_behavior:{definition.code}")
    if not definition.audit_behavior:
        raise ReasonCodeRegistryError(f"reason_code_missing_audit_behavior:{definition.code}")
    if definition.fallback_applied not in {"required", "forbidden", "not_applicable"}:
        raise ReasonCodeRegistryError(f"reason_code_bad_fallback_rule:{definition.code}")
    fallback = definition.fallback_reason
    if isinstance(fallback, ReasonCode) and fallback.value not in FALLBACK_REASON_CODES:
        raise ReasonCodeRegistryError(f"reason_code_bad_fallback_reason:{definition.code}")
    if isinstance(fallback, str) and fallback not in FALLBACK_REASON_CODES:
        raise ReasonCodeRegistryError(f"reason_code_bad_fallback_reason:{definition.code}")
    if not definition.canonicalization_behavior:
        raise ReasonCodeRegistryError(f"reason_code_missing_canonicalization:{definition.code}")


validate_reason_code_registry()

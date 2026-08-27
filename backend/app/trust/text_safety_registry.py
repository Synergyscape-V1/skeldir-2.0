"""Deterministic B2.5-P3 text trust registry.

The registry is deliberately explicit. Unknown TrustEnvelope string paths,
unknown trust classes, unknown risk classes, and missing matrix cells are
errors, not safe defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


TEXT_DISPOSITION_VERSION = "text-disposition-v1"

MACHINE_AUTHORITY_ENUM = "machine_authority_enum"
MACHINE_AUTHORITY_CODE = "machine_authority_code"
SAFE_SYSTEM_ENUM = "safe_system_enum"
OPAQUE_REFERENCE = "opaque_reference"
UNTRUSTED_DISPLAY_LABEL = "untrusted_display_label"
QUARANTINED_TEXT_HASH = "quarantined_text_hash"
REDACTED_TEXT = "redacted_text"

TEXT_TRUST_CLASSES: tuple[str, ...] = (
    MACHINE_AUTHORITY_ENUM,
    MACHINE_AUTHORITY_CODE,
    SAFE_SYSTEM_ENUM,
    OPAQUE_REFERENCE,
    UNTRUSTED_DISPLAY_LABEL,
    QUARANTINED_TEXT_HASH,
    REDACTED_TEXT,
)


class TextSafetyRegistryError(ValueError):
    """Raised when P3 registry coverage or matrix totality is invalid."""


SAFE_PRINTABLE = "safe_printable"
OVERLONG = "overlong"
CONTROL_CHARACTERS = "control_characters"
NULL_BYTE = "null_byte"
BIDI_CONTROL_CHARACTERS = "bidi_control_characters"
MARKUP_OR_SCRIPT = "markup_or_script"
KNOWN_MACHINE_INSTRUCTION_INDICATORS = "known_machine_instruction_indicators"
JSON_XML_MARKDOWN_DELIMITER_BREAKOUT = "json_xml_markdown_delimiter_breakout"
TOOL_CALL_SYNTAX = "tool_call_syntax"
UNKNOWN_BINARY_OR_INVALID_ENCODING = "unknown_binary_or_invalid_encoding"

CONTENT_RISK_CLASSES: tuple[str, ...] = (
    SAFE_PRINTABLE,
    OVERLONG,
    CONTROL_CHARACTERS,
    NULL_BYTE,
    BIDI_CONTROL_CHARACTERS,
    MARKUP_OR_SCRIPT,
    KNOWN_MACHINE_INSTRUCTION_INDICATORS,
    JSON_XML_MARKDOWN_DELIMITER_BREAKOUT,
    TOOL_CALL_SYNTAX,
    UNKNOWN_BINARY_OR_INVALID_ENCODING,
)

REJECT_OR_REFUSE = "reject_or_refuse"
PRESERVE_AS_SAFE_SYSTEM_VALUE = "preserve_as_safe_system_value"
EMIT_UNTRUSTED_DISPLAY_LABEL = "emit_untrusted_display_label"
REPLACE_WITH_KEYED_OPAQUE_REFERENCE = "replace_with_keyed_opaque_reference"
OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA = (
    "omit_raw_text_and_emit_quarantine_metadata"
)
REDACT_WITH_REASON = "redact_with_reason"

DISPOSITION_ACTIONS: tuple[str, ...] = (
    REJECT_OR_REFUSE,
    PRESERVE_AS_SAFE_SYSTEM_VALUE,
    EMIT_UNTRUSTED_DISPLAY_LABEL,
    REPLACE_WITH_KEYED_OPAQUE_REFERENCE,
    OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA,
    REDACT_WITH_REASON,
)

MACHINE_AUTHORITY_CLASSES = frozenset(
    {MACHINE_AUTHORITY_ENUM, MACHINE_AUTHORITY_CODE, SAFE_SYSTEM_ENUM}
)

_SAFE_SYSTEM_ENUM_FIELDS = frozenset(
    {
        "canonicalization_version",
        "envelope_version",
        "schema_version",
        "semantic_unicode_probe",
        "signing_algorithm",
        "untrusted_display_data.text_disposition_version",
    }
)

_MACHINE_AUTHORITY_ENUM_FIELDS = frozenset(
    {
        "attribution_model",
        "audience_binding.audience_mode",
        "audience_binding.audience_scope[]",
        "audience_binding.presentation_policy",
        "benchmark_metadata.benchmark_authority",
        "benchmark_metadata.benchmark_status",
        "benchmark_metadata.unavailable_reason",
        "causal_status",
        "confidence_metadata.bayesian_model_type",
        "confidence_metadata.confidence_authority",
        "confidence_metadata.confidence_status",
        "confidence_metadata.diagnostics_status",
        "confidence_metadata.unavailable_reason",
        "currency",
        "data_completeness_status",
        "deterministic_verification_status",
        "discrepancy_class",
        "evidence_temporal_boundary.data_freshness_bound",
        "evidence_temporal_boundary.evidence_age_status",
        "evidence_temporal_boundary.snapshot_consistency_status",
        "evidence_temporal_boundary.staleness_status",
        "fallback_reason",
        "match_verdict_status",
        "model_assumption",
        "policy_action_authority.allowed_scopes[]",
        "policy_action_authority.forbidden_scopes[]",
        "policy_action_authority.policy_state",
        "provenance_chain[].authority_table",
        "provenance_chain[].display_metadata.display_transform",
        "provenance_chain[].display_metadata.text_trust_class",
        "provenance_chain[].provenance_type",
        "subject_authority.allowed_source_tables[]",
        "subject_authority.source_authority_class",
        "subject_authority.subject_type",
        "subject_type",
        "truth_authority.authority_class",
        "truth_authority.source_system",
        "truth_type",
        "untrusted_display_data.content_safety_flags[]",
        "untrusted_display_data.display_transform",
        "untrusted_display_data.disposition_action",
        "untrusted_display_data.opaque_reference_metadata.hash_algorithm",
        "untrusted_display_data.opaque_reference_metadata.hash_domain",
        "untrusted_display_data.opaque_reference_metadata.key_scope",
        "untrusted_display_data.opaque_reference_metadata.key_version",
        "untrusted_display_data.opaque_reference_metadata.provider",
        "untrusted_display_data.opaque_reference_metadata.source_field_path",
        "untrusted_display_data.redaction_reason",
        "untrusted_display_data.text_trust_class",
    }
)

_MACHINE_AUTHORITY_CODE_FIELDS = frozenset(
    {
        "audience_binding.audience_id_hash",
        "audit_hash",
        "benchmark_metadata.benchmark_hash",
        "confidence_metadata.bayesian_model_version",
        "confidence_metadata.inference_provenance.diagnostic_policy_version",
        "confidence_metadata.inference_provenance.confidence_policy_version",
        "confidence_metadata.inference_provenance.confidence_semantics_version",
        "confidence_metadata.inference_provenance.inference_profile_version",
        "confidence_metadata.inference_provenance.policy_bundle_hash",
        "confidence_metadata.inference_provenance.runtime_policy_version",
        "confidence_metadata.inference_provenance.sampling_policy_version",
        "created_at",
        "envelope_id",
        "evidence_temporal_boundary.evidence_snapshot_at",
        "evidence_temporal_boundary.evidence_snapshot_hash",
        "evidence_temporal_boundary.source_read_completed_at",
        "evidence_temporal_boundary.source_read_started_at",
        "policy_action_authority.reason_code",
        "provenance_chain[].display_metadata.raw_text_sha256",
        "provenance_chain[].observed_at",
        "provenance_chain[].source_ref_hash",
        "provenance_chain[].source_snapshot_hash",
        "semantic_truth_hash",
        "signature",
        "signature_hash",
        "signing_key_id",
        "subject_authority.subject_ref_hash",
        "subject_ref_hash",
        "tenant_id_hash",
        "truth_authority.source_snapshot_hash",
        "untrusted_display_data.opaque_reference_hash",
        "untrusted_display_data.raw_text_hmac",
        "untrusted_display_data.raw_text_sha256",
        "valid_until",
    }
)

_OPAQUE_REFERENCE_FIELDS = frozenset(
    {
        "artifact_ref",
        "audit_ref",
        "benchmark_metadata.benchmark_ref",
        "provenance_chain[].source_ref",
        "subject_authority.subject_ref",
        "subject_ref",
    }
)

_UNTRUSTED_DISPLAY_FIELDS = frozenset(
    {
        "untrusted_display_data.display_text",
        "untrusted_display_data.normalized_display_text",
    }
)

_QUARANTINED_HASH_FIELDS = frozenset(
    {
        "artifact_hash",
    }
)

_REDACTED_TEXT_FIELDS: frozenset[str] = frozenset()


def _field_registry() -> dict[str, str]:
    groups = {
        SAFE_SYSTEM_ENUM: _SAFE_SYSTEM_ENUM_FIELDS,
        MACHINE_AUTHORITY_ENUM: _MACHINE_AUTHORITY_ENUM_FIELDS,
        MACHINE_AUTHORITY_CODE: _MACHINE_AUTHORITY_CODE_FIELDS,
        OPAQUE_REFERENCE: _OPAQUE_REFERENCE_FIELDS,
        UNTRUSTED_DISPLAY_LABEL: _UNTRUSTED_DISPLAY_FIELDS,
        QUARANTINED_TEXT_HASH: _QUARANTINED_HASH_FIELDS,
        REDACTED_TEXT: _REDACTED_TEXT_FIELDS,
    }
    registry: dict[str, str] = {}
    duplicates: set[str] = set()
    for trust_class, field_paths in groups.items():
        for field_path in field_paths:
            if field_path in registry:
                duplicates.add(field_path)
            registry[field_path] = trust_class
    if duplicates:
        raise TextSafetyRegistryError(
            f"text_trust_duplicate_paths:{sorted(duplicates)}"
        )
    return registry


FIELD_TEXT_TRUST_CLASSES: Mapping[str, str] = _field_registry()


def _matrix() -> dict[tuple[str, str], str]:
    matrix: dict[tuple[str, str], str] = {}
    for trust_class in TEXT_TRUST_CLASSES:
        for risk_class in CONTENT_RISK_CLASSES:
            if trust_class in MACHINE_AUTHORITY_CLASSES:
                action = REJECT_OR_REFUSE
            elif trust_class == OPAQUE_REFERENCE:
                action = REPLACE_WITH_KEYED_OPAQUE_REFERENCE
            elif trust_class == UNTRUSTED_DISPLAY_LABEL:
                action = (
                    EMIT_UNTRUSTED_DISPLAY_LABEL
                    if risk_class == SAFE_PRINTABLE
                    else OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA
                )
            elif trust_class == QUARANTINED_TEXT_HASH:
                action = OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA
            elif trust_class == REDACTED_TEXT:
                action = REDACT_WITH_REASON
            else:
                raise TextSafetyRegistryError(
                    f"text_trust_class_unhandled:{trust_class}"
                )
            matrix[(trust_class, risk_class)] = action
    return matrix


DISPOSITION_MATRIX: Mapping[tuple[str, str], str] = _matrix()


@dataclass(frozen=True)
class RegistryValidationResult:
    field_paths_checked: int
    text_trust_classes_checked: int
    content_risk_classes_checked: int
    disposition_matrix_cells_checked: int


def classify_field_path(field_path: str) -> str:
    """Return the declared text trust class for a TrustEnvelope string path."""
    try:
        return FIELD_TEXT_TRUST_CLASSES[field_path]
    except KeyError as exc:
        raise TextSafetyRegistryError(f"text_trust_unclassified:{field_path}") from exc


def disposition_action_for(trust_class: str, risk_class: str) -> str:
    """Return the single disposition action for a trust/risk pair."""
    if trust_class not in TEXT_TRUST_CLASSES:
        raise TextSafetyRegistryError(f"text_trust_unknown:{trust_class}")
    if risk_class not in CONTENT_RISK_CLASSES:
        raise TextSafetyRegistryError(f"content_risk_unknown:{risk_class}")
    try:
        return DISPOSITION_MATRIX[(trust_class, risk_class)]
    except KeyError as exc:
        raise TextSafetyRegistryError(
            f"disposition_matrix_missing:{trust_class}:{risk_class}"
        ) from exc


def validate_registry_totality(
    schema_string_field_paths: set[str],
) -> RegistryValidationResult:
    """Validate exact schema-to-registry coverage and full matrix totality."""
    registry_paths = set(FIELD_TEXT_TRUST_CLASSES)
    missing = sorted(schema_string_field_paths - registry_paths)
    extra = sorted(registry_paths - schema_string_field_paths)
    if missing:
        raise TextSafetyRegistryError(f"text_trust_missing_paths:{missing}")
    if extra:
        raise TextSafetyRegistryError(f"text_trust_unknown_paths:{extra}")

    matrix_keys = set(DISPOSITION_MATRIX)
    expected_keys = {
        (trust_class, risk_class)
        for trust_class in TEXT_TRUST_CLASSES
        for risk_class in CONTENT_RISK_CLASSES
    }
    missing_cells = sorted(expected_keys - matrix_keys)
    extra_cells = sorted(matrix_keys - expected_keys)
    if missing_cells:
        raise TextSafetyRegistryError(
            f"disposition_matrix_missing_cells:{missing_cells}"
        )
    if extra_cells:
        raise TextSafetyRegistryError(f"disposition_matrix_unknown_cells:{extra_cells}")
    for key, action in DISPOSITION_MATRIX.items():
        if action not in DISPOSITION_ACTIONS:
            raise TextSafetyRegistryError(f"disposition_action_unknown:{key}:{action}")

    return RegistryValidationResult(
        field_paths_checked=len(schema_string_field_paths),
        text_trust_classes_checked=len(TEXT_TRUST_CLASSES),
        content_risk_classes_checked=len(CONTENT_RISK_CLASSES),
        disposition_matrix_cells_checked=len(expected_keys),
    )

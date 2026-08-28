"""Complete semantic issuance authority for B2.5 TrustEnvelope signing.

The public signature is business authority, not merely byte integrity.  This
module keeps the exact P5 observation immutable through the only permitted P7
audit transform and exposes a capability that the private-key boundary can
distinguish from caller-authored JSON.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from app.inference_policy_registry import (
    PolicyRegistryError,
    validate_envelope_policy_authority,
)
from app.trust.audit_hash import audit_ref_from_identity, request_identity_hash
from app.trust.canonicalization import (
    canonicalize_envelope_payload,
    encode_envelope_structure_snapshot,
)
from app.trust.hash_identity import compute_semantic_truth_hash, compute_signature_hash
from app.trust.money_source_adapter import AuthoritativeMoneyMinor
from app.trust.provenance import replace_audit_provenance_entries
from app.trust.refusal import tagged_sha256
from app.trust.subject_authority import subject_authority_definition


AUTHORITY_MANIFEST_VERSION = "b25-p13-c14-semantic-authority-v1"

# Every property in trust-envelope.v2.yaml is classified here, including the
# fixture-only Unicode probe and subject families that are not currently issued.
# CI compares this inventory with the schema, so a newly signed field is denied
# until its authority is deliberately declared.
TRUST_ENVELOPE_AUTHORITY_FIELDS = frozenset(
    {
        "artifact_hash",
        "artifact_ref",
        "attribution_model",
        "audience_binding",
        "audit_hash",
        "audit_ref",
        "benchmark_metadata",
        "canonicalization_version",
        "causal_status",
        "confidence_metadata",
        "created_at",
        "currency",
        "data_completeness_status",
        "deterministic_verification_status",
        "discrepancy_class",
        "envelope_id",
        "envelope_version",
        "evidence_temporal_boundary",
        "fallback_applied",
        "fallback_reason",
        "match_verdict_status",
        "model_assumption",
        "policy_action_authority",
        "provenance_chain",
        "schema_version",
        "semantic_truth_hash",
        "semantic_unicode_probe",
        "signature",
        "signature_hash",
        "signing_algorithm",
        "signing_key_id",
        "subject_authority",
        "subject_ref",
        "subject_ref_hash",
        "subject_type",
        "tenant_id_hash",
        "truth_authority",
        "truth_type",
        "untrusted_display_data",
        "valid_until",
        "verified_revenue_minor",
    }
)

_CAPABILITY_SEAL = object()


class TrustSemanticAuthorityError(ValueError):
    """Raised before crypto when a Trust claim lacks semantic authority."""


@dataclass(frozen=True, slots=True)
class AuthorizedTrustEnvelope:
    """Immutable, content-addressed capability required by the private signer."""

    _payload_snapshot: bytes = field(repr=False)
    authority_proof_hash: str
    authority_manifest_version: str
    _seal: object = field(repr=False, compare=False)

    def _validated_payload_copy(self) -> dict[str, Any]:
        if self._seal is not _CAPABILITY_SEAL:
            raise TrustSemanticAuthorityError("issuance_capability_invalid")
        if self.authority_manifest_version != AUTHORITY_MANIFEST_VERSION:
            raise TrustSemanticAuthorityError("issuance_capability_manifest_mismatch")
        decoded = json.loads(self._payload_snapshot.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise TrustSemanticAuthorityError("issuance_capability_payload_invalid")
        expected = _authority_proof_hash(canonicalize_envelope_payload(decoded))
        if self.authority_proof_hash != expected:
            raise TrustSemanticAuthorityError("issuance_capability_content_mismatch")
        return decoded

    def external_payload_copy(self) -> dict[str, Any]:
        """Return an isolated projection; mutations cannot alter this capability."""

        return self._validated_payload_copy()


def _authority_proof_hash(canonical_payload: bytes) -> str:
    material = AUTHORITY_MANIFEST_VERSION.encode("utf-8") + b"\x00" + canonical_payload
    return "sha256:" + sha256(material).hexdigest()


def _expect_dict(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise TrustSemanticAuthorityError(f"semantic_object_required:{field_name}")
    return value


def _expect_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise TrustSemanticAuthorityError(f"semantic_string_required:{field_name}")
    return value


def _validate_identity_correspondence(
    payload: dict[str, Any],
    *,
    witness: Any,
) -> None:
    if payload.get("tenant_id_hash") != witness.tenant_id_hash:
        raise TrustSemanticAuthorityError("tenant_authority_mismatch")
    for field_name in ("subject_type", "subject_ref", "subject_ref_hash"):
        if payload.get(field_name) != getattr(witness, field_name):
            raise TrustSemanticAuthorityError(
                f"subject_authority_mismatch:{field_name}"
            )
    expected_ref_hash = tagged_sha256({"subject_ref": payload["subject_ref"]})
    if payload.get("subject_ref_hash") != expected_ref_hash:
        raise TrustSemanticAuthorityError("subject_ref_hash_mismatch")

    subject_authority = _expect_dict(payload, "subject_authority")
    definition = subject_authority_definition(_expect_string(payload, "subject_type"))
    expected_subject = {
        "subject_type": payload["subject_type"],
        "subject_ref": payload["subject_ref"],
        "subject_ref_hash": payload["subject_ref_hash"],
        "source_authority_class": definition.source_authority_class,
        "allowed_source_tables": list(definition.governed_source_tables),
        "mutable_workflow_subject": False,
    }
    if subject_authority != expected_subject:
        raise TrustSemanticAuthorityError("subject_authority_projection_mismatch")


def _validate_source_window_correspondence(
    payload: dict[str, Any],
    *,
    witness: Any,
) -> None:
    truth_authority = _expect_dict(payload, "truth_authority")
    temporal = _expect_dict(payload, "evidence_temporal_boundary")
    source_snapshot_hash = truth_authority.get("source_snapshot_hash")
    if source_snapshot_hash != witness.source_snapshot_hash:
        raise TrustSemanticAuthorityError("source_snapshot_authority_mismatch")
    if temporal.get("evidence_snapshot_hash") != source_snapshot_hash:
        raise TrustSemanticAuthorityError("evidence_window_snapshot_mismatch")


def _validate_confidence_state(payload: dict[str, Any]) -> None:
    metadata = _expect_dict(payload, "confidence_metadata")
    status = metadata.get("confidence_status")
    authority = metadata.get("confidence_authority")
    model_type = metadata.get("bayesian_model_type")
    model_version = metadata.get("bayesian_model_version")
    diagnostics = metadata.get("diagnostics_status")
    reason = metadata.get("unavailable_reason")
    provenance = metadata.get("inference_provenance")
    subject_type = payload.get("subject_type")

    if subject_type != "confidence_projection":
        expected = {
            "confidence_status": "unavailable",
            "confidence_authority": "deterministic_only",
            "confidence_score_basis_points": None,
            "bayesian_model_type": "deterministic_only",
            "bayesian_model_version": None,
            "diagnostics_status": "not_applicable",
            "unavailable_reason": "not_applicable",
            "inference_provenance": None,
        }
        if metadata != expected:
            raise TrustSemanticAuthorityError("deterministic_confidence_state_invalid")
        return

    if status == "available":
        valid = (
            authority == "b24_confidence_projection"
            and model_type == "pymc_marketing_mmm"
            and isinstance(model_version, str)
            and diagnostics == "passed"
            and reason is None
            and isinstance(provenance, dict)
            and payload.get("truth_type") == "confidence_projection_context"
            and payload.get("data_completeness_status") == "complete"
            and payload.get("fallback_applied") is False
            and payload.get("fallback_reason") == "none"
            and payload.get("artifact_ref") is not None
            and payload.get("artifact_hash") is not None
        )
    elif status == "diagnostics_failed":
        valid = (
            authority == "b24_confidence_projection"
            and model_type == "pymc_marketing_mmm"
            and isinstance(model_version, str)
            and diagnostics == "failed"
            and reason == "diagnostics_failed"
            and isinstance(provenance, dict)
            and payload.get("fallback_reason") == "diagnostics_failed"
        )
    elif status == "degraded" and authority == "b24_confidence_projection":
        valid = (
            model_type == "pymc_marketing_mmm"
            and isinstance(model_version, str)
            and diagnostics == "unavailable"
            and reason in {"artifact_pruned", "artifact_unavailable"}
            and isinstance(provenance, dict)
            and payload.get("fallback_reason") == reason
            and payload.get("artifact_ref") is None
            and payload.get("artifact_hash") is None
        )
    elif status in {"degraded", "unavailable"}:
        valid = (
            authority == "explicitly_unavailable"
            and model_type is None
            and model_version is None
            and diagnostics == "unavailable"
            and reason
            in {
                "cold_start_insufficient_data",
                "model_not_fit",
                "confidence_unavailable",
                "source_snapshot_stale",
                "unsupported_financial_context",
            }
            and payload.get("fallback_applied") is True
        )
    else:
        valid = False

    if not valid:
        raise TrustSemanticAuthorityError("confidence_semantic_state_invalid")
    if (
        payload.get("truth_type") != "degraded_or_unavailable_truth"
        and status != "available"
    ):
        raise TrustSemanticAuthorityError("confidence_truth_type_mismatch")
    if provenance is not None:
        try:
            validate_envelope_policy_authority(payload)
        except PolicyRegistryError as exc:
            raise TrustSemanticAuthorityError(
                f"confidence_policy_authority_invalid:{exc}"
            ) from exc


def validate_trust_semantic_authority(
    payload: dict[str, Any],
    *,
    build_result: Any,
) -> None:
    """Validate the complete claim against the authority witness before sealing."""

    unknown = set(payload) - TRUST_ENVELOPE_AUTHORITY_FIELDS
    if unknown:
        raise TrustSemanticAuthorityError(
            "undeclared_signed_semantics:" + ",".join(sorted(unknown))
        )
    witness = getattr(build_result, "authority_witness", None)
    provisional = getattr(build_result, "unsigned_payload", None)
    if witness is None or not isinstance(provisional, dict):
        raise TrustSemanticAuthorityError("builder_authority_witness_required")
    try:
        witness.assert_authoritative_payload(provisional)
    except Exception as exc:
        raise TrustSemanticAuthorityError(f"builder_authority_invalid:{exc}") from exc
    if not set(payload).issubset(set(witness.field_authority_names)):
        missing = set(payload) - set(witness.field_authority_names)
        raise TrustSemanticAuthorityError(
            "builder_field_authority_missing:" + ",".join(sorted(missing))
        )
    _validate_identity_correspondence(payload, witness=witness)
    _validate_source_window_correspondence(payload, witness=witness)
    _validate_confidence_state(payload)
    if payload.get("subject_type") == "match_verdict" and not isinstance(
        getattr(build_result, "money_authority_decision", None),
        AuthoritativeMoneyMinor,
    ):
        raise TrustSemanticAuthorityError("financial_authority_witness_required")
    try:
        validate_envelope_policy_authority(payload)
    except PolicyRegistryError as exc:
        raise TrustSemanticAuthorityError(f"policy_authority_invalid:{exc}") from exc


def _authorize_audited_trust_envelope(
    *,
    build_result: Any,
    audit_record: Any,
    audited_payload: dict[str, Any],
    observed_at: Any,
) -> AuthorizedTrustEnvelope:
    """Mint the sole production Trust signing capability after P5 + P7."""

    if getattr(build_result, "status", None) != "success":
        raise TrustSemanticAuthorityError("successful_builder_authority_required")
    if (
        getattr(audit_record, "event_type", None) != "issuance"
        or getattr(audit_record, "status", None) != "success"
    ):
        raise TrustSemanticAuthorityError("successful_audit_authority_required")
    provisional = getattr(build_result, "unsigned_payload", None)
    witness = getattr(build_result, "authority_witness", None)
    if not isinstance(provisional, dict) or witness is None:
        raise TrustSemanticAuthorityError("builder_authority_witness_required")
    try:
        witness.assert_authoritative_payload(provisional)
    except Exception as exc:
        raise TrustSemanticAuthorityError(f"builder_authority_invalid:{exc}") from exc

    expected = deepcopy(provisional)
    expected["audit_ref"] = audit_record.audit_ref
    expected["audit_hash"] = audit_record.audit_hash
    expected["provenance_chain"] = replace_audit_provenance_entries(
        list(expected["provenance_chain"]),
        audit_ref=audit_record.audit_ref,
        audit_hash=audit_record.audit_hash,
        observed_at=observed_at,
    )
    expected["semantic_truth_hash"] = "sha256:" + ("0" * 64)
    expected["signature_hash"] = "sha256:" + ("0" * 64)
    expected["semantic_truth_hash"] = compute_semantic_truth_hash(expected)
    expected["signature_hash"] = compute_signature_hash(expected)
    expected_bytes = canonicalize_envelope_payload(expected)
    actual_bytes = canonicalize_envelope_payload(audited_payload)
    if actual_bytes != expected_bytes:
        raise TrustSemanticAuthorityError("audited_payload_authority_mismatch")
    if audited_payload != expected:
        raise TrustSemanticAuthorityError("audited_payload_structure_mismatch")

    audience = _expect_dict(audited_payload, "audience_binding")
    audience_id_hash = audience.get("audience_id_hash")
    if not isinstance(audience_id_hash, str):
        raise TrustSemanticAuthorityError("audience_id_hash_required")
    expected_identity = request_identity_hash(
        tenant_id_hash=witness.tenant_id_hash,
        subject_type=witness.subject_type,
        subject_ref_hash=witness.subject_ref_hash,
        audience_id_hash=audience_id_hash,
    )
    if audit_record.request_identity_hash != expected_identity:
        raise TrustSemanticAuthorityError("audit_request_identity_mismatch")
    expected_audit_ref = audit_ref_from_identity(
        event_type="issuance",
        idempotency_key_hash=audit_record.idempotency_key_hash,
    )
    if audit_record.audit_ref != expected_audit_ref:
        raise TrustSemanticAuthorityError("audit_reference_identity_mismatch")

    validate_trust_semantic_authority(audited_payload, build_result=build_result)
    payload_snapshot = encode_envelope_structure_snapshot(audited_payload)
    return AuthorizedTrustEnvelope(
        _payload_snapshot=payload_snapshot,
        authority_proof_hash=_authority_proof_hash(actual_bytes),
        authority_manifest_version=AUTHORITY_MANIFEST_VERSION,
        _seal=_CAPABILITY_SEAL,
    )

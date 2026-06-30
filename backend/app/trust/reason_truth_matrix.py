"""Deterministic B2.5-P6 reason-code truth matrix validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.trust.reason_codes import (
    ACTION_LIKE_POLICY_STATES,
    MONEY_FIELDS,
    REQUIRED_P6_REASON_CODES,
    REASON_CODE_REGISTRY,
    ReasonCode,
    ReasonCodeDefinition,
    ReasonCodeRegistryError,
    coerce_reason_code,
    get_reason_definition,
    validate_reason_code_registry,
)


class ReasonTruthMatrixError(ValueError):
    """Raised when a reason-code decision contradicts source truth."""


@dataclass(frozen=True)
class ReasonTruthDecision:
    """Typed P6 decision returned by the truth matrix."""

    reason_code: ReasonCode
    envelope_status: str
    source_predicate: str
    allowed_fields: tuple[str, ...]
    forbidden_fields: tuple[str, ...]
    policy_action_authority_behavior: str
    confidence_metadata_behavior: str
    benchmark_metadata_behavior: str
    signature_behavior: str
    audit_behavior: str
    fallback_applied_behavior: str
    fallback_reason_behavior: str | None
    canonicalization_behavior: str
    future_phase_owner: str | None
    contradiction_status: str

    def external_projection(self) -> dict[str, object]:
        """Return stable machine-inspectable matrix output."""
        return {
            "reason_code": self.reason_code.value,
            "envelope_status": self.envelope_status,
            "source_predicate": self.source_predicate,
            "allowed_fields": list(self.allowed_fields),
            "forbidden_fields": list(self.forbidden_fields),
            "policy_action_authority_behavior": self.policy_action_authority_behavior,
            "confidence_metadata_behavior": self.confidence_metadata_behavior,
            "benchmark_metadata_behavior": self.benchmark_metadata_behavior,
            "signature_behavior": self.signature_behavior,
            "audit_behavior": self.audit_behavior,
            "fallback_applied_behavior": self.fallback_applied_behavior,
            "fallback_reason_behavior": self.fallback_reason_behavior,
            "canonicalization_behavior": self.canonicalization_behavior,
            "future_phase_owner": self.future_phase_owner,
            "contradiction_status": self.contradiction_status,
        }


def evaluate_reason_truth_state(
    reason_code: ReasonCode,
    envelope_candidate: dict[str, Any] | None = None,
) -> ReasonTruthDecision:
    """Evaluate one reason code against an optional envelope candidate."""
    code = require_reason_code(reason_code)
    definition = get_reason_definition(code)
    if envelope_candidate is not None:
        validate_reason_truth_payload(definition.code, envelope_candidate)
    return _decision_from_definition(definition)


def apply_reason_truth_matrix(
    reason_code: ReasonCode,
    envelope_candidate: dict[str, Any],
) -> ReasonTruthDecision:
    """Validate an envelope candidate under a reason-code matrix row."""
    return evaluate_reason_truth_state(reason_code, envelope_candidate)


def validate_reason_truth_payload(
    reason_code: ReasonCode,
    payload: dict[str, Any],
) -> None:
    """Fail closed on P6 contradiction fixtures."""
    if not isinstance(payload, dict):
        raise ReasonTruthMatrixError("payload_not_object")
    code = require_reason_code(reason_code)
    definition = get_reason_definition(code)
    _reject_forbidden_fields(definition, payload)
    _validate_fallback(definition, payload)
    _validate_reason_specific_contradictions(code, payload)


def validate_reason_truth_matrix(
    registry: dict[ReasonCode, ReasonCodeDefinition] | None = None,
) -> int:
    """Validate matrix registry completeness and source-predicate behavior."""
    count = validate_reason_code_registry(registry)
    current = registry or REASON_CODE_REGISTRY
    missing = sorted(REQUIRED_P6_REASON_CODES - {code.value for code in current})
    if missing:
        raise ReasonTruthMatrixError(f"required_reason_codes_missing:{missing}")
    for definition in current.values():
        _decision_from_definition(definition)
    return count


def _decision_from_definition(definition: ReasonCodeDefinition) -> ReasonTruthDecision:
    fallback = definition.fallback_reason
    return ReasonTruthDecision(
        reason_code=definition.code,
        envelope_status=definition.envelope_status,
        source_predicate=definition.source_predicate,
        allowed_fields=tuple(sorted(definition.allowed_fields)),
        forbidden_fields=tuple(sorted(definition.forbidden_fields)),
        policy_action_authority_behavior=definition.policy_action_authority_behavior,
        confidence_metadata_behavior=definition.confidence_metadata_behavior,
        benchmark_metadata_behavior=definition.benchmark_metadata_behavior,
        signature_behavior=definition.signature_behavior,
        audit_behavior=definition.audit_behavior,
        fallback_applied_behavior=definition.fallback_applied,
        fallback_reason_behavior=(
            fallback.value if isinstance(fallback, ReasonCode) else fallback
        ),
        canonicalization_behavior=definition.canonicalization_behavior,
        future_phase_owner=definition.future_phase_owner,
        contradiction_status="accepted_no_contradiction",
    )


def require_reason_code(value: object) -> ReasonCode:
    """Require an internal ReasonCode enum member before matrix evaluation."""
    if not isinstance(value, ReasonCode):
        raise ReasonTruthMatrixError(
            f"reason_code_not_enum:{type(value).__name__}"
        )
    return value


def _reject_forbidden_fields(
    definition: ReasonCodeDefinition, payload: dict[str, Any]
) -> None:
    forbidden = set(definition.forbidden_fields)
    for field in forbidden:
        if field in payload and payload[field] is not None:
            raise ReasonTruthMatrixError(
                f"forbidden_field_present:{definition.code.value}:{field}"
            )


def _validate_fallback(
    definition: ReasonCodeDefinition, payload: dict[str, Any]
) -> None:
    if "fallback_applied" in payload:
        applied = payload["fallback_applied"]
        if definition.fallback_applied == "required" and applied is not True:
            raise ReasonTruthMatrixError(
                f"fallback_required:{definition.code.value}"
            )
        if definition.fallback_applied == "forbidden" and applied is not False:
            raise ReasonTruthMatrixError(
                f"fallback_forbidden:{definition.code.value}"
            )
    if "fallback_reason" in payload:
        expected = definition.fallback_reason
        expected_value = expected.value if isinstance(expected, ReasonCode) else expected
        actual = payload["fallback_reason"]
        if expected_value is not None and actual != expected_value:
            raise ReasonTruthMatrixError(
                f"fallback_reason_mismatch:{definition.code.value}:{actual}"
            )
        if actual is not None and not isinstance(actual, str):
            raise ReasonTruthMatrixError(
                f"fallback_reason_not_enum_string:{definition.code.value}"
            )
        if isinstance(actual, str) and actual.startswith(("system:", "developer:")):
            raise ReasonTruthMatrixError(
                f"fallback_reason_provider_text:{definition.code.value}"
            )


def _validate_reason_specific_contradictions(
    code: ReasonCode, payload: dict[str, Any]
) -> None:
    if code == ReasonCode.DIAGNOSTICS_FAILED:
        _reject_available_confidence(code, payload)
    elif code == ReasonCode.CONFIDENCE_UNAVAILABLE:
        _reject_fake_confidence(code, payload)
    elif code == ReasonCode.SOURCE_SNAPSHOT_STALE:
        _reject_verified_current_snapshot(code, payload)
    elif code == ReasonCode.MONEY_SOURCE_NOT_AUTHORITATIVE:
        _reject_money_fields(code, payload)
    elif code in {
        ReasonCode.POLICY_DENIED,
        ReasonCode.POLICY_ENGINE_NOT_AVAILABLE,
        ReasonCode.SCOPE_DENIED,
        ReasonCode.TENANT_MISMATCH,
        ReasonCode.RATE_LIMITED,
    }:
        _reject_action_policy(code, payload)
    elif code == ReasonCode.BENCHMARK_UNAVAILABLE:
        _reject_benchmark_values(code, payload)
    elif code == ReasonCode.PROVIDER_TEXT_QUARANTINED:
        _reject_provider_text_authority(code, payload)
    elif code in {
        ReasonCode.SCHEMA_VERSION_UNSUPPORTED,
        ReasonCode.CANONICALIZATION_VERSION_UNSUPPORTED,
        ReasonCode.SCHEMA_DOWNGRADE_REJECTED,
    }:
        _reject_success_semantics(code, payload)
    elif code == ReasonCode.SIGNATURE_ALGORITHM_UNSUPPORTED:
        _reject_valid_signature_behavior(code, payload)
    elif code == ReasonCode.ARTIFACT_PRUNED:
        _reject_artifact_claims(code, payload)
    elif code == ReasonCode.DETERMINISTIC_EVIDENCE_UNAVAILABLE:
        _reject_money_fields(code, payload)


def _reject_available_confidence(code: ReasonCode, payload: dict[str, Any]) -> None:
    confidence = _metadata(payload, "confidence_metadata")
    if confidence.get("confidence_status") == "available":
        raise ReasonTruthMatrixError(f"diagnostics_failed_available_confidence:{code}")
    if confidence.get("diagnostics_status") == "passed":
        raise ReasonTruthMatrixError(f"diagnostics_failed_passed_diagnostics:{code}")
    if confidence.get("confidence_score_basis_points") is not None:
        raise ReasonTruthMatrixError(f"diagnostics_failed_fake_score:{code}")


def _reject_fake_confidence(code: ReasonCode, payload: dict[str, Any]) -> None:
    confidence = _metadata(payload, "confidence_metadata")
    if confidence.get("confidence_status") == "available":
        raise ReasonTruthMatrixError(f"confidence_unavailable_marked_available:{code}")
    if confidence.get("confidence_score_basis_points") is not None:
        raise ReasonTruthMatrixError(f"confidence_unavailable_fake_score:{code}")


def _reject_verified_current_snapshot(code: ReasonCode, payload: dict[str, Any]) -> None:
    temporal = _metadata(payload, "evidence_temporal_boundary")
    if temporal.get("staleness_status") == "current":
        raise ReasonTruthMatrixError(f"source_snapshot_stale_marked_current:{code}")
    if temporal.get("snapshot_consistency_status") == "consistent":
        raise ReasonTruthMatrixError(f"source_snapshot_stale_marked_consistent:{code}")


def _reject_money_fields(code: ReasonCode, payload: dict[str, Any]) -> None:
    for field in MONEY_FIELDS:
        if field in payload and payload[field] is not None:
            raise ReasonTruthMatrixError(f"money_not_authoritative_field_present:{field}:{code}")


def _reject_action_policy(code: ReasonCode, payload: dict[str, Any]) -> None:
    policy = _metadata(payload, "policy_action_authority")
    state = policy.get("policy_state")
    if state in ACTION_LIKE_POLICY_STATES:
        raise ReasonTruthMatrixError(f"policy_denial_action_like_state:{state}:{code}")
    serialized = str(policy)
    for token in (
        "auto_executable_within_policy",
        "execute",
        "auto_execute",
        "direct_action_allowed",
        "trust.action.execute_allowed",
    ):
        if token in serialized and "forbidden_scopes" not in serialized:
            raise ReasonTruthMatrixError(f"policy_denial_action_token:{token}:{code}")


def _reject_benchmark_values(code: ReasonCode, payload: dict[str, Any]) -> None:
    benchmark = _metadata(payload, "benchmark_metadata")
    if benchmark.get("benchmark_status") == "available":
        raise ReasonTruthMatrixError(f"benchmark_unavailable_marked_available:{code}")
    if benchmark.get("benchmark_ref") is not None:
        raise ReasonTruthMatrixError(f"benchmark_unavailable_ref_present:{code}")
    if benchmark.get("benchmark_hash") is not None:
        raise ReasonTruthMatrixError(f"benchmark_unavailable_hash_present:{code}")
    forbidden_value_keys = {
        "benchmark_value",
        "benchmark_rate",
        "raw_benchmark",
        "decision_safe_benchmark",
    }
    if forbidden_value_keys & set(benchmark):
        raise ReasonTruthMatrixError(f"benchmark_unavailable_value_present:{code}")


def _reject_provider_text_authority(code: ReasonCode, payload: dict[str, Any]) -> None:
    for path in (
        "fallback_reason",
        "policy_action_authority.reason_code",
        "truth_type",
        "causal_status",
        "model_assumption",
        "data_completeness_status",
    ):
        value = _path_value(payload, path)
        if isinstance(value, str) and _looks_like_provider_control(value):
            raise ReasonTruthMatrixError(f"provider_text_in_authority:{path}:{code}")


def _reject_success_semantics(code: ReasonCode, payload: dict[str, Any]) -> None:
    if payload.get("envelope_status") == "success" or payload.get("status") == "success":
        raise ReasonTruthMatrixError(f"unsupported_version_success_semantics:{code}")
    if payload.get("truth_type") in {
        "deterministic_revenue_verification",
        "deterministic_match_verdict",
        "deterministic_attribution",
    }:
        raise ReasonTruthMatrixError(f"unsupported_version_truth_success:{code}")


def _reject_valid_signature_behavior(code: ReasonCode, payload: dict[str, Any]) -> None:
    behavior = payload.get("signature_behavior")
    if behavior in {"valid", "verified", "signature_valid"}:
        raise ReasonTruthMatrixError(f"unsupported_signature_marked_valid:{code}")


def _reject_artifact_claims(code: ReasonCode, payload: dict[str, Any]) -> None:
    if payload.get("artifact_ref") is not None or payload.get("artifact_hash") is not None:
        raise ReasonTruthMatrixError(f"artifact_pruned_artifact_present:{code}")


def _metadata(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ReasonTruthMatrixError(f"metadata_not_object:{key}")
    return value


def _path_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _looks_like_provider_control(value: str) -> bool:
    lower = value.lower()
    return any(
        token in lower
        for token in (
            "system:",
            "developer:",
            "ignore previous",
            "auto_execute",
            "</system>",
            "```tool",
        )
    )


def assert_reason_known(reason_code: str | ReasonCode) -> ReasonCode:
    """Public helper for P5-compatible refusal paths."""
    try:
        return coerce_reason_code(reason_code)
    except ReasonCodeRegistryError as exc:
        raise ReasonTruthMatrixError(str(exc)) from exc


validate_reason_truth_matrix()

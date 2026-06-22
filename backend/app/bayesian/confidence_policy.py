"""Backend-owned confidence semantics for B2.4-P10 projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


CONFIDENCE_POLICY_VERSION = "b24-p10-confidence-policy-v1"
CONFIDENCE_SEMANTICS_VERSION = "b24-p10-confidence-semantics-v1"


class ConfidenceBucket(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNAVAILABLE = "unavailable"


class ConfidenceBucketReason(StrEnum):
    NARROW_INTERVAL = "narrow_interval"
    MODERATE_INTERVAL = "moderate_interval"
    WIDE_INTERVAL = "wide_interval"
    NO_FIT = "no_fit"
    INSUFFICIENT_DATA = "insufficient_data"
    NONCONVERGED = "nonconverged"
    BAD_RHAT = "bad_rhat"
    LOW_ESS = "low_ess"
    DIVERGENCE = "divergence"
    TIMEOUT = "timeout"
    WORKER_FAILURE = "worker_failure"
    INPUT_TOO_LARGE = "input_too_large"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    ARTIFACT_PRUNED = "artifact_pruned"
    ARTIFACT_QUOTA_EXCEEDED = "artifact_quota_exceeded"
    SOURCE_SNAPSHOT_CHANGED = "source_snapshot_changed"
    REFIT_LOCKED = "refit_locked"
    UNSUPPORTED_MODEL_TYPE = "unsupported_model_type"
    BAYESIAN_NOT_IMPLEMENTED = "bayesian_not_implemented"


@dataclass(frozen=True)
class ConfidencePolicyDecision:
    """Final backend confidence classification."""

    confidence_available: bool
    confidence_bucket: ConfidenceBucket
    confidence_bucket_reason: ConfidenceBucketReason
    confidence_policy_version: str = CONFIDENCE_POLICY_VERSION
    confidence_semantics_version: str = CONFIDENCE_SEMANTICS_VERSION


@dataclass(frozen=True)
class ConfidencePolicyInput:
    """Normalized fit and deterministic context for bucket classification."""

    deterministic_revenue_minor: int
    fit_id: str | None
    fit_status: str | None
    diagnostics_status: str | None
    credible_interval_status: str | None
    fallback_applied: bool
    fallback_reason: str | None
    diagnostic_failure_reason: str | None
    hdi_lower: float | None
    hdi_upper: float | None
    artifact_ref: str | None
    artifact_hash: str | None
    artifact_lifecycle_status: str | None
    source_snapshot_mismatch: bool = False


FALLBACK_REASON_MAP: dict[str, ConfidenceBucketReason] = {
    "source_window_empty": ConfidenceBucketReason.INSUFFICIENT_DATA,
    "insufficient_data": ConfidenceBucketReason.INSUFFICIENT_DATA,
    "insufficient_privacy_cohort": ConfidenceBucketReason.INSUFFICIENT_DATA,
    "input_too_large": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "feature_width_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "source_window_too_large": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "memory_bound_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "graph_complexity_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "parameter_count_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "hierarchy_width_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "compilation_memory_bound_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "timeout": ConfidenceBucketReason.TIMEOUT,
    "worker_failure": ConfidenceBucketReason.WORKER_FAILURE,
    "no_convergence": ConfidenceBucketReason.NONCONVERGED,
    "resource_bound_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "source_snapshot_mismatch": ConfidenceBucketReason.SOURCE_SNAPSHOT_CHANGED,
    "source_snapshot_changed": ConfidenceBucketReason.SOURCE_SNAPSHOT_CHANGED,
    "source_unavailable": ConfidenceBucketReason.INSUFFICIENT_DATA,
    "artifact_unavailable": ConfidenceBucketReason.ARTIFACT_UNAVAILABLE,
    "storage_quota_exceeded": ConfidenceBucketReason.ARTIFACT_QUOTA_EXCEEDED,
    "refit_locked": ConfidenceBucketReason.REFIT_LOCKED,
    "unsupported_model_type": ConfidenceBucketReason.UNSUPPORTED_MODEL_TYPE,
    "bayesian_not_implemented": ConfidenceBucketReason.BAYESIAN_NOT_IMPLEMENTED,
}

DIAGNOSTIC_REASON_MAP: dict[str, ConfidenceBucketReason] = {
    "bad_rhat": ConfidenceBucketReason.BAD_RHAT,
    "low_ess": ConfidenceBucketReason.LOW_ESS,
    "divergence": ConfidenceBucketReason.DIVERGENCE,
    "diagnostics_timeout": ConfidenceBucketReason.TIMEOUT,
    "diagnostics_memory_exceeded": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "diagnostics_failed": ConfidenceBucketReason.NONCONVERGED,
    "nonfinite_diagnostic": ConfidenceBucketReason.NONCONVERGED,
    "invalid_diagnostic_summary": ConfidenceBucketReason.NONCONVERGED,
    "diagnostic_scope_too_large": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "interval_dimension_exceeded": ConfidenceBucketReason.NONCONVERGED,
    "interval_payload_too_large": ConfidenceBucketReason.INPUT_TOO_LARGE,
    "skipped_non_sampled": ConfidenceBucketReason.NONCONVERGED,
}


def _unavailable(reason: ConfidenceBucketReason) -> ConfidencePolicyDecision:
    return ConfidencePolicyDecision(
        confidence_available=False,
        confidence_bucket=ConfidenceBucket.UNAVAILABLE,
        confidence_bucket_reason=reason,
    )


def _coerce_policy_input(value: ConfidencePolicyInput | dict[str, Any]) -> ConfidencePolicyInput:
    if isinstance(value, ConfidencePolicyInput):
        return value
    return ConfidencePolicyInput(
        deterministic_revenue_minor=int(value.get("deterministic_revenue_minor") or 0),
        fit_id=_nullable_str(value.get("fit_id")),
        fit_status=_nullable_str(value.get("fit_status") or value.get("status")),
        diagnostics_status=_nullable_str(value.get("diagnostic_status")),
        credible_interval_status=_nullable_str(value.get("credible_interval_status")),
        fallback_applied=bool(value.get("fallback_applied") or False),
        fallback_reason=_nullable_str(value.get("fallback_reason")),
        diagnostic_failure_reason=_nullable_str(value.get("diagnostic_failure_reason")),
        hdi_lower=_nullable_float(value.get("hdi_lower")),
        hdi_upper=_nullable_float(value.get("hdi_upper")),
        artifact_ref=_nullable_str(value.get("artifact_ref")),
        artifact_hash=_nullable_str(value.get("artifact_hash")),
        artifact_lifecycle_status=_nullable_str(value.get("artifact_lifecycle_status")),
        source_snapshot_mismatch=bool(value.get("source_snapshot_mismatch") or False),
    )


def _nullable_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nullable_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_confidence(
    value: ConfidencePolicyInput | dict[str, Any],
) -> ConfidencePolicyDecision:
    """Return final P10 confidence semantics owned by the backend."""

    data = _coerce_policy_input(value)
    if data.source_snapshot_mismatch:
        return _unavailable(ConfidenceBucketReason.SOURCE_SNAPSHOT_CHANGED)
    if data.fit_id is None:
        return _unavailable(ConfidenceBucketReason.NO_FIT)
    if data.fallback_applied:
        reason = FALLBACK_REASON_MAP.get(
            data.fallback_reason or "",
            ConfidenceBucketReason.NONCONVERGED,
        )
        return _unavailable(reason)
    if data.fit_status in {"failed", "timeout", "worker_lost", "fallback_only", "cancelled"}:
        reason = FALLBACK_REASON_MAP.get(
            data.fallback_reason or data.fit_status or "",
            ConfidenceBucketReason.NONCONVERGED,
        )
        return _unavailable(reason)
    if data.diagnostics_status != "passed":
        reason = DIAGNOSTIC_REASON_MAP.get(
            data.diagnostic_failure_reason or "",
            ConfidenceBucketReason.NONCONVERGED,
        )
        return _unavailable(reason)
    if data.credible_interval_status not in {"available"}:
        return _unavailable(
            DIAGNOSTIC_REASON_MAP.get(
                data.diagnostic_failure_reason or "",
                ConfidenceBucketReason.NONCONVERGED,
            )
        )
    if data.hdi_lower is None or data.hdi_upper is None:
        return _unavailable(ConfidenceBucketReason.NONCONVERGED)
    if data.artifact_ref is None or data.artifact_hash is None:
        return _unavailable(ConfidenceBucketReason.ARTIFACT_UNAVAILABLE)
    if data.artifact_lifecycle_status in {"rejected"}:
        return _unavailable(ConfidenceBucketReason.ARTIFACT_UNAVAILABLE)

    width = max(data.hdi_upper - data.hdi_lower, 0.0)
    denominator = max(abs(float(data.deterministic_revenue_minor)), 1.0)
    width_ratio = width / denominator
    if width_ratio <= 0.10:
        return ConfidencePolicyDecision(
            confidence_available=True,
            confidence_bucket=ConfidenceBucket.HIGH,
            confidence_bucket_reason=ConfidenceBucketReason.NARROW_INTERVAL,
        )
    if width_ratio <= 0.25:
        return ConfidencePolicyDecision(
            confidence_available=True,
            confidence_bucket=ConfidenceBucket.MEDIUM,
            confidence_bucket_reason=ConfidenceBucketReason.MODERATE_INTERVAL,
        )
    return ConfidencePolicyDecision(
        confidence_available=True,
        confidence_bucket=ConfidenceBucket.LOW,
        confidence_bucket_reason=ConfidenceBucketReason.WIDE_INTERVAL,
    )

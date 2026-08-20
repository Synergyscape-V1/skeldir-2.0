"""Single-owner B2.4 confidence classification policy.

This neutral module is intentionally reachable from the Trust path.  It classifies
already-persisted fit, diagnostic, and artifact state; it cannot plan, dispatch, or
execute Bayesian work.  ``app.bayesian.confidence_policy`` is a compatibility
facade over this module so B2.4 and B2.5 cannot drift into separate classifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


CONFIDENCE_POLICY_VERSION = "b24-p10-confidence-policy-v1"
CONFIDENCE_SEMANTICS_VERSION = "b24-p10-confidence-semantics-v1"

#: Single owner of the allowable future-skew tolerance between the clock that
#: stamped a piece of evidence and the clock that reads it. The database mirrors
#: this exact number in ``public.b24_evidence_future_skew_tolerance_seconds()``
#: and the B2.5-P13 C5 CI gate asserts the two are equal, so producer and
#: consumer can never end up enforcing two different temporal policies.
#:
#: A bounded tolerance rather than a strict ``<= now()`` because the database
#: clock and the API clock are genuinely different clocks; a few seconds of skew
#: is a fact of deployment, thirty days is a defect.
_TEMPORAL_POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "trust-api"
    / "temporal-policy.v1.yaml"
)


@lru_cache(maxsize=1)
def _temporal_policy() -> dict[str, object]:
    with _TEMPORAL_POLICY_PATH.open(encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    if not isinstance(policy, dict):
        raise RuntimeError("temporal_policy_not_object")
    return policy


EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS = int(
    _temporal_policy()["evidence_future_skew_tolerance_seconds"]
)

#: The largest age the wire contract can represent in ``data_freshness_seconds``.
#: Evidence older than this is not misreported as exactly this old -- see
#: ``data_freshness_bound`` in the evidence temporal boundary.
EVIDENCE_FRESHNESS_CEILING_SECONDS = int(
    _temporal_policy()["evidence_freshness_ceiling_seconds"]
)


def evidence_timestamp_is_plausible(
    value: object, *, authoritative_now: datetime | None = None
) -> bool:
    """True when ``value`` is not materially in the future of the reading clock.

    ``None`` is plausible: absent evidence is handled by completeness rules, not
    by temporal rules. A non-datetime is not.
    """

    if value is None:
        return True
    if not isinstance(value, datetime):
        return False
    now = authoritative_now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    horizon = now + timedelta(seconds=EVIDENCE_FUTURE_SKEW_TOLERANCE_SECONDS)
    return value <= horizon


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
    SOURCE_AUTHORITY_UNKNOWN = "source_authority_unknown"
    MULTI_CURRENCY_UNSUPPORTED = "multi_currency_unsupported"
    PERSISTED_CLASSIFICATION_MISSING = "persisted_classification_missing"
    PERSISTED_CLASSIFICATION_INVALID = "persisted_classification_invalid"
    REFIT_LOCKED = "refit_locked"
    UNSUPPORTED_MODEL_TYPE = "unsupported_model_type"
    EVIDENCE_TIMESTAMP_IMPLAUSIBLE = "evidence_timestamp_implausible"
    BAYESIAN_NOT_IMPLEMENTED = "bayesian_not_implemented"


@dataclass(frozen=True)
class ConfidencePolicyDecision:
    """Final B2.4 confidence classification."""

    confidence_available: bool
    confidence_bucket: ConfidenceBucket
    confidence_bucket_reason: ConfidenceBucketReason
    confidence_policy_version: str = CONFIDENCE_POLICY_VERSION
    confidence_semantics_version: str = CONFIDENCE_SEMANTICS_VERSION


@dataclass(frozen=True)
class ConfidencePolicyInput:
    """Persisted fit and deterministic context used for classification."""

    deterministic_revenue_minor: int
    currency_count: int
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
    "artifact_pruned": ConfidenceBucketReason.ARTIFACT_PRUNED,
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


def _coerce_policy_input(
    value: ConfidencePolicyInput | dict[str, Any],
) -> ConfidencePolicyInput:
    if isinstance(value, ConfidencePolicyInput):
        return value
    return ConfidencePolicyInput(
        deterministic_revenue_minor=int(value.get("deterministic_revenue_minor") or 0),
        currency_count=int(value.get("currency_count") or 0),
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


def classify_confidence(
    value: ConfidencePolicyInput | dict[str, Any],
) -> ConfidencePolicyDecision:
    """Classify persisted B2.4 state without computing diagnostics or fitting."""

    data = _coerce_policy_input(value)
    if data.source_snapshot_mismatch:
        return _unavailable(ConfidenceBucketReason.SOURCE_SNAPSHOT_CHANGED)
    if data.currency_count > 1:
        return _unavailable(ConfidenceBucketReason.MULTI_CURRENCY_UNSUPPORTED)
    if data.fit_id is None:
        return _unavailable(ConfidenceBucketReason.NO_FIT)
    if data.fallback_applied:
        return _unavailable(
            FALLBACK_REASON_MAP.get(
                data.fallback_reason or "", ConfidenceBucketReason.NONCONVERGED
            )
        )
    if data.fit_status in {
        "failed",
        "timeout",
        "worker_lost",
        "fallback_only",
        "cancelled",
    }:
        return _unavailable(
            FALLBACK_REASON_MAP.get(
                data.fallback_reason or data.fit_status or "",
                ConfidenceBucketReason.NONCONVERGED,
            )
        )
    if data.diagnostics_status != "passed":
        return _unavailable(
            DIAGNOSTIC_REASON_MAP.get(
                data.diagnostic_failure_reason or "",
                ConfidenceBucketReason.NONCONVERGED,
            )
        )
    if data.credible_interval_status != "available":
        return _unavailable(
            DIAGNOSTIC_REASON_MAP.get(
                data.diagnostic_failure_reason or "",
                ConfidenceBucketReason.NONCONVERGED,
            )
        )
    if data.hdi_lower is None or data.hdi_upper is None:
        return _unavailable(ConfidenceBucketReason.NONCONVERGED)
    if data.artifact_lifecycle_status == "pruned":
        return _unavailable(ConfidenceBucketReason.ARTIFACT_PRUNED)
    if data.artifact_lifecycle_status == "rejected":
        return _unavailable(ConfidenceBucketReason.ARTIFACT_UNAVAILABLE)
    if data.artifact_ref is None or data.artifact_hash is None:
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


def persisted_confidence_decision(
    *,
    confidence_bucket: str | None,
    confidence_bucket_reason: str | None,
    confidence_policy_version: str | None,
    confidence_semantics_version: str | None,
    deterministic_revenue_minor: object = None,
    deterministic_row_count: object = None,
    match_verdict_count: object = None,
    currency_count: object = None,
    confidence_classified_at: object = None,
    confidence_evidence_snapshot_hash: str | None = None,
    source_snapshot_hash: str | None = None,
    source_read_started_at: object = None,
    source_read_completed_at: object = None,
    fit_status: str | None = None,
    data_completeness_status: str | None = None,
    fallback_applied: bool | None = None,
    diagnostic_status: str | None = None,
    credible_interval_status: str | None = None,
    authoritative_now: datetime | None = None,
) -> ConfidencePolicyDecision:
    """Validate and project a B2.4-persisted classification without recomputing it."""

    # Absolute temporal plausibility is checked before anything else, and for
    # every row rather than only for available ones. The C4 constraints proved
    # relative chronology (start <= end <= classified); a fit dated thirty days
    # ahead satisfies all of it. `trg_b24_evidence_temporal_plausibility` blocks
    # such a row being written today, but rows written before that trigger
    # existed are still readable, so the consumer revalidates rather than
    # trusting that the producer was always governed.
    for stamp in (
        source_read_started_at,
        source_read_completed_at,
        confidence_classified_at,
    ):
        if stamp is not None and not evidence_timestamp_is_plausible(
            stamp, authoritative_now=authoritative_now
        ):
            return _unavailable(ConfidenceBucketReason.EVIDENCE_TIMESTAMP_IMPLAUSIBLE)
    if not confidence_bucket or not confidence_bucket_reason:
        return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_MISSING)
    try:
        bucket = ConfidenceBucket(confidence_bucket)
        reason = ConfidenceBucketReason(confidence_bucket_reason)
    except ValueError:
        return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)

    available_pairs = {
        ConfidenceBucket.HIGH: ConfidenceBucketReason.NARROW_INTERVAL,
        ConfidenceBucket.MEDIUM: ConfidenceBucketReason.MODERATE_INTERVAL,
        ConfidenceBucket.LOW: ConfidenceBucketReason.WIDE_INTERVAL,
    }
    if bucket is ConfidenceBucket.UNAVAILABLE:
        if reason in set(available_pairs.values()):
            return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)
    elif available_pairs.get(bucket) is not reason:
        return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)
    if (
        confidence_policy_version != CONFIDENCE_POLICY_VERSION
        or confidence_semantics_version != CONFIDENCE_SEMANTICS_VERSION
    ):
        return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)
    if bucket is not ConfidenceBucket.UNAVAILABLE:
        integer_evidence = (
            deterministic_revenue_minor,
            deterministic_row_count,
            match_verdict_count,
            currency_count,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in integer_evidence
        ):
            return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)
        assert isinstance(deterministic_revenue_minor, int)
        assert isinstance(deterministic_row_count, int)
        assert isinstance(match_verdict_count, int)
        assert isinstance(currency_count, int)
        if (
            deterministic_row_count < 0
            or match_verdict_count < 0
            or currency_count < 0
            or currency_count > 1
        ):
            return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)
        if (
            not isinstance(confidence_classified_at, datetime)
            or not confidence_evidence_snapshot_hash
            or confidence_evidence_snapshot_hash != source_snapshot_hash
            or not isinstance(source_read_started_at, datetime)
            or not isinstance(source_read_completed_at, datetime)
            or source_read_completed_at < source_read_started_at
            or confidence_classified_at < source_read_completed_at
            or fit_status != "succeeded"
            or data_completeness_status != "complete"
            or fallback_applied is not False
            or diagnostic_status != "passed"
            or credible_interval_status != "available"
        ):
            return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)
    return ConfidencePolicyDecision(
        confidence_available=bucket is not ConfidenceBucket.UNAVAILABLE,
        confidence_bucket=bucket,
        confidence_bucket_reason=reason,
        confidence_policy_version=confidence_policy_version,
        confidence_semantics_version=confidence_semantics_version,
    )

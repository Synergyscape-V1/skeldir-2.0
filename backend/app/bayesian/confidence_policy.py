"""Compatibility facade for the single-owner B2.4 confidence policy."""

from app.confidence_projection.policy import (
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
    DIAGNOSTIC_REASON_MAP,
    FALLBACK_REASON_MAP,
    ConfidenceBucket,
    ConfidenceBucketReason,
    ConfidencePolicyDecision,
    ConfidencePolicyInput,
    classify_confidence,
    persisted_confidence_decision,
)

__all__ = (
    "CONFIDENCE_POLICY_VERSION",
    "CONFIDENCE_SEMANTICS_VERSION",
    "DIAGNOSTIC_REASON_MAP",
    "FALLBACK_REASON_MAP",
    "ConfidenceBucket",
    "ConfidenceBucketReason",
    "ConfidencePolicyDecision",
    "ConfidencePolicyInput",
    "classify_confidence",
    "persisted_confidence_decision",
)

"""B2.3 revenue verification semantic authority package."""

from .semantic_authority import (
    B23DiscrepancyClass,
    B23Verdict,
    CanonicalReferenceResult,
    CanonicalizationStatus,
    PrecedenceResolution,
    classify_payment_adjustment_support,
    canonicalize_attribution_commerce_reference,
    canonicalize_verified_commerce_reference,
    map_b23_discrepancy_for_downstream,
    map_b23_verdict_for_downstream,
    resolve_canonical_match_key,
    validate_delayed_arrival_strategy,
    validate_delayed_arrival_topology,
)

__all__ = [
    "B23DiscrepancyClass",
    "B23Verdict",
    "CanonicalReferenceResult",
    "CanonicalizationStatus",
    "PrecedenceResolution",
    "classify_payment_adjustment_support",
    "canonicalize_attribution_commerce_reference",
    "canonicalize_verified_commerce_reference",
    "map_b23_discrepancy_for_downstream",
    "map_b23_verdict_for_downstream",
    "resolve_canonical_match_key",
    "validate_delayed_arrival_strategy",
    "validate_delayed_arrival_topology",
]

"""Machine-owned B2.4-P2 deterministic source input contract.

This module is the authority for what B2.4 source snapshot hashing may observe.
It intentionally describes sanitized deterministic B2.1/B2.3 state only.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


SOURCE_CONTRACT_VERSION = "b24-source-v1"
ELIGIBILITY_POLICY_VERSION = "b24-eligibility-v1"
STREAM_CHUNK_FORMAT_VERSION = "b24-canonical-chunk-v1"
SENTINEL_PREFIX = "B24_SOURCE_SNAPSHOT_SENTINEL"
SENTINEL_FALLBACK_REASONS = (
    "source_window_empty",
    "insufficient_data",
    "insufficient_privacy_cohort",
)

REQUIRED_TRANSACTION_ISOLATION = "REPEATABLE READ"
REQUIRED_TRANSACTION_ACCESS_MODE = "READ ONLY"
REQUIRED_TENANT_GUC = "app.current_tenant_id"
MIN_SPARSE_PRIVACY_FLOOR = 20
# Feature dimensionality is not a privacy cohort. Requiring the privacy floor
# here made eligibility impossible because the canonical channel vocabulary has
# fewer than twenty values. Two independently evidenced, non-direct channels
# are the minimum shape that can support a channel-effect model.
MIN_MODEL_DIMENSION_FLOOR = 2
SOURCE_STREAM_PARTITION_SIZE = 128
SOURCE_STREAM_MAX_ROW_BUFFER = 256


@dataclass(frozen=True)
class SparsePrivacyThresholds:
    """Machine-owned sparse privacy gates enforced before row-level streaming."""

    minimum_eligible_source_events: int = MIN_SPARSE_PRIVACY_FLOOR
    minimum_distinct_source_events: int = MIN_SPARSE_PRIVACY_FLOOR
    minimum_conversion_or_revenue_events: int = MIN_SPARSE_PRIVACY_FLOOR
    minimum_confirmed_match_verdicts: int = MIN_SPARSE_PRIVACY_FLOOR
    minimum_distinct_channels: int = MIN_MODEL_DIMENSION_FLOOR
    minimum_observations_per_currency: int = MIN_SPARSE_PRIVACY_FLOOR
    minimum_source_window_density_days: int = MIN_SPARSE_PRIVACY_FLOOR


SPARSE_PRIVACY_THRESHOLDS = SparsePrivacyThresholds()

ALLOWED_SOURCE_READ_MODELS = MappingProxyType(
    {
        "attribution_events": (
            "id",
            "tenant_id",
            "occurred_at",
            "event_timestamp",
            "event_type",
            "channel",
            "campaign_id",
            "revenue_cents",
            "conversion_value_cents",
            "currency",
            "processing_status",
        ),
        "attribution_allocations": (
            "id",
            "tenant_id",
            "event_id",
            "created_at",
            "channel_code",
            "allocated_revenue_cents",
            "allocation_ratio",
            "model_type",
            "model_version",
            "verified",
            "verification_source",
            "verification_timestamp",
        ),
        "b23_match_verdicts": (
            "id",
            "tenant_id",
            "attribution_event_id",
            "provider",
            "canonical_commerce_reference",
            "status",
            "match_quality",
            "attributed_amount_minor",
            "verified_amount_minor",
            "currency_code",
            "confirmed_at",
            "adjusted_at",
            "last_transition_at",
            "canonical_expected_gross_amount_minor",
            "canonical_captured_gross_amount_minor",
            "canonical_net_verified_amount_minor",
            "discrepancy_amount_minor",
            "discrepancy_ratio_bps",
            "discrepancy_band",
        ),
        "b23_revenue_events": (
            "id",
            "tenant_id",
            "match_verdict_id",
            "provider",
            "canonical_commerce_reference",
            "event_type",
            "currency_code",
            "event_occurred_at",
            "captured_amount_minor",
            "refund_amount_minor",
            "chargeback_amount_minor",
            "reversal_amount_minor",
            "net_effect_sign",
            "is_gross_capture_correction",
        ),
    }
)

FORBIDDEN_MANIFEST_SOURCES = frozenset(
    {
        "attribution_commerce_identities",
        "webhook_ingress_identities",
        "raw_event_payloads",
        "raw provider payloads",
        "oauth tables",
        "token-bearing tables",
        "raw customer identity rows",
    }
)

FORBIDDEN_FIELD_FRAGMENTS = frozenset(
    {
        "email",
        "phone",
        "name",
        "address",
        "ip",
        "user_agent",
        "oauth",
        "token",
        "secret",
        "raw_payload",
        "payload",
        "native_event_reference",
        "native_commerce_reference",
        "session_id",
        "idempotency_key",
        "external_event_id",
    }
)

LIFECYCLE_INCLUSION_RULES = MappingProxyType(
    {
        # Ingestion events are immutable and remain pending after deterministic
        # attribution. Source authority is therefore the verified allocation
        # lineage required by the source queries, not a mutable status flag.
        "attribution_events.processing_status": ("pending", "processed"),
        # Production commerce adapters emit ``purchase``. ``conversion`` is
        # retained for backward-compatible deterministic ingress.
        "attribution_events.event_type": ("conversion", "purchase"),
        "attribution_allocations.verified": (True,),
        "b23_match_verdicts.status": ("matched_confirmed", "adjusted"),
        "b23_revenue_events.event_type": (
            "payment_capture",
            "partial_refund",
            "full_refund",
            "chargeback_lost",
            "chargeback_won",
            "reversal",
        ),
    }
)

LIFECYCLE_EXCLUSION_RULES = MappingProxyType(
    {
        "attribution_events.processing_status": ("failed",),
        "b23_match_verdicts.status": ("pending", "matched_provisional", "unmatched"),
        "b23_revenue_events.event_type": ("chargeback_opened",),
        "source_window": ("out_of_window",),
    }
)

SOURCE_WINDOW_SEMANTICS = MappingProxyType(
    {
        "window": "[source_window_start, source_window_end)",
        "timezone": "UTC",
        "timestamp_precision": "microseconds",
    }
)

CURRENCY_GROUPING_SEMANTICS = "upper-case ISO 4217 currency code; per-currency observation thresholds are enforced before streaming"
INTEGER_MINOR_UNIT_HANDLING = "authoritative money fields remain integer minor units; no DECIMAL/FLOAT money authority"
TIMESTAMP_NORMALIZATION = "all timestamps are serialized as UTC ISO-8601 with microsecond precision and Z suffix"
PRIVACY_BOUNDARY = (
    "B2.4-P2 hashes only sanitized deterministic source state after sparse privacy "
    "preflight; PII, raw payloads, identity rows, token-bearing fields, and sparse "
    "behavioral fingerprints are excluded."
)
VERIFICATION_COVERAGE_RULE = (
    "excluded_in_b24_source_v1: current verification coverage aggregate reads "
    "webhook_ingress_identities, so P2 does not include coverage in the source hash."
)
SOURCE_STREAM_BUFFERING_RULE = (
    "eligible source rows are consumed with SQLAlchemy async streaming, explicit "
    "stream_results/yield_per/max_row_buffer execution options, and Result.partitions(); "
    "full-result materialization is forbidden."
)
SOURCE_STREAM_INDEX_REQUIREMENTS = MappingProxyType(
    {
        "attribution_events": "idx_b24_p2_attribution_events_source_stream",
        "attribution_allocations": "idx_b24_p2_attribution_allocations_source_stream",
        "b23_match_verdicts": "idx_b24_p2_match_verdicts_source_stream",
        "b23_revenue_events": "idx_b24_p2_revenue_events_source_stream",
    }
)


@dataclass(frozen=True)
class SourceReadModel:
    """Hashable source stream definition."""

    name: str
    discriminator: str
    allowed_fields: tuple[str, ...]
    primary_timestamp_field: str
    immutable_tie_breaker: str = "id"
    order_by: tuple[str, ...] = ()


SOURCE_READ_MODELS: tuple[SourceReadModel, ...] = tuple(
    SourceReadModel(
        name=name,
        discriminator=name,
        allowed_fields=fields,
        primary_timestamp_field={
            "attribution_events": "occurred_at",
            "attribution_allocations": "created_at",
            "b23_match_verdicts": "last_transition_at",
            "b23_revenue_events": "event_occurred_at",
        }[name],
        order_by=(
            "source_table_discriminator",
            "tenant_id",
            {
                "attribution_events": "occurred_at ASC NULLS LAST",
                "attribution_allocations": "created_at ASC NULLS LAST",
                "b23_match_verdicts": "last_transition_at ASC NULLS LAST",
                "b23_revenue_events": "event_occurred_at ASC NULLS LAST",
            }[name],
            "id ASC",
        ),
    )
    for name, fields in ALLOWED_SOURCE_READ_MODELS.items()
)


def validate_contract() -> None:
    """Fail closed if source membership violates P2 privacy/order rules."""

    for threshold_name, threshold_value in SPARSE_PRIVACY_THRESHOLDS.__dict__.items():
        floor = (
            MIN_MODEL_DIMENSION_FLOOR
            if threshold_name == "minimum_distinct_channels"
            else MIN_SPARSE_PRIVACY_FLOOR
        )
        if threshold_value < floor:
            raise ValueError(
                f"eligibility threshold below floor: {threshold_name}={threshold_value}"
            )
    for forbidden_source in FORBIDDEN_MANIFEST_SOURCES:
        if forbidden_source in ALLOWED_SOURCE_READ_MODELS:
            raise ValueError(f"forbidden source read model allowed: {forbidden_source}")
    for model in SOURCE_READ_MODELS:
        if "id ASC" not in model.order_by:
            raise ValueError(
                f"source stream lacks immutable id tie-breaker: {model.name}"
            )
        if not any("NULLS" in order_key for order_key in model.order_by):
            raise ValueError(
                f"source stream lacks explicit null ordering: {model.name}"
            )
        for field in model.allowed_fields:
            lowered = field.lower()
            for fragment in FORBIDDEN_FIELD_FRAGMENTS:
                if fragment in lowered:
                    raise ValueError(f"forbidden field in {model.name}: {field}")


validate_contract()

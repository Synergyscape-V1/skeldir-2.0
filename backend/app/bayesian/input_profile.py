"""B2.4-P4 bounded input cardinality profile.

The profiler is deliberately aggregate-only and allocation-free. It consumes
the P2 aggregate preflight result and emits counts used by later arithmetic
envelopes. Future DB-backed rollups can replace these formulas without moving
P4 behind graph construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.bayesian.eligibility import EligibilityPreflightResult
from app.bayesian.model_family_contract import (
    B24_ACTIVE_FEATURE_DIMENSIONS,
    assert_profiled_dimensions_cover_model,
)
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY_VERSION


PROFILE_QUERY_PLAN_PROOF = """
B2.4-P4 source profile is aggregate-only. Runtime profile construction uses
P2 EligibilityPreflightResult counts that are produced before source stream
hashing and never opens ORM relationships, tabular frames, or source-row lists.
Provider and campaign feature cardinality are live-derived from approved
source-contract fields only: b23_match_verdicts.provider,
b23_revenue_events.provider, and attribution_events.campaign_id. They are not
raw payload, identity, token, or PII fields. Cardinality reads are backed by
the B2.4-P4 tenant-leading next-key early-stop indexes:
idx_b24_p4_attribution_events_channel_early_stop,
idx_b24_p4_attribution_events_campaign_early_stop,
idx_b24_p4_match_verdicts_provider_early_stop,
idx_b24_p4_revenue_events_provider_early_stop.
Distinct cardinality gates are governed by
true_next_key_early_stop_cap_plus_one_v1: fake-bounded GROUP BY/LIMIT and
unbounded exact distinct-count SQL are rejected by validate_b24_p4_resource_bounds.py.
Representative source access remains tenant-leading and backed by the P2/P3
source stream indexes:
idx_b24_p2_attribution_events_source_stream,
idx_b24_p2_attribution_allocations_source_stream,
idx_b24_p2_match_verdicts_source_stream,
idx_b24_p2_revenue_events_source_stream,
idx_b24_p3_attribution_events_source_stream_fallback,
idx_b24_p3_attribution_allocations_source_stream_fallback,
idx_b24_p3_match_verdicts_source_stream_fallback,
idx_b24_p3_revenue_events_source_stream_fallback.
No HashAggregate or Sort over a large tenant/window slice is permitted in the
planner path without EXPLAIN/BUFFERS proof.
"""


@dataclass(frozen=True)
class B24InputProfile:
    tenant_id: UUID
    preflight_lease_id: str
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    policy_version: str
    source_row_count: int
    touchpoint_count: int
    conversion_count: int
    channel_count: int
    currency_count: int
    provider_count: int
    campaign_or_feature_count: int
    window_days: int
    cardinality_profiled_dimensions: tuple[str, ...]
    computed_at: datetime


def _window_days(start: datetime, end: datetime) -> int:
    return max(1, (end.date() - start.date()).days + 1)


def build_input_profile_from_preflight(
    *,
    preflight_lease_id: str,
    source_snapshot_hash: str,
    preflight: EligibilityPreflightResult,
) -> B24InputProfile:
    """Build a cardinality profile from bounded aggregate preflight counts."""

    counts = preflight.included_row_counts_by_source
    attribution_event_count = int(counts.get("attribution_events", 0))
    allocation_count = int(counts.get("attribution_allocations", 0))
    match_verdict_count = int(counts.get("b23_match_verdicts", 0))
    revenue_event_count = int(counts.get("b23_revenue_events", 0))
    source_row_count = (
        attribution_event_count
        + allocation_count
        + match_verdict_count
        + revenue_event_count
    )
    currency_count = len(preflight.eligible_amount_minor_by_currency)
    profiled_dimensions = tuple(sorted(B24_ACTIVE_FEATURE_DIMENSIONS))
    assert_profiled_dimensions_cover_model(
        model_type=preflight.model_type,
        profiled_dimensions=profiled_dimensions,
    )
    return B24InputProfile(
        tenant_id=preflight.tenant_id,
        preflight_lease_id=preflight_lease_id,
        model_type=preflight.model_type,
        model_version=preflight.model_version,
        source_window_start=preflight.source_window_start,
        source_window_end=preflight.source_window_end,
        source_snapshot_hash=source_snapshot_hash,
        policy_version=B24_RESOURCE_POLICY_VERSION,
        source_row_count=source_row_count,
        touchpoint_count=allocation_count,
        conversion_count=attribution_event_count + revenue_event_count,
        channel_count=int(preflight.eligible_channel_count),
        currency_count=currency_count,
        provider_count=int(preflight.provider_count),
        campaign_or_feature_count=int(preflight.campaign_or_feature_count),
        window_days=_window_days(
            preflight.source_window_start,
            preflight.source_window_end,
        ),
        cardinality_profiled_dimensions=profiled_dimensions,
        computed_at=datetime.now(timezone.utc),
    )

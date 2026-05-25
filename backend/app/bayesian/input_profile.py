"""B2.4-P4 bounded input cardinality profile.

The profiler is deliberately aggregate-only and allocation-free. It consumes
P2 row-count preflight output plus the snapshot-fresh source-window feature
authority. It never discovers feature cardinality from raw source tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.bayesian.eligibility import EligibilityPreflightResult
from app.bayesian.feature_authority import SourceWindowFeatureAuthority
from app.bayesian.model_family_contract import (
    B24_ACTIVE_FEATURE_DIMENSIONS,
    assert_profiled_dimensions_cover_model,
)
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY_VERSION


PROFILE_QUERY_PLAN_PROOF = """
B2.4-P4 source profile is aggregate-only. Runtime profile construction uses
P2 EligibilityPreflightResult row counts and source-window feature authority
from public.b24_source_window_feature_authority. P4 performs one bounded lookup
by tenant_id, model_type, model_version, source_window_start, source_window_end,
and source_snapshot_hash. Provider, campaign, channel, and currency counts come
from that already-deduplicated snapshot authority. Missing, stale, or mismatched
authority fails closed before graph, sampler, artifact, or dispatch behavior.
P4 does not run raw attribution_events, b23_match_verdicts, or b23_revenue_events
feature discovery during planning; raw recursive probes, COUNT(DISTINCT), UNION
deduplication, and GROUP BY/LIMIT fake bounds are rejected by
validate_b24_p4_resource_bounds.py.
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
    feature_authority: SourceWindowFeatureAuthority,
) -> B24InputProfile:
    """Build a profile from P2 row counts and snapshot feature authority."""

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
    profiled_dimensions = tuple(sorted(B24_ACTIVE_FEATURE_DIMENSIONS))
    assert_profiled_dimensions_cover_model(
        model_type=preflight.model_type,
        profiled_dimensions=profiled_dimensions,
    )
    if feature_authority.source_snapshot_hash != source_snapshot_hash:
        raise ValueError("feature authority snapshot hash mismatch")
    if (
        feature_authority.tenant_id != preflight.tenant_id
        or feature_authority.model_type != preflight.model_type
        or feature_authority.model_version != preflight.model_version
        or feature_authority.source_window_start != preflight.source_window_start
        or feature_authority.source_window_end != preflight.source_window_end
    ):
        raise ValueError("feature authority candidate identity mismatch")
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
        channel_count=int(feature_authority.channel_count),
        currency_count=int(feature_authority.currency_count),
        provider_count=int(feature_authority.provider_count),
        campaign_or_feature_count=int(feature_authority.campaign_or_feature_count),
        window_days=_window_days(
            preflight.source_window_start,
            preflight.source_window_end,
        ),
        cardinality_profiled_dimensions=profiled_dimensions,
        computed_at=datetime.now(timezone.utc),
    )

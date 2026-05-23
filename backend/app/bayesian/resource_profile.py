"""B2.4-P4 resource/profile decision orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.bayesian.design_matrix_envelope import (
    DesignMatrixEnvelope,
    estimate_design_matrix_envelope,
)
from app.bayesian.enums import FallbackReason
from app.bayesian.graph_complexity_envelope import (
    GraphComplexityEnvelope,
    estimate_graph_complexity_envelope,
)
from app.bayesian.input_profile import B24InputProfile, build_input_profile_from_preflight
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY, B24ResourcePolicy
from app.bayesian.source_snapshot import SourceSnapshotResult


@dataclass(frozen=True)
class B24ResourceDecision:
    input_profile: B24InputProfile
    design_envelope: DesignMatrixEnvelope
    graph_envelope: GraphComplexityEnvelope
    decision: str
    failure_reason: FallbackReason | None
    computed_at: datetime

    @property
    def allowed(self) -> bool:
        return self.failure_reason is None


def _mb_to_bytes(value: int) -> int:
    return int(value) * 1024 * 1024


def _failure_reason(
    profile: B24InputProfile,
    design: DesignMatrixEnvelope,
    graph: GraphComplexityEnvelope,
    policy: B24ResourcePolicy,
) -> FallbackReason | None:
    if profile.window_days > policy.max_window_days:
        return FallbackReason.SOURCE_WINDOW_TOO_LARGE
    if (
        profile.source_row_count > policy.max_source_rows
        or profile.touchpoint_count > policy.max_touchpoints
        or profile.conversion_count > policy.max_conversions
    ):
        return FallbackReason.INPUT_TOO_LARGE
    if (
        profile.channel_count > policy.max_channels
        or profile.currency_count > policy.max_currencies
        or profile.provider_count > policy.max_providers
        or profile.campaign_or_feature_count > policy.max_campaigns_or_feature_keys
        or design.estimated_design_matrix_columns > policy.max_campaigns_or_feature_keys
    ):
        return FallbackReason.FEATURE_WIDTH_EXCEEDED
    if (
        design.estimated_design_matrix_cells > policy.max_design_matrix_cells
        or design.estimated_tensor_elements > policy.max_tensor_elements
        or design.estimated_tensor_rank > policy.max_tensor_rank
        or design.estimated_input_memory_bytes > _mb_to_bytes(policy.max_input_memory_mb)
    ):
        return FallbackReason.MEMORY_BOUND_EXCEEDED
    if (
        graph.estimated_hierarchical_groups > policy.max_hierarchical_groups
        or max(graph.estimated_group_levels_by_dimension.values())
        > policy.max_levels_per_hierarchy
    ):
        return FallbackReason.HIERARCHY_WIDTH_EXCEEDED
    if graph.estimated_parameter_count > policy.max_parameter_count:
        return FallbackReason.PARAMETER_COUNT_EXCEEDED
    if graph.estimated_compilation_memory_bytes > _mb_to_bytes(
        policy.max_compilation_memory_mb_estimate
    ):
        return FallbackReason.COMPILATION_MEMORY_BOUND_EXCEEDED
    if (
        graph.estimated_symbolic_nodes > policy.max_graph_nodes_estimate
        or graph.estimated_random_variables > policy.max_random_variables_estimate
        or graph.estimated_plate_size > policy.max_plate_size
        or graph.estimated_logp_terms > policy.max_logp_terms_estimate
        or graph.estimated_transform_ops > policy.max_transform_ops_estimate
    ):
        return FallbackReason.GRAPH_COMPLEXITY_EXCEEDED
    return None


def evaluate_source_snapshot_resource_bounds(
    *,
    snapshot: SourceSnapshotResult,
    preflight_lease_id: str,
    policy: B24ResourcePolicy = B24_RESOURCE_POLICY,
) -> B24ResourceDecision:
    """Evaluate P4 before claim, graph build, sampler dispatch, or artifacts."""

    input_profile = build_input_profile_from_preflight(
        preflight_lease_id=preflight_lease_id,
        source_snapshot_hash=snapshot.source_snapshot_hash,
        preflight=snapshot.preflight,
    )
    return evaluate_input_profile_resource_bounds(input_profile=input_profile, policy=policy)


def evaluate_input_profile_resource_bounds(
    *,
    input_profile: B24InputProfile,
    policy: B24ResourcePolicy = B24_RESOURCE_POLICY,
) -> B24ResourceDecision:
    """Evaluate an already bounded input profile using arithmetic formulas only."""

    design = estimate_design_matrix_envelope(input_profile)
    graph = estimate_graph_complexity_envelope(input_profile, design)
    reason = _failure_reason(input_profile, design, graph, policy)
    return B24ResourceDecision(
        input_profile=input_profile,
        design_envelope=design,
        graph_envelope=graph,
        decision="allowed" if reason is None else "fallback",
        failure_reason=reason,
        computed_at=input_profile.computed_at,
    )

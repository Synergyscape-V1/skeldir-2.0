"""B2.4-P4 formula-only symbolic graph-complexity envelope."""

from __future__ import annotations

from dataclasses import dataclass

from app.bayesian.design_matrix_envelope import DesignMatrixEnvelope
from app.bayesian.input_profile import B24InputProfile
from app.bayesian.resource_bounds import B24_GRAPH_COMPLEXITY_SAFETY_FACTOR


BYTES_PER_SYMBOLIC_NODE_ESTIMATE = 2_048
FIXED_COMPILATION_OVERHEAD_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class GraphComplexityEnvelope:
    estimated_random_variables: int
    estimated_hierarchical_groups: int
    estimated_group_levels_by_dimension: dict[str, int]
    estimated_parameter_count: int
    estimated_logp_terms: int
    estimated_symbolic_nodes: int
    estimated_transform_ops: int
    estimated_compilation_memory_bytes: int
    estimated_plate_size: int


def estimate_graph_complexity_envelope(
    profile: B24InputProfile,
    design: DesignMatrixEnvelope,
) -> GraphComplexityEnvelope:
    """Estimate symbolic graph pressure without importing any sampler stack."""

    levels = {
        "channel": max(1, profile.channel_count),
        "currency": max(1, profile.currency_count),
        "provider": max(1, profile.provider_count),
        "campaign_or_feature": max(1, profile.campaign_or_feature_count),
    }
    hierarchical_groups = sum(levels.values())
    parameters = (
        design.estimated_design_matrix_columns * 3
        + hierarchical_groups * 2
        + max(1, profile.conversion_count)
    )
    random_variables = hierarchical_groups + 8
    logp_terms = profile.source_row_count + profile.conversion_count + random_variables
    transform_ops = random_variables * 2 + hierarchical_groups
    symbolic_nodes = (
        parameters
        + logp_terms
        + transform_ops
        + design.estimated_tensor_rank * 16
    ) * B24_GRAPH_COMPLEXITY_SAFETY_FACTOR
    compilation_memory = (
        symbolic_nodes * BYTES_PER_SYMBOLIC_NODE_ESTIMATE
        + FIXED_COMPILATION_OVERHEAD_BYTES
    )
    return GraphComplexityEnvelope(
        estimated_random_variables=random_variables,
        estimated_hierarchical_groups=hierarchical_groups,
        estimated_group_levels_by_dimension=levels,
        estimated_parameter_count=parameters,
        estimated_logp_terms=logp_terms,
        estimated_symbolic_nodes=symbolic_nodes,
        estimated_transform_ops=transform_ops,
        estimated_compilation_memory_bytes=compilation_memory,
        estimated_plate_size=max(1, profile.source_row_count),
    )

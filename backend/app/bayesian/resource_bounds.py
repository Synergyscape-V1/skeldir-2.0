"""B2.4-P4 versioned resource and graph-complexity policy.

These constants are intentionally machine-owned and deterministic. They are
not Celery process limits; they are semantic pre-graph bounds that reject a
candidate before model input materialization, symbolic graph construction, or
broker dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


B24_RESOURCE_POLICY_VERSION = "b24-resource-policy-v1"


@dataclass(frozen=True)
class B24ResourcePolicy:
    policy_version: str = B24_RESOURCE_POLICY_VERSION
    max_source_rows: int = 250_000
    max_touchpoints: int = 200_000
    max_conversions: int = 75_000
    max_channels: int = 128
    max_currencies: int = 8
    max_providers: int = 16
    max_campaigns_or_feature_keys: int = 2_048
    max_window_days: int = 370
    max_design_matrix_cells: int = 25_000_000
    max_tensor_elements: int = 50_000_000
    max_tensor_rank: int = 4
    max_input_memory_mb: int = 512
    memory_estimate_safety_factor: int = 3
    max_graph_nodes_estimate: int = 100_000
    max_random_variables_estimate: int = 10_000
    max_hierarchical_groups: int = 2_500
    max_levels_per_hierarchy: int = 1_000
    max_plate_size: int = 250_000
    max_parameter_count: int = 100_000
    max_transform_ops_estimate: int = 50_000
    max_logp_terms_estimate: int = 300_000
    max_compilation_memory_mb_estimate: int = 1_024
    graph_complexity_safety_factor: int = 2
    distinct_cardinality_policy: str = "true_next_key_early_stop_cap_plus_one_v1"
    db_work_budget_policy: str = "b24_cardinality_no_exact_distinct_no_group_limit_v1"
    max_cardinality_plan_rows: int = 15_000
    max_cardinality_plan_shared_buffers: int = 60_000
    max_cardinality_plan_temp_blocks: int = 0
    max_cardinality_plan_sort_nodes: int = 0
    max_cardinality_plan_hashaggregate_nodes: int = 0
    max_cardinality_plan_seq_scan_nodes: int = 0
    max_cardinality_plan_bitmap_heap_scan_nodes: int = 0
    max_cardinality_plan_execution_ms: int = 500
    max_cardinality_plan_planning_ms: int = 100
    cardinality_plan_work_mem: str = "1MB"

    def validate(self) -> None:
        zero_budget_fields = {
            "max_cardinality_plan_temp_blocks",
            "max_cardinality_plan_sort_nodes",
            "max_cardinality_plan_hashaggregate_nodes",
            "max_cardinality_plan_seq_scan_nodes",
            "max_cardinality_plan_bitmap_heap_scan_nodes",
        }
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, int) and item.name in zero_budget_fields and value < 0:
                raise ValueError(f"invalid negative B2.4-P4 budget: {item.name}")
            if (
                isinstance(value, int)
                and item.name not in zero_budget_fields
                and value <= 0
            ):
                raise ValueError(f"invalid non-positive B2.4-P4 cap: {item.name}")
            if isinstance(value, str) and not value.strip():
                raise ValueError(f"invalid blank B2.4-P4 policy field: {item.name}")


B24_RESOURCE_POLICY = B24ResourcePolicy()
B24_RESOURCE_POLICY.validate()

# Required directive aliases. Tests and validators assert these names stay
# explicit instead of scattering numeric literals through the codebase.
B24_MAX_SOURCE_ROWS = B24_RESOURCE_POLICY.max_source_rows
B24_MAX_TOUCHPOINTS = B24_RESOURCE_POLICY.max_touchpoints
B24_MAX_CONVERSIONS = B24_RESOURCE_POLICY.max_conversions
B24_MAX_CHANNELS = B24_RESOURCE_POLICY.max_channels
B24_MAX_CURRENCIES = B24_RESOURCE_POLICY.max_currencies
B24_MAX_PROVIDERS = B24_RESOURCE_POLICY.max_providers
B24_MAX_CAMPAIGNS_OR_FEATURE_KEYS = B24_RESOURCE_POLICY.max_campaigns_or_feature_keys
B24_MAX_WINDOW_DAYS = B24_RESOURCE_POLICY.max_window_days
B24_MAX_DESIGN_MATRIX_CELLS = B24_RESOURCE_POLICY.max_design_matrix_cells
B24_MAX_TENSOR_ELEMENTS = B24_RESOURCE_POLICY.max_tensor_elements
B24_MAX_TENSOR_RANK = B24_RESOURCE_POLICY.max_tensor_rank
B24_MAX_INPUT_MEMORY_MB = B24_RESOURCE_POLICY.max_input_memory_mb
B24_MEMORY_ESTIMATE_SAFETY_FACTOR = B24_RESOURCE_POLICY.memory_estimate_safety_factor
B24_MAX_GRAPH_NODES_ESTIMATE = B24_RESOURCE_POLICY.max_graph_nodes_estimate
B24_MAX_RANDOM_VARIABLES_ESTIMATE = B24_RESOURCE_POLICY.max_random_variables_estimate
B24_MAX_HIERARCHICAL_GROUPS = B24_RESOURCE_POLICY.max_hierarchical_groups
B24_MAX_LEVELS_PER_HIERARCHY = B24_RESOURCE_POLICY.max_levels_per_hierarchy
B24_MAX_PLATE_SIZE = B24_RESOURCE_POLICY.max_plate_size
B24_MAX_PARAMETER_COUNT = B24_RESOURCE_POLICY.max_parameter_count
B24_MAX_TRANSFORM_OPS_ESTIMATE = B24_RESOURCE_POLICY.max_transform_ops_estimate
B24_MAX_LOGP_TERMS_ESTIMATE = B24_RESOURCE_POLICY.max_logp_terms_estimate
B24_MAX_COMPILATION_MEMORY_MB_ESTIMATE = (
    B24_RESOURCE_POLICY.max_compilation_memory_mb_estimate
)
B24_GRAPH_COMPLEXITY_SAFETY_FACTOR = B24_RESOURCE_POLICY.graph_complexity_safety_factor
B24_DISTINCT_CARDINALITY_POLICY = B24_RESOURCE_POLICY.distinct_cardinality_policy
B24_DB_WORK_BUDGET_POLICY = B24_RESOURCE_POLICY.db_work_budget_policy
B24_MAX_CARDINALITY_PLAN_ROWS = B24_RESOURCE_POLICY.max_cardinality_plan_rows
B24_MAX_CARDINALITY_PLAN_SHARED_BUFFERS = (
    B24_RESOURCE_POLICY.max_cardinality_plan_shared_buffers
)
B24_MAX_CARDINALITY_PLAN_TEMP_BLOCKS = (
    B24_RESOURCE_POLICY.max_cardinality_plan_temp_blocks
)
B24_MAX_CARDINALITY_PLAN_SORT_NODES = (
    B24_RESOURCE_POLICY.max_cardinality_plan_sort_nodes
)
B24_MAX_CARDINALITY_PLAN_HASHAGGREGATE_NODES = (
    B24_RESOURCE_POLICY.max_cardinality_plan_hashaggregate_nodes
)
B24_MAX_CARDINALITY_PLAN_SEQ_SCAN_NODES = (
    B24_RESOURCE_POLICY.max_cardinality_plan_seq_scan_nodes
)
B24_MAX_CARDINALITY_PLAN_BITMAP_HEAP_SCAN_NODES = (
    B24_RESOURCE_POLICY.max_cardinality_plan_bitmap_heap_scan_nodes
)
B24_MAX_CARDINALITY_PLAN_EXECUTION_MS = (
    B24_RESOURCE_POLICY.max_cardinality_plan_execution_ms
)
B24_MAX_CARDINALITY_PLAN_PLANNING_MS = (
    B24_RESOURCE_POLICY.max_cardinality_plan_planning_ms
)
B24_CARDINALITY_PLAN_WORK_MEM = B24_RESOURCE_POLICY.cardinality_plan_work_mem


def required_policy_caps() -> dict[str, int | str]:
    """Return the policy as stable, test-visible evidence."""

    return {
        "B24_RESOURCE_POLICY_VERSION": B24_RESOURCE_POLICY_VERSION,
        "B24_MAX_SOURCE_ROWS": B24_MAX_SOURCE_ROWS,
        "B24_MAX_TOUCHPOINTS": B24_MAX_TOUCHPOINTS,
        "B24_MAX_CONVERSIONS": B24_MAX_CONVERSIONS,
        "B24_MAX_CHANNELS": B24_MAX_CHANNELS,
        "B24_MAX_CURRENCIES": B24_MAX_CURRENCIES,
        "B24_MAX_PROVIDERS": B24_MAX_PROVIDERS,
        "B24_MAX_CAMPAIGNS_OR_FEATURE_KEYS": B24_MAX_CAMPAIGNS_OR_FEATURE_KEYS,
        "B24_MAX_WINDOW_DAYS": B24_MAX_WINDOW_DAYS,
        "B24_MAX_DESIGN_MATRIX_CELLS": B24_MAX_DESIGN_MATRIX_CELLS,
        "B24_MAX_TENSOR_ELEMENTS": B24_MAX_TENSOR_ELEMENTS,
        "B24_MAX_TENSOR_RANK": B24_MAX_TENSOR_RANK,
        "B24_MAX_INPUT_MEMORY_MB": B24_MAX_INPUT_MEMORY_MB,
        "B24_MEMORY_ESTIMATE_SAFETY_FACTOR": B24_MEMORY_ESTIMATE_SAFETY_FACTOR,
        "B24_MAX_GRAPH_NODES_ESTIMATE": B24_MAX_GRAPH_NODES_ESTIMATE,
        "B24_MAX_RANDOM_VARIABLES_ESTIMATE": B24_MAX_RANDOM_VARIABLES_ESTIMATE,
        "B24_MAX_HIERARCHICAL_GROUPS": B24_MAX_HIERARCHICAL_GROUPS,
        "B24_MAX_LEVELS_PER_HIERARCHY": B24_MAX_LEVELS_PER_HIERARCHY,
        "B24_MAX_PLATE_SIZE": B24_MAX_PLATE_SIZE,
        "B24_MAX_PARAMETER_COUNT": B24_MAX_PARAMETER_COUNT,
        "B24_MAX_TRANSFORM_OPS_ESTIMATE": B24_MAX_TRANSFORM_OPS_ESTIMATE,
        "B24_MAX_LOGP_TERMS_ESTIMATE": B24_MAX_LOGP_TERMS_ESTIMATE,
        "B24_MAX_COMPILATION_MEMORY_MB_ESTIMATE": B24_MAX_COMPILATION_MEMORY_MB_ESTIMATE,
        "B24_GRAPH_COMPLEXITY_SAFETY_FACTOR": B24_GRAPH_COMPLEXITY_SAFETY_FACTOR,
        "B24_DISTINCT_CARDINALITY_POLICY": B24_DISTINCT_CARDINALITY_POLICY,
        "B24_DB_WORK_BUDGET_POLICY": B24_DB_WORK_BUDGET_POLICY,
        "B24_MAX_CARDINALITY_PLAN_ROWS": B24_MAX_CARDINALITY_PLAN_ROWS,
        "B24_MAX_CARDINALITY_PLAN_SHARED_BUFFERS": B24_MAX_CARDINALITY_PLAN_SHARED_BUFFERS,
        "B24_MAX_CARDINALITY_PLAN_TEMP_BLOCKS": B24_MAX_CARDINALITY_PLAN_TEMP_BLOCKS,
        "B24_MAX_CARDINALITY_PLAN_SORT_NODES": B24_MAX_CARDINALITY_PLAN_SORT_NODES,
        "B24_MAX_CARDINALITY_PLAN_HASHAGGREGATE_NODES": B24_MAX_CARDINALITY_PLAN_HASHAGGREGATE_NODES,
        "B24_MAX_CARDINALITY_PLAN_SEQ_SCAN_NODES": B24_MAX_CARDINALITY_PLAN_SEQ_SCAN_NODES,
        "B24_MAX_CARDINALITY_PLAN_BITMAP_HEAP_SCAN_NODES": B24_MAX_CARDINALITY_PLAN_BITMAP_HEAP_SCAN_NODES,
        "B24_MAX_CARDINALITY_PLAN_EXECUTION_MS": B24_MAX_CARDINALITY_PLAN_EXECUTION_MS,
        "B24_MAX_CARDINALITY_PLAN_PLANNING_MS": B24_MAX_CARDINALITY_PLAN_PLANNING_MS,
        "B24_CARDINALITY_PLAN_WORK_MEM": B24_CARDINALITY_PLAN_WORK_MEM,
    }

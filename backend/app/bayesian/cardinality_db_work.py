"""B2.4-P4 cardinality DB-work budget validation.

The production P4 cardinality path uses cap-plus-one next-key probes rather
than exact distinct aggregation. This module defines the numeric plan budgets
used by tests and evidence review to reject plans that regress to full-slice
deduplication work.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.bayesian.resource_bounds import B24_RESOURCE_POLICY


@dataclass(frozen=True)
class CardinalityPlanEvidence:
    total_plan_rows: int
    shared_buffers_hit_or_read: int
    temp_blocks_read_or_written: int
    sort_nodes: int
    hashaggregate_nodes: int
    seq_scan_nodes: int
    bitmap_heap_scan_nodes: int
    execution_ms: float
    planning_ms: float
    work_mem: str
    explain_options: str


class CardinalityDBWorkBudgetError(ValueError):
    pass


def validate_cardinality_plan_evidence(evidence: CardinalityPlanEvidence) -> None:
    """Fail plans that exceed the B2.4-P4 bounded cardinality work envelope."""

    policy = B24_RESOURCE_POLICY
    required_explain_options = ("ANALYZE", "BUFFERS", "VERBOSE", "SETTINGS")
    missing_options = [
        option
        for option in required_explain_options
        if option not in evidence.explain_options.upper()
    ]
    if missing_options:
        raise CardinalityDBWorkBudgetError(
            f"cardinality EXPLAIN proof missing options: {', '.join(missing_options)}"
        )
    if evidence.work_mem != policy.cardinality_plan_work_mem:
        raise CardinalityDBWorkBudgetError(
            f"cardinality proof must run with work_mem={policy.cardinality_plan_work_mem}"
        )
    checks = (
        ("rows", evidence.total_plan_rows, policy.max_cardinality_plan_rows),
        (
            "shared_buffers",
            evidence.shared_buffers_hit_or_read,
            policy.max_cardinality_plan_shared_buffers,
        ),
        (
            "temp_blocks",
            evidence.temp_blocks_read_or_written,
            policy.max_cardinality_plan_temp_blocks,
        ),
        ("sort_nodes", evidence.sort_nodes, policy.max_cardinality_plan_sort_nodes),
        (
            "hashaggregate_nodes",
            evidence.hashaggregate_nodes,
            policy.max_cardinality_plan_hashaggregate_nodes,
        ),
        (
            "seq_scan_nodes",
            evidence.seq_scan_nodes,
            policy.max_cardinality_plan_seq_scan_nodes,
        ),
        (
            "bitmap_heap_scan_nodes",
            evidence.bitmap_heap_scan_nodes,
            policy.max_cardinality_plan_bitmap_heap_scan_nodes,
        ),
        (
            "execution_ms",
            evidence.execution_ms,
            policy.max_cardinality_plan_execution_ms,
        ),
        ("planning_ms", evidence.planning_ms, policy.max_cardinality_plan_planning_ms),
    )
    for label, observed, limit in checks:
        if observed > limit:
            raise CardinalityDBWorkBudgetError(
                f"cardinality plan exceeds {label} budget: {observed} > {limit}"
            )

"""
Prometheus metrics label policy for B0.5.6.3 cardinality/privacy enforcement.

This module is the single source of truth for allowed metric labels.
All label values MUST be bounded (finite closed sets) to prevent cardinality explosion.

Prohibited labels:
- tenant_id (privacy + unbounded cardinality)
- Any UUID-like values
- Any user-supplied strings without normalization

The computed series budget is protected by CI tests.
"""
from __future__ import annotations

from typing import Optional

from app.core.queues import ALLOWED_QUEUES


# =============================================================================
# Allowed Label Keys
# =============================================================================

# Only these label keys are permitted on application metrics.
# Prometheus internals (le, quantile, etc.) are excluded from enforcement.
ALLOWED_LABEL_KEYS: frozenset[str] = frozenset({
    "queue",
    "state",
    "task_name",
    "outcome",
    "view_name",
})


# =============================================================================
# Allowed Outcome Values
# =============================================================================

# Bounded set of task/operation outcomes.
# All instrumentation must map to one of these values.
OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"
OUTCOME_RETRY = "retry"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_REJECTED = "rejected"
OUTCOME_SKIPPED = "skipped"

ALLOWED_OUTCOMES: frozenset[str] = frozenset({
    OUTCOME_SUCCESS,
    OUTCOME_FAILURE,
    OUTCOME_RETRY,
    OUTCOME_TIMEOUT,
    OUTCOME_REJECTED,
    OUTCOME_SKIPPED,
})


# =============================================================================
# Allowed Queue State Values (B0.5.6.4)
# =============================================================================

QUEUE_STATE_VISIBLE = "visible"
QUEUE_STATE_INVISIBLE = "invisible"
QUEUE_STATE_TOTAL = "total"

ALLOWED_QUEUE_STATES: frozenset[str] = frozenset({
    QUEUE_STATE_VISIBLE,
    QUEUE_STATE_INVISIBLE,
    QUEUE_STATE_TOTAL,
})


# =============================================================================
# Allowed Task Names
# =============================================================================

# Explicit allowlist of Celery task names.
# Derived from app/tasks/*.py @celery_app.task(name=...) definitions.
ALLOWED_TASK_NAMES: frozenset[str] = frozenset({
    # health
    "app.tasks.health.probe",
    # housekeeping
    "app.tasks.housekeeping.ping",
    # llm
    "app.tasks.llm.route",
    "app.tasks.llm.explanation",
    "app.tasks.llm.investigation",
    "app.tasks.llm.budget_optimization",
    # matviews
    "app.tasks.matviews.refresh_single",
    "app.tasks.matviews.refresh_all_for_tenant",
    "app.tasks.matviews.pulse_matviews_global",
    # maintenance
    "app.tasks.maintenance.refresh_all_matviews_global_legacy",
    "app.tasks.maintenance.refresh_matview_for_tenant",
    "app.tasks.maintenance.scan_for_pii_contamination",
    "app.tasks.maintenance.enforce_data_retention",
    # attribution
    "app.tasks.attribution.recompute_window",
    # r4_failure_semantics
    "app.tasks.r4_failure_semantics.poison_pill",
    "app.tasks.r4_failure_semantics.crash_after_write_pre_ack",
    "app.tasks.r4_failure_semantics.rls_cross_tenant_probe",
    "app.tasks.r4_failure_semantics.runaway_sleep",
    "app.tasks.r4_failure_semantics.sentinel_side_effect",
    "app.tasks.r4_failure_semantics.privilege_probes",
    # r6_resource_governance
    "app.tasks.r6_resource_governance.runtime_snapshot",
    "app.tasks.r6_resource_governance.timeout_probe",
    "app.tasks.r6_resource_governance.retry_probe",
    "app.tasks.r6_resource_governance.prefetch_short_task",
    "app.tasks.r6_resource_governance.prefetch_long_task",
    "app.tasks.r6_resource_governance.pid_probe",
})


# =============================================================================
# Allowed View Names
# =============================================================================

# Materialized view names from app/matviews/registry.py.
ALLOWED_VIEW_NAMES: frozenset[str] = frozenset({
    "mv_allocation_summary",
    "mv_channel_performance",
    "mv_daily_revenue_summary",
    "mv_realtime_revenue",
    "mv_reconciliation_status",
})


# =============================================================================
# Normalization Helpers
# =============================================================================

def normalize_outcome(raw: Optional[str]) -> str:
    """
    Normalize an outcome string to a bounded value.
    
    Returns the raw value if it's in ALLOWED_OUTCOMES, otherwise 'failure'.
    """
    if raw and raw in ALLOWED_OUTCOMES:
        return raw
    return OUTCOME_FAILURE


def normalize_task_name(raw: Optional[str]) -> str:
    """
    Normalize a task name to a bounded value.
    
    Returns the raw value if it's in ALLOWED_TASK_NAMES, otherwise 'unknown'.
    """
    if raw and raw in ALLOWED_TASK_NAMES:
        return raw
    return "unknown"


def normalize_queue(raw: Optional[str]) -> str:
    """
    Normalize a queue name to a bounded value.
    
    Returns the raw value if it's in ALLOWED_QUEUES, otherwise 'unknown'.
    """
    if raw and raw in ALLOWED_QUEUES:
        return raw
    return "unknown"


def normalize_queue_state(raw: Optional[str]) -> str:
    """
    Normalize a queue state to a bounded value.

    Returns the raw value if it's in ALLOWED_QUEUE_STATES, otherwise 'total'.
    """
    if raw and raw in ALLOWED_QUEUE_STATES:
        return raw
    return QUEUE_STATE_TOTAL


def normalize_view_name(raw: Optional[str]) -> str:
    """
    Normalize a materialized view name to a bounded value.
    
    Returns the raw value if it's in ALLOWED_VIEW_NAMES, otherwise 'unknown'.
    """
    if raw and raw in ALLOWED_VIEW_NAMES:
        return raw
    return "unknown"


# =============================================================================
# Series Budget Calculation
# =============================================================================

def compute_series_budget() -> dict[str, int | dict[str, int]]:
    """
    Compute the worst-case series budget based on closed-set dimensions.
    
    Returns a dict with:
    - dimension_sizes: size of each label dimension
    - metric_families: estimated series per metric family
    - total_upper_bound: sum of all metric family budgets
    """
    dim_queues = len(ALLOWED_QUEUES) + 1  # +1 for 'unknown'
    dim_queue_states = len(ALLOWED_QUEUE_STATES)
    dim_task_names = len(ALLOWED_TASK_NAMES) + 1  # +1 for 'unknown'
    dim_outcomes = len(ALLOWED_OUTCOMES)
    dim_view_names = len(ALLOWED_VIEW_NAMES) + 1  # +1 for 'unknown'
    
    # Metric families and their label dimensions:
    # - events_* metrics: no labels (aggregate only, tenant_id removed)
    # - celery_task_* metrics: task_name only
    # - matview_refresh_* metrics: view_name, outcome
    # - celery_queue_* metrics: queue,state and queue
    
    events_series = 1  # No labels after B0.5.6.3
    celery_task_series = dim_task_names  # task_name only
    matview_series = dim_view_names * dim_outcomes  # view_name × outcome
    celery_queue_messages_series = dim_queues * dim_queue_states  # queue × state
    celery_queue_max_age_series = dim_queues  # queue
    celery_queue_ops_series = 1  # no labels
    
    # Number of metric families per category (counters + histograms)
    # Events: 4 families (ingested, duplicate, dlq, duration)
    # Celery: 4 families (started, success, failure, duration)
    # Matview: 3 families (total, duration, failures)
    
    events_total = 4 * events_series
    celery_total = 4 * celery_task_series
    matview_total = 3 * matview_series
    celery_queue_total = (
        1 * celery_queue_messages_series
        + 1 * celery_queue_max_age_series
        + 2 * celery_queue_ops_series
    )
    
    return {
        "dimension_sizes": {
            "queues": dim_queues,
            "queue_states": dim_queue_states,
            "task_names": dim_task_names,
            "outcomes": dim_outcomes,
            "view_names": dim_view_names,
        },
        "metric_families": {
            "events": events_total,
            "celery_task": celery_total,
            "matview_refresh": matview_total,
            "celery_queue": celery_queue_total,
        },
        "total_upper_bound": events_total + celery_total + matview_total + celery_queue_total,
    }


# Series budget threshold (conservative limit for alerting).
# This bound is validated in CI via compute_series_budget().
# Adding headroom: 500 series max.
SERIES_BUDGET_THRESHOLD = 500

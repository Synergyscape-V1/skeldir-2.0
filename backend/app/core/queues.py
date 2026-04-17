"""
Queue name constants to keep routing deterministic and centralized.

B0.5.6.3: All queue names are defined here as the single source of truth.
This enables bounded cardinality enforcement in Prometheus metrics.
"""

# Core queue definitions (must match celery_app.py task_queues)
QUEUE_HOUSEKEEPING = "housekeeping"
QUEUE_MAINTENANCE = "maintenance"
QUEUE_LLM = "llm"
QUEUE_ATTRIBUTION = "attribution"
QUEUE_BAYESIAN = "bayesian"

# Frozen set of all allowed queues for metrics policy enforcement
ALLOWED_QUEUES: frozenset[str] = frozenset({
    QUEUE_HOUSEKEEPING,
    QUEUE_MAINTENANCE,
    QUEUE_LLM,
    QUEUE_ATTRIBUTION,
    QUEUE_BAYESIAN,
})

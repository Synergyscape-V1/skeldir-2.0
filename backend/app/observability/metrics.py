from prometheus_client import Counter, Histogram

EVENT_LABELS = ["tenant_id", "vendor", "event_type", "error_type"]

events_ingested_total = Counter(
    "events_ingested_total",
    "Total successfully ingested events",
    EVENT_LABELS,
)

events_duplicate_total = Counter(
    "events_duplicate_total",
    "Total duplicate events detected by idempotency",
    EVENT_LABELS,
)

events_dlq_total = Counter(
    "events_dlq_total",
    "Total events routed to DLQ",
    EVENT_LABELS,
)

ingestion_duration_seconds = Histogram(
    "ingestion_duration_seconds",
    "Ingestion duration per event",
    EVENT_LABELS,
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

celery_task_started_total = Counter(
    "celery_task_started_total",
    "Total Celery tasks started",
    ["task_name"],
)

celery_task_success_total = Counter(
    "celery_task_success_total",
    "Total Celery tasks succeeded",
    ["task_name"],
)

celery_task_failure_total = Counter(
    "celery_task_failure_total",
    "Total Celery tasks failed",
    ["task_name"],
)

celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds",
    "Duration of Celery tasks in seconds",
    ["task_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

matview_refresh_total = Counter(
    "matview_refresh_total",
    "Total materialized view refresh attempts",
    ["view_name", "outcome", "strategy"],
)

matview_refresh_duration_seconds = Histogram(
    "matview_refresh_duration_seconds",
    "Materialized view refresh duration in seconds",
    ["view_name", "outcome"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

matview_refresh_failures_total = Counter(
    "matview_refresh_failures_total",
    "Materialized view refresh failures",
    ["view_name", "error_type"],
)

# B056 — Worker Observability Grafana Dashboard (Template)

This folder contains an **opinionated Grafana dashboard JSON template** for B0.5.6 Phase 8.

## Invariants (non-negotiable)

- No per-tenant leakage: this dashboard **must not** query, template on, or expose a tenant identifier (directly or indirectly). Tenant identity belongs in **logs**, not metrics panels.
- No DB sink for telemetry: metrics are assumed **Prometheus-scraped**, not written to Postgres for observability.
- No worker HTTP sidecar: the worker does **not** host `/metrics`. Worker task metrics are exposed via the **dedicated exporter** process.

## Scrape topology (truth)

- **API metrics**: scraped from the API process `/metrics` (FastAPI route `GET /metrics`).
  - Includes: API ingestion counters/histograms and **broker-truth** queue gauges.
  - Excludes: `celery_task_*`, `matview_refresh_*`, `multiproc_*` families (guarded by API-side filtering).
- **Worker task metrics**: scraped from the dedicated exporter process `app.observability.worker_metrics_exporter` (`/metrics` only).
  - Exporter bind is controlled by env vars:
    - `WORKER_METRICS_EXPORTER_HOST` (default `127.0.0.1`)
    - `WORKER_METRICS_EXPORTER_PORT` (default `9108`)

## Dashboard variables

- `$datasource`: Prometheus datasource selector.
- `$api_job`: Prometheus scrape `job` for the API `/metrics` target.
- `$worker_job`: Prometheus scrape `job` for the worker metrics exporter target.
- `$queue`: queue selector (bounded, derived from `celery_queue_messages` label `queue`).
- `$task_name`: task selector (bounded allowlist; derived from `celery_task_*` label `task_name`).

## Metric families referenced by the dashboard

- Worker task metrics (exporter):
  - `celery_task_started_total`
  - `celery_task_success_total`
  - `celery_task_failure_total`
  - `celery_task_duration_seconds_bucket` (for p50/p90/p99 via `histogram_quantile`)
- Broker-truth queue backlog (API `/metrics`):
  - `celery_queue_messages` (labels: `queue`, `state`)
  - `celery_queue_max_age_seconds` (label: `queue`)

## Import

Grafana → **Dashboards** → **New** → **Import** → upload:

- `docs/ops/grafana/skeldir_b056_worker_observability_dashboard.json`

# B0.5.6 Phase 8 — Grafana Dashboard Template + Evidence Closure

**Date**: 2026-01-20  
**Phase**: B0.5.6.8  
**Status**: COMPLETE  
**Commit SHA**: 70c9240d1b762ddf0dbe2e21a8f8f4753a240bcf  
**CI Run (primary)**: https://github.com/Muk223/skeldir-2.0/actions/runs/21178399899  

---

## 1) Hypotheses (initially UNVALIDATED → empirically evaluated)

### H-C1 — Dashboard absence / non-authoritative location
**VALIDATED**: repo contains Grafana JSONs, but no canonical B056 worker dashboard template existed under `docs/ops/grafana/` prior to this phase.

### H-C2 — Metric-name mismatch risk
**MITIGATED**: dashboard queries reference metric names extracted from code (see Section 3).

### H-C3 — Split-brain scrape assumption risk
**MITIGATED**: dashboard assumes worker metrics are scraped from the dedicated exporter job (not from worker HTTP), and API `/metrics` is a separate scrape target.

### H-C4 — Privacy / cardinality amplification risk
**MITIGATED**: dashboard templates only on bounded low-cardinality labels (`queue`, `task_name`) and contains no tenant identifier references.

### H-C5 — Evidence closure incomplete
**RESOLVED**: evidence pack added + `docs/forensics/INDEX.md` updated with a Phase 8 row.

---

## 2) Deliverables (paths)

- Dashboard JSON: `docs/ops/grafana/skeldir_b056_worker_observability_dashboard.json`
- Import/scope README: `docs/ops/grafana/README_b056_worker_observability.md`

---

## 3) Exit Gate Evidence (verbatim command outputs)

### EG8.1 — Dashboard JSON valid + coverage

#### 3.1 File existence (tracked)

```powershell
git ls-files | rg skeldir_b056_worker_observability_dashboard.json
```

```text
docs/ops/grafana/skeldir_b056_worker_observability_dashboard.json
```

#### 3.2 JSON validity

```powershell
cmd /c "python -m json.tool docs\\ops\\grafana\\skeldir_b056_worker_observability_dashboard.json > NUL"
echo "json_tool_exit=$LASTEXITCODE"
```

```text
json_tool_exit=0
```

```powershell
python -c "import json; json.load(open('docs/ops/grafana/skeldir_b056_worker_observability_dashboard.json','r',encoding='utf-8')); print('OK')"
```

```text
OK
```

#### 3.3 Required rows/panels present (titles + required `up{job=~...}` panels)

```powershell
rg -n "Row A — Worker Health of Observability|Row B — Throughput|Row C — Error Rate|Row D — Latency|Row E — Backlog" docs/ops/grafana/skeldir_b056_worker_observability_dashboard.json
```

```text
90:        "title": "Row A — Worker Health of Observability",
123:        "title": "Row B — Throughput",
169:        "title": "Row C — Error Rate",
193:        "title": "Row D — Latency",
242:        "title": "Row E — Backlog (Broker Truth)",
```

```powershell
rg -n 'up\\{job=~' docs/ops/grafana/skeldir_b056_worker_observability_dashboard.json
```

```text
102:            "expr": "up{job=~\"$worker_job\"}",
115:            "expr": "up{job=~\"$api_job\"}",
```

#### 3.4 Metric-name cross-check (dashboard ↔ code)

**Dashboard metric strings**:

```powershell
rg -n "celery_|events_ingested" docs/ops/grafana -g "*.json"
```

```text
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:59:          "query": "label_values(celery_queue_messages{job=~\"$api_job\"}, queue)",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:60:          "definition": "label_values(celery_queue_messages{job=~\"$api_job\"}, queue)",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:74:          "query": "label_values(celery_task_started_total{job=~\"$worker_job\"}, task_name)",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:75:          "definition": "label_values(celery_task_started_total{job=~\"$worker_job\"}, task_name)",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:135:            "expr": "sum by (task_name) (rate(celery_task_started_total{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m]))",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:148:            "expr": "sum by (task_name) (rate(celery_task_success_total{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m]))",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:161:            "expr": "sum by (task_name) (rate(celery_task_failure_total{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m]))",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:185:            "expr": "100 * (sum(rate(celery_task_failure_total{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m])) / clamp_min(sum(rate(celery_task_started_total{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m])), 1e-9))",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:206:            "expr": "histogram_quantile(0.50, sum by (le) (rate(celery_task_duration_seconds_bucket{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m])))",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:220:            "expr": "histogram_quantile(0.90, sum by (le) (rate(celery_task_duration_seconds_bucket{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m])))",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:234:            "expr": "histogram_quantile(0.99, sum by (le) (rate(celery_task_duration_seconds_bucket{job=~\"$worker_job\",task_name=~\"$task_name\"}[5m])))",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:254:            "expr": "sum by (queue) (celery_queue_messages{job=~\"$api_job\",queue=~\"$queue\",state=\"visible\"})",
docs/ops/grafana\skeldir_b056_worker_observability_dashboard.json:268:            "expr": "max by (queue) (celery_queue_max_age_seconds{job=~\"$api_job\",queue=~\"$queue\"})",
```

**Code metric inventory (definitions)**:

```powershell
rg -n "Counter\\(|Histogram\\(|Gauge\\(" backend/app | rg -n "observability"
```

```text
1:backend/app\observability\api_metrics.py:16:events_ingested_total = Counter(
2:backend/app\observability\api_metrics.py:21:events_duplicate_total = Counter(
3:backend/app\observability\api_metrics.py:26:events_dlq_total = Counter(
4:backend/app\observability\api_metrics.py:31:ingestion_duration_seconds = Histogram(
5:backend/app\observability\metrics.py:37:celery_task_started_total = Counter(
6:backend/app\observability\metrics.py:43:celery_task_success_total = Counter(
7:backend/app\observability\metrics.py:49:celery_task_failure_total = Counter(
8:backend/app\observability\metrics.py:55:celery_task_duration_seconds = Histogram(
9:backend/app\observability\metrics.py:69:matview_refresh_total = Counter(
10:backend/app\observability\metrics.py:75:matview_refresh_duration_seconds = Histogram(
11:backend/app\observability\metrics.py:82:matview_refresh_failures_total = Counter(
12:backend/app\observability\metrics.py:94:multiproc_orphan_files_detected = Counter(
13:backend/app\observability\metrics.py:99:multiproc_pruned_files_total = Counter(
14:backend/app\observability\metrics.py:104:multiproc_dir_overflow_total = Counter(
```

**Code metric inventory (B0.5.6 queue gauges; broker truth)**:

```powershell
rg -n "BROKER_QUEUE_MESSAGES_METRIC|BROKER_QUEUE_MAX_AGE_METRIC|celery_queue_messages|celery_queue_max_age_seconds" backend/app/observability/broker_queue_stats.py backend/app/observability/metrics_policy.py
```

```text
backend/app/observability/metrics_policy.py:220:    celery_queue_messages_series = dim_queues * dim_queue_states  # queue × state
backend/app/observability/metrics_policy.py:235:        1 * celery_queue_messages_series
backend/app/observability/broker_queue_stats.py:95:BROKER_QUEUE_MESSAGES_METRIC = "celery_queue_messages"
backend/app/observability/broker_queue_stats.py:96:BROKER_QUEUE_MAX_AGE_METRIC = "celery_queue_max_age_seconds"
backend/app/observability/broker_queue_stats.py:240:            BROKER_QUEUE_MESSAGES_METRIC,
backend/app/observability/broker_queue_stats.py:259:            BROKER_QUEUE_MAX_AGE_METRIC,
```

#### 3.5 Privacy proof (no tenant identifier usage in dashboard JSON/README)

```powershell
rg -n "tenant_id" docs/ops/grafana -g "*.json" -g "*.md"
echo "rg_exit=$LASTEXITCODE"
```

```text
rg_exit=1
```

---

### EG8.2 — Evidence pack contains proofs for every exit gate

This document includes verbatim command outputs for:

- JSON validity (Section 3.2)
- Row/panel coverage (Section 3.3)
- Metric-name cross-check (Section 3.4)
- Privacy grep (Section 3.5)

Remaining fill-ins required for closure (after push):

- None.

CI status for `70c9240d1b762ddf0dbe2e21a8f8f4753a240bcf`:

```text
 databaseId workflowName                                status    conclusion url                                                           
 ---------- ------------                                ------    ---------- ---                                                           
21178399832 B0.5.4.1 View Registry Gates                completed success    https://github.com/Muk223/skeldir-2.0/actions/runs/21178399832
21178399807 B0.5.4.2 Refresh Executor Gates             completed success    https://github.com/Muk223/skeldir-2.0/actions/runs/21178399807
21178399822 B0.5.4.3 Matview Task Layer Gates           completed success    https://github.com/Muk223/skeldir-2.0/actions/runs/21178399822
21178399899 CI                                          completed success    https://github.com/Muk223/skeldir-2.0/actions/runs/21178399899
21178399867 Empirical Validation - Directive Compliance completed success    https://github.com/Muk223/skeldir-2.0/actions/runs/21178399867
```

---

### EG8.3 — INDEX updated (canonical convention)

```powershell
rg -n "b056_phase8_.*evidence\\.md" docs/forensics/INDEX.md
```

```text
34:| B0.5.6 Phase 8 | docs/forensics/b056_phase8_grafana_dashboard_template_evidence.md | Grafana dashboard template (worker throughput/error/latency + broker-truth backlog) + evidence closure | 70c9240 | https://github.com/Muk223/skeldir-2.0/actions/runs/21178399899 |
```

---

## 4) Topology truth alignment (dashboard ↔ scrape surfaces)

API `/metrics` filters out worker task metric families, and worker task metrics are exposed via the dedicated exporter:

```powershell
rg -n "/metrics|excluded_prefixes|worker_metrics_exporter" backend/app/api/health.py
```

```text
341:    B0.5.6.7: No split-brain. API `/metrics` must not aggregate from
350:    # configuring Celery), API `/metrics` must not expose worker task metrics.
353:    excluded_prefixes = (
362:                if metric.name.startswith(excluded_prefixes):
371:@router.get("/metrics")
376:    B0.5.6.7: API `/metrics` exposes API metrics + broker-truth queue gauges only.
377:    Worker task metrics are exposed via `app.observability.worker_metrics_exporter`.
```

Exporter bind + `/metrics` surface:

```powershell
rg -n "WORKER_METRICS_EXPORTER_HOST|WORKER_METRICS_EXPORTER_PORT|make_server|PROMETHEUS_MULTIPROC_DIR|/metrics" backend/app/observability/worker_metrics_exporter.py backend/app/observability/metrics_runtime_config.py
```

```text
backend/app/observability/worker_metrics_exporter.py:6:- Exporter is strictly read-only w.r.t. PROMETHEUS_MULTIPROC_DIR (no wipes/deletes).
backend/app/observability/worker_metrics_exporter.py:13:from wsgiref.simple_server import WSGIRequestHandler, make_server
backend/app/observability/worker_metrics_exporter.py:26:    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(multiproc_dir)
backend/app/observability/worker_metrics_exporter.py:33:        if path != "/metrics":
backend/app/observability/worker_metrics_exporter.py:51:    httpd = make_server(bind.host, bind.port, _build_wsgi_app(), handler_class=_NoLoggingHandler)
backend/app/observability/metrics_runtime_config.py:6:- Provides a single authority for PROMETHEUS_MULTIPROC_DIR and exporter bind config.
backend/app/observability/metrics_runtime_config.py:19:    "B0.5.6.5: PROMETHEUS_MULTIPROC_DIR must be an absolute path to an existing, "
backend/app/observability/metrics_runtime_config.py:46:    raw = _get_env("PROMETHEUS_MULTIPROC_DIR")
backend/app/observability/metrics_runtime_config.py:75:    host = _get_env("WORKER_METRICS_EXPORTER_HOST") or "127.0.0.1"
backend/app/observability/metrics_runtime_config.py:76:    port = _get_int_env("WORKER_METRICS_EXPORTER_PORT", 9108)
```

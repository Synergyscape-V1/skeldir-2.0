# B0.5.7-P1 - Canonical E2E Bring-Up Remediation Evidence (Docker Compose)

## Scope / non-negotiables

- Deliver **repo-native**, **one-command** bring-up matching current **monolith** topology (no legacy microservice resurrection).
- Preserve B0.5.6.7: **truthful scrape targets** (API `/metrics` excludes worker task metrics; exporter `/metrics` includes them).
- Evidence-only in this pack: commands, outputs, and runtime observations.

---

## Repo anchors (code-defined authority)

Timestamp (local): `2026-01-20T14:06:41-06:00`

- Branch (work): `b057-p1-canonical-e2e-bringup`
- Pre-remediation anchor (this branch, before P1 changes): `0a31d08e18acc97c630b0a97d65b3664837d2ce4`
- Remediation implementation commit (compose + scripts + runbook): `9dd08fa461301b6daa192fc48d664ffe303c7dfc`
- PR head SHA (CI-validated): `da19f564d32c93b0529d171bad89aa9dc39aa5a8`
- `main` at time of work (per branch history): `f083d23` (`b056: phase8 ledger closure`)

Commands:

```powershell
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git log -5 --oneline
```

Output (trimmed):

```text
b057-p1-canonical-e2e-bringup
0a31d08e18acc97c630b0a97d65b3664837d2ce4
0a31d08 docs: add B0.5.7 context gathering evidence
f083d23 b056: phase8 ledger closure
732233c b056: phase8 evidence finalize
70c9240 b056: phase8 grafana dashboard + evidence closure
676ee30 B0567: update Phase 7 evidence for EG7.4
```

---

## Local environment facts (runtime authority)

Commands:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber | Format-List
python --version
docker --version
docker compose version
```

Output:

```text
Caption     : Microsoft Windows 11 Pro
Version     : 10.0.26100
BuildNumber : 26100
Python 3.11.9
Docker version 28.5.1, build e180ab8
Docker Compose version v2.40.0-desktop.1
```

---

## Mandatory investigation (validate/refute before remediation)

### H-P1-R1 (compose drift: legacy microservice paths) - TRUE

Command:

```powershell
rg -n "dockerfile:" docker-compose.component-dev.yml
```

Output:

```text
30:      dockerfile: backend/app/ingestion/Dockerfile
52:      dockerfile: backend/app/attribution/Dockerfile
74:      dockerfile: backend/app/auth/Dockerfile
98:      dockerfile: backend/app/webhooks/Dockerfile
```

### H-P1-R2 (no active Dockerfile outside archive at pre-remediation anchor) - TRUE

Command (tree listing at the pre-remediation anchor):

```powershell
git ls-tree -r --name-only 0a31d08e18acc97c630b0a97d65b3664837d2ce4 | rg -i "(^|/)Dockerfile(\\.|$)"
```

Output:

```text
docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.attribution
docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.auth
docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.ingestion
docs/forensics/archive/docker_tools/legacy_microservices/Dockerfile.webhooks
```

### H-P1-D1 (component-dev compose is nonfunctional on main) - TRUE

Command:

```powershell
docker compose -f docker-compose.component-dev.yml config
docker compose -f docker-compose.component-dev.yml build
```

Output (trimmed):

```text
resolve : CreateFile C:\Users\ayewhy\II SKELDIR II\backend\app\attribution: The system cannot find the file specified.
```

---

## Remediation artifacts (repo-native canonical bring-up)

Added:

- `.dockerignore`
- `backend/Dockerfile`
- `docker-compose.e2e.yml`
- `scripts/e2e/up.ps1`
- `scripts/e2e/down.ps1`
- `docs/runbooks/B0.5.7_P1_CANONICAL_E2E_BRINGUP.md`

---

## Canonical E2E compose: topology + invariants

Topology (docker-compose.e2e.yml):

- `db`: Postgres 16 (persistence + Celery broker + Celery result backend; Postgres-only)
- `migrate`: one-shot (role bootstrap + `alembic upgrade heads`)
- `api`: FastAPI (health + `/metrics` broker-truth only)
- `worker`: Celery worker (no HTTP listener)
- `exporter`: worker metrics exporter (binds `0.0.0.0:9108`, serves `/metrics`)

UTF-8 stability guarantee:

```text
POSTGRES_INITDB_ARGS: "--encoding=UTF8 --lc-collate=C --lc-ctype=C"
```

Runtime proof:

```powershell
docker compose -f docker-compose.e2e.yml exec -T db psql -U postgres -d skeldir_e2e -c "SHOW server_encoding;"
docker compose -f docker-compose.e2e.yml exec -T db psql -U postgres -d skeldir_e2e -c "SELECT version();"
```

Output:

```text
server_encoding
UTF8

PostgreSQL 16.11 (Debian 16.11-1.pgdg13+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit
```

---

## Gates (EG-P1.*) - evidence

### EG-P1.1 - Compose integrity (config + build)

Commands:

```powershell
docker compose -f docker-compose.e2e.yml config
docker compose -f docker-compose.e2e.yml build
```

Observed:

- `docker compose -f docker-compose.e2e.yml config` exits `0`
- `docker compose -f docker-compose.e2e.yml build` exits `0`

### EG-P1.2 - Topology bring-up

Commands:

```powershell
docker compose -f docker-compose.e2e.yml down -v
docker compose -f docker-compose.e2e.yml up -d
docker compose -f docker-compose.e2e.yml ps -a
```

Output (`docker compose ps -a`):

```text
NAME                     SERVICE    STATUS                     PORTS
skeldir-e2e-api-1         api        Up 2 hours (healthy)        0.0.0.0:18000->8000/tcp, [::]:18000->8000/tcp
skeldir-e2e-db-1          db         Up 2 hours (healthy)        0.0.0.0:15432->5432/tcp, [::]:15432->5432/tcp
skeldir-e2e-exporter-1    exporter   Up 2 hours (healthy)        0.0.0.0:9108->9108/tcp, [::]:9108->9108/tcp
skeldir-e2e-migrate-1     migrate    Exited (0) 18 seconds ago
skeldir-e2e-worker-1      worker     Up 2 hours
```

### EG-P1.3 - Health truth gate

Commands:

```powershell
curl.exe -sS -i http://127.0.0.1:18000/health/live
curl.exe -sS -i http://127.0.0.1:18000/health/ready
curl.exe -sS -i http://127.0.0.1:18000/health/worker
```

Output (trimmed):

```text
HTTP/1.1 200 OK
{"status":"ok"}

HTTP/1.1 200 OK
{"status":"ok","database":"ok","rls":"ok","tenant_guc":"ok"}

HTTP/1.1 200 OK
{"status":"ok","broker":"ok","database":"ok","worker":"ok","probe_latency_ms":707,"cached":false,"cache_scope":"process"}
```

### EG-P1.4 - Scrape target truth gate (anti split-brain)

API `/metrics` shows broker-truth queue gauges and excludes worker task metrics:

```powershell
$apiMetrics = curl.exe -sS http://127.0.0.1:18000/metrics
($apiMetrics | Select-String -Pattern 'celery_queue_' | Select-Object -First 8) -join \"`n\"
@($apiMetrics | Select-String -Pattern 'celery_task_').Count
```

Output (trimmed):

```text
# HELP celery_queue_messages Celery queue depth derived from kombu tables (broker truth)
# TYPE celery_queue_messages gauge
celery_queue_messages{queue="attribution",state="visible"} 0.0
celery_queue_messages{queue="attribution",state="invisible"} 0.0
celery_queue_messages{queue="attribution",state="total"} 0.0
celery_queue_messages{queue="housekeeping",state="visible"} 0.0
celery_queue_messages{queue="housekeeping",state="invisible"} 4.0
celery_queue_messages{queue="housekeeping",state="total"} 4.0
0
```

Exporter `/metrics` shows worker task metrics and (after a refresh task) `matview_refresh_*`:

```powershell
$expMetrics = curl.exe -sS http://127.0.0.1:9108/metrics
($expMetrics | Select-String -Pattern 'celery_task_' | Select-Object -First 6) -join \"`n\"
($expMetrics | Select-String -Pattern 'matview_refresh_' | Select-Object -First 10) -join \"`n\"
```

Output (trimmed):

```text
# HELP celery_task_started_total Total Celery tasks started
# TYPE celery_task_started_total counter
celery_task_started_total{task_name="app.tasks.matviews.refresh_single"} 3.0
celery_task_started_total{task_name="app.tasks.health.probe"} 10.0
# HELP celery_task_success_total Total Celery tasks succeeded
# TYPE celery_task_success_total counter

# HELP matview_refresh_total Total materialized view refresh attempts
# TYPE matview_refresh_total counter
matview_refresh_total{outcome="success",view_name="mv_realtime_revenue"} 3.0
```

How `matview_refresh_*` was forced to exist (task invocation):

```powershell
docker compose -f docker-compose.e2e.yml exec -T db psql -U postgres -d skeldir_e2e -v ON_ERROR_STOP=1 -c `
  "INSERT INTO tenants (name, api_key_hash, notification_email) VALUES ('e2e-tenant', 'e2e_hash_1', 'noreply@example.invalid') RETURNING id;"

docker compose -f docker-compose.e2e.yml exec -T api python -c "import uuid; from app.celery_app import celery_app; cid=str(uuid.uuid4()); r=celery_app.send_task('app.tasks.matviews.refresh_single', queue='maintenance', kwargs={'tenant_id': 'e6ea7765-0622-4670-a69c-4b2956f0b3b9', 'view_name': 'mv_realtime_revenue', 'correlation_id': cid, 'force': True}); print(r.get(timeout=120))"
```

### EG-P1.5 - Regression guard gate (B0.5.6.7)

Test run used the compose Postgres (`127.0.0.1:15432`) as broker+results+persistence (Postgres-only).

Command:

```powershell
cd backend
$env:DATABASE_URL='postgresql+asyncpg://app_user:app_user@127.0.0.1:15432/skeldir_e2e'
$env:CELERY_BROKER_URL='sqla+postgresql://app_user:app_user@127.0.0.1:15432/skeldir_e2e'
$env:CELERY_RESULT_BACKEND='db+postgresql://app_user:app_user@127.0.0.1:15432/skeldir_e2e'
python -m pytest -vv tests/test_b0567_integration_truthful_scrape_targets.py
```

Output (trimmed):

```text
============================= test session starts =============================
tests\test_b0567_integration_truthful_scrape_targets.py::test_t71_task_metrics_delta_on_exporter PASSED [ 20%]
tests\test_b0567_integration_truthful_scrape_targets.py::test_t72_api_queue_gauges_match_broker_truth PASSED [ 40%]
tests\test_b0567_integration_truthful_scrape_targets.py::test_t73_api_metrics_do_not_include_worker_task_metrics PASSED [ 60%]
tests\test_b0567_integration_truthful_scrape_targets.py::test_t74_forbidden_labels_absent_on_both_scrape_surfaces PASSED [ 80%]
tests\test_b0567_integration_truthful_scrape_targets.py::test_t75_health_semantics_live_ready_worker_capability PASSED [100%]
============================= 5 passed in 12.13s ==============================
```

---

## Port collision handling (Windows)

Observed on this machine: an unrelated local listener on `127.0.0.1:8000` caused host traffic to miss the compose-mapped API.

Remediation in harness defaults:

- API host port defaulted to `18000` (`SKELDIR_API_PORT`)
- DB host port defaulted to `15432` (`SKELDIR_DB_PORT`)
- Exporter remains host `9108` by default (`SKELDIR_EXPORTER_PORT`)

---

## PR / push gate (EG-P1.7)

Branch push + PR:

- Branch push: `origin/b057-p1-canonical-e2e-bringup`
- PR URL: https://github.com/Muk223/skeldir-2.0/pull/24
- CI run (compose topology validation): https://github.com/Muk223/skeldir-2.0/actions/runs/21189584586
- CI run (main CI): https://github.com/Muk223/skeldir-2.0/actions/runs/21189584540

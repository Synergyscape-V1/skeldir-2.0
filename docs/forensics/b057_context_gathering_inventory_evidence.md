# B0.5.7 — Context Gathering Inventory Evidence (Static + Runtime)

**Objective**: Forensic inventory of Skeldir’s current backend system state, grounded in **`main` branch repo truth + observed runtime behavior**. Docs/specs are treated as hypotheses unless validated by code/runtime/CI config.

**Collected (local)**: `2026-01-20T12:19:22.7890936-06:00` (see command transcript sections for additional timestamps)

---

## G0 — Ground Truth Anchors

### Git anchors (start-of-run)

Commands:
```powershell
cd "c:\Users\ayewhy\II SKELDIR II"
git status --porcelain=v1
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git pull
```

Key outputs:
```text
(git status --porcelain=v1):  (empty)  # clean at start
branch: main
HEAD: f083d23e214e84729d4121ac6b4620cd68ad0dfd
git pull: Already up to date.
```

### Local environment facts

Commands:
```powershell
Get-ComputerInfo -Property WindowsProductName,WindowsVersion,OsBuildNumber | Format-List
python --version
docker --version
docker compose version
psql --version
```

Key outputs:
```text
WindowsProductName : Windows 10 Pro
WindowsVersion     : 2009
OsBuildNumber      : 26100

Python 3.11.9
Docker version 28.5.1, build e180ab8
Docker Compose version v2.40.0-desktop.1
psql (PostgreSQL) 18.0
```

Docker runtime status (local):
```powershell
Get-Service com.docker.service | Format-List Status,Name,StartType
docker ps
```

Key outputs:
```text
Status    : Stopped
Name      : com.docker.service
StartType : Manual

docker ps:
error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.51/containers/json": open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

**Runtime implication**: Docker-based harness startup is **not locally available** in this run; Postgres runtime was provisioned via local `postgres` binaries.

---

## PASS 1 — Static Analysis (Repo Forensics)

### Repo root inventory (selected)

Command:
```powershell
Get-ChildItem -Force -Name | Sort-Object
```

Key observed entries (non-exhaustive):
```text
.github
AGENTS.md
alembic
alembic.ini
backend
db
docker-compose.component-dev.yml
docker-compose.mock.yml
docker-compose.yml.deprecated
docs
Makefile
Procfile
scripts
tests
```

### Forensics ledger + prior evidence packs (B0.5.6 presence)

Commands:
```powershell
Get-ChildItem docs/forensics -Force -Name | Sort-Object
type docs\forensics\INDEX.md
```

Key observations:
- `docs/forensics/INDEX.md` exists and enumerates multiple B0.5.6 evidence packs (Phase 0–8).
- B0.5.6 “closure” is represented as a ledger row: `B0.5.6 Phase 8 ... evidence closure` in `docs/forensics/INDEX.md`.

### B0.5.7/B057 pre-existence scan

Command:
```powershell
rg -n "B0\.5\.7|b057" -S --glob "!node_modules/**" --glob "!frontend/nul" .
```

Observed result: **no matches** (exit code 1).

### CI topology snapshot (selected workflows)

Key files:
- `.github/workflows/ci.yml`: main CI, includes `pytest` execution of worker/metrics/privacy gate tests.
- `.github/workflows/r3-ingestion-under-fire.yml`: CI runtime harness for webhook ingestion load + DB truth verification (Postgres service).
- `.github/workflows/r4-worker-failure-semantics.yml`: CI runtime harness for worker crash semantics (Postgres-only broker/backend).
- `.github/workflows/r5-context-gathering.yml`: CI “context gathering” probes (Postgres service).
- `.github/workflows/empirical-validation.yml`: provisions **Postgres + Redis** service containers (note: Redis referenced here; see H-C1 notes).

Evidence (CI executes key pytest gates):
```powershell
rg -n "pytest" .github\workflows\ci.yml
```

Output (selected lines):
```text
391: pytest tests/test_llm_payload_contract.py -q
620: tests/test_b0564_queue_depth_max_age_broker_truth.py -q ...
742: pytest -vv tests/test_b0567_integration_truthful_scrape_targets.py
```

### Orchestration/harness artifacts (docker compose)

Files present:
- `docker-compose.mock.yml` (Prism mocks only)
- `docker-compose.yml.deprecated` (deprecated mocks compose)
- `docker-compose.component-dev.yml` (claims component dev microservices)

Critical static mismatch:
- `docker-compose.component-dev.yml` references Dockerfiles at:
  - `backend/app/ingestion/Dockerfile`
  - `backend/app/attribution/Dockerfile`
  - `backend/app/auth/Dockerfile`
  - `backend/app/webhooks/Dockerfile`
- No such Dockerfiles exist on `main`.

Evidence:
```powershell
rg --files --glob "!node_modules/**" | rg -n "(?i)dockerfile"
```
```text
docs\forensics\archive\docker_tools\legacy_microservices\Dockerfile.webhooks
docs\forensics\archive\docker_tools\legacy_microservices\Dockerfile.ingestion
docs\forensics\archive\docker_tools\legacy_microservices\Dockerfile.auth
docs\forensics\archive\docker_tools\legacy_microservices\Dockerfile.attribution
```

### API surface (FastAPI routers, webhooks, health, metrics)

Router wiring:
- `backend/app/main.py` includes routers:
  - `/api/auth/*`
  - `/api/attribution/*`
  - `/health*`
  - `/api/webhooks/*`
  - `/metrics`

Implemented webhook routes (current code):
```powershell
rg -n "/webhooks" backend\app\api\webhooks.py
```
```text
150:    "/webhooks/shopify/order_create",
187:    "/webhooks/stripe/payment_intent_succeeded",
230:    "/webhooks/stripe/payment_intent/succeeded",
385:    "/webhooks/paypal/sale_completed",
423:    "/webhooks/woocommerce/order_completed",
```

Contract webhook surfaces (current OpenAPI) include **multiple** endpoints per vendor (not just one). Example paths:
- `api-contracts/openapi/v1/webhooks/shopify.yaml`: `/api/webhooks/shopify/order_create`, `/api/webhooks/shopify/orders/paid`, `/api/webhooks/shopify/refunds/create`, ...
- `api-contracts/openapi/v1/webhooks/stripe.yaml`: `/api/webhooks/stripe/charge/succeeded`, `/api/webhooks/stripe/payment_intent/succeeded`, ...
- `api-contracts/openapi/v1/webhooks/paypal.yaml`: `/api/webhooks/paypal/sale_completed`, `/api/webhooks/paypal/payment/capture/completed`, ...
- `api-contracts/openapi/v1/webhooks/woocommerce.yaml`: `/api/webhooks/woocommerce/order/created`, `/api/webhooks/woocommerce/order_completed`, ...

Health semantics (code):
- `backend/app/api/health.py` defines:
  - `/health/live` liveness
  - `/health/ready` readiness (DB + RLS + tenant GUC)
  - `/health/worker` worker capability (Celery data-plane probe)
  - `/metrics` API metrics + broker-truth queue gauges (filtered; no worker task metrics)

### Celery broker/backend + queues + timeouts (code-defined)

Broker/backend (Postgres-only):
- `backend/app/celery_app.py`:
  - broker: `sqla+postgresql://...` (SQLAlchemy transport over Postgres)
  - result backend: `db+postgresql://...` (database backend over Postgres)
- `backend/app/core/config.py` defaults:
  - `CELERY_TASK_SOFT_TIME_LIMIT_S=300`
  - `CELERY_TASK_TIME_LIMIT_S=360`

Queue registry:
- `backend/app/core/queues.py` defines `housekeeping`, `maintenance`, `llm`, `attribution` as the bounded set.

Worker metrics topology:
- `backend/app/observability/worker_metrics_exporter.py`: exporter is the **only** HTTP listener for worker/task metrics.
- `backend/app/observability/metrics_runtime_config.py`: exporter bind defaults to `127.0.0.1:9108`.

### Materialized views registry (code-defined)

Canonical registry:
- `backend/app/matviews/registry.py` defines 5 refreshable matviews:
  - `mv_allocation_summary`
  - `mv_channel_performance`
  - `mv_daily_revenue_summary`
  - `mv_realtime_revenue`
  - `mv_reconciliation_status`

Refresh pathway:
- `backend/app/tasks/matviews.py` provides:
  - `app.tasks.matviews.refresh_one_for_tenant`
  - `app.tasks.matviews.refresh_all_for_tenant`
  - `app.tasks.matviews.pulse_matviews_global`

### LLM stubs (code-defined)

Tasks exist (deterministic stubs):
- `backend/app/tasks/llm.py`: `app.tasks.llm.route`, `.explanation`, `.investigation`, `.budget_optimization`
- `backend/app/workers/llm.py`: deterministic audit writes to `llm_api_calls` and monthly rollups (no external provider calls).

Static warning:
- Current DB grants (from migrations) do **not** grant `app_user/app_rw` access to `llm_api_calls` (validated at runtime).

---

## PASS 2 — Runtime Audit (Integrated Execution)

### Runtime bootstrap (local Postgres, no Docker)

Reason: Docker engine was not available locally (`com.docker.service` stopped; `docker ps` connect failure).

#### 1) Start fresh Postgres cluster

First attempt failure (encoding):
- `initdb` defaulted to `WIN1252` and **migrations failed** with:
  - `UnicodeEncodeError: 'charmap' codec can't encode character '\u2705' ...`

Resolution:
- Reinitialized Postgres cluster with UTF8 encoding:

```powershell
cd "c:\Users\ayewhy\II SKELDIR II"
pg_ctl -D .tmp\b057_pgdata stop -m immediate
Remove-Item -Recurse -Force .tmp\b057_pgdata
initdb -D .tmp\b057_pgdata -U postgres -A trust -E UTF8
pg_ctl -D .tmp\b057_pgdata -l .tmp\b057_postgres.log -o "-p 5432 -h 127.0.0.1" start
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -Atc "SHOW server_encoding;"
```

Key output:
```text
server_encoding: UTF8
```

Postgres runtime identity:
```powershell
psql -h 127.0.0.1 -p 5432 -U b057_admin -d b057 -c "SELECT version(); SHOW server_version;"
```
```text
PostgreSQL 18.0 ... (Windows)
server_version: 18.0
```

#### 2) Create DB + roles

```powershell
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE ROLE b057_admin LOGIN PASSWORD 'b057_admin' SUPERUSER;"
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE ROLE app_user LOGIN PASSWORD 'app_user' NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;"
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE DATABASE b057 OWNER b057_admin;"
psql -h 127.0.0.1 -p 5432 -U postgres -d b057 -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO app_user; GRANT CONNECT ON DATABASE b057 TO app_user;"
```

#### 3) Run migrations from empty DB

```powershell
$env:MIGRATION_DATABASE_URL="postgresql://b057_admin:b057_admin@127.0.0.1:5432/b057"
alembic upgrade heads
```

Result: ✅ `alembic upgrade heads` succeeded from empty DB on UTF8 cluster.

#### 4) Grant `app_user` membership in `app_rw`

```powershell
psql -h 127.0.0.1 -p 5432 -U b057_admin -d b057 -c "DO $$BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN GRANT app_rw TO app_user; END IF; END$$;"
```

Evidence:
```powershell
psql -h 127.0.0.1 -p 5432 -U b057_admin -d b057 -Atc "SELECT pg_has_role('app_user','app_rw','member');"
```
```text
t
```

### Operational topology snapshot (observed)

Ports/processes (local):
```powershell
netstat -ano | findstr ":18000"
netstat -ano | findstr ":9108"
netstat -ano | findstr ":5432"
```

Key output:
```text
API:      127.0.0.1:18000 LISTENING pid=78028
Exporter: 127.0.0.1:9108  LISTENING pid=100316
DB:       127.0.0.1:5432  LISTENING pid=99200
```

Topology map (runtime):
- FastAPI (`uvicorn`) at `http://127.0.0.1:18000`
  - `/health/live`, `/health/ready`, `/health/worker`
  - `/metrics` (API metrics + broker-truth queue gauges)
- Postgres at `127.0.0.1:5432`
  - persistence + Celery broker (kombu SQLA transport) + Celery result backend
- Celery worker (no HTTP listener)
  - consumes queues: `housekeeping`, `maintenance`, `llm`, `attribution`
- Worker metrics exporter at `http://127.0.0.1:9108/metrics`
  - reads `PROMETHEUS_MULTIPROC_DIR` shards (read-only) for worker/task metrics

**Port note**: `8000` was already occupied by an existing local python process (`netstat` showed PID 36724), so this audit ran FastAPI on `18000`.

### Health truthfulness (normal state)

```powershell
curl.exe -sS -i http://127.0.0.1:18000/health/live
curl.exe -sS -i http://127.0.0.1:18000/health/ready
curl.exe -sS -i http://127.0.0.1:18000/health/worker
```

Observed (representative):
```json
/health/live: 200 {"status":"ok"}
/health/ready: 200 {"status":"ok","database":"ok","rls":"ok","tenant_guc":"ok"}
/health/worker: 200 {"status":"ok","broker":"ok","database":"ok","worker":"ok",...}
```

### Metrics scrape topology (truthfulness)

API metrics include broker-truth gauges and exclude worker task metrics:
```powershell
curl.exe -sS http://127.0.0.1:18000/metrics | findstr /i "celery_queue_"
```

Worker metrics live on exporter only:
```powershell
curl.exe -sS http://127.0.0.1:9108/metrics | findstr /i "celery_task_"
curl.exe -sS http://127.0.0.1:9108/metrics | findstr /i "matview_refresh_"
```

### Webhook ingestion E2E attempt (blocked)

Attempt (minimal request):
```powershell
curl.exe -sS -i -X POST http://127.0.0.1:18000/api/webhooks/paypal/sale_completed ^
  -H "Content-Type: application/json" ^
  -H "X-Skeldir-Tenant-Key: test" ^
  -d "{}"
```

Observed:
```text
HTTP/1.1 500 Internal Server Error
Internal Server Error
```

Root cause evidence (API error log excerpt):
```text
asyncpg.exceptions.InsufficientPrivilegeError: permission denied for table tenants
... in backend/app/core/tenant_context.py:get_tenant_with_webhook_secrets()
```

DB grant evidence:
```powershell
psql -h 127.0.0.1 -p 5432 -U b057_admin -d b057 -c "SELECT table_name, grantee, privilege_type FROM information_schema.role_table_grants WHERE table_schema='public' AND table_name='tenants' ORDER BY table_name, grantee, privilege_type;"
```
```text
tenants grants: only b057_admin has privileges; app_user/app_rw have none
```

**Conclusion**: webhook ingestion cannot execute end-to-end under the “least-privilege” `app_user` runtime DSN currently used by FastAPI (`DATABASE_URL=...app_user...`). This blocks the full webhook→persistence chain in this local runtime configuration.

### Matview refresh chain (success evidence)

Tenant seed (admin insert for FK presence):
```powershell
psql -h 127.0.0.1 -p 5432 -U b057_admin -d b057 -c "INSERT INTO tenants (...) VALUES ('00000000-0000-0000-0000-000000000057', ...) ON CONFLICT DO NOTHING;"
```

Trigger refresh task:
```powershell
python -c "from app.celery_app import celery_app; ...; celery_app.send_task('app.tasks.matviews.refresh_all_for_tenant', kwargs={...}).get(...)"
```

Observed result (representative):
- Task returns `status=ok` with per-view `outcome=SUCCESS` and `duration_ms` for all 5 views.
- Exporter metrics show `matview_refresh_total{view_name=..., outcome=\"success\"} 1.0` for each view.

### Controlled failure pathway + failed-job persistence (success evidence)

Poison pill failure injection (R4 task):
```powershell
python -c "from app.celery_app import celery_app; ...; celery_app.send_task('app.tasks.r4_failure_semantics.poison_pill', kwargs={...}).get(...)"
```

Observed: task fails (expected) and is persisted to `worker_failed_jobs` with `retry_count=3`.

Evidence query:
```powershell
psql -h 127.0.0.1 -p 5432 -U b057_admin -d b057 -x -c "SELECT task_id, task_name, queue, tenant_id, retry_count, status, left(error_message,120) AS error_message_120, failed_at FROM worker_failed_jobs ORDER BY failed_at DESC LIMIT 3;"
```

### RLS enforcement (tenant isolation) — empirical proof

Evidence (same user, different tenant contexts):
```powershell
psql -h 127.0.0.1 -p 5432 -U app_user -d b057 -c "SELECT set_config('app.current_tenant_id','00000000-0000-0000-0000-000000000057', false); SELECT count(*) FROM worker_failed_jobs;"
psql -h 127.0.0.1 -p 5432 -U app_user -d b057 -c "SELECT set_config('app.current_tenant_id','00000000-0000-0000-0000-000000000058', false); SELECT count(*) FROM worker_failed_jobs;"
psql -h 127.0.0.1 -p 5432 -U app_user -d b057 -c "RESET app.current_tenant_id; SELECT count(*) FROM worker_failed_jobs;"
```

Observed:
```text
tenant_id=...057: count(*) = 5
tenant_id=...058: count(*) = 0
no tenant GUC:     count(*) = 0
```

---

## Failure Semantics Trace (Truthful Degradation)

### 1) Worker stopped

Action:
```powershell
Stop-Process -Id <celery_pid> -Force
```

Observed:
- `/health/live` remained 200 (liveness truth)
- `/health/ready` remained 200 (DB/RLS readiness truth)
- `/health/worker` became 503 (worker capability truth)

Representative output (after worker stop):
```text
HTTP/1.1 200 OK
{"status":"ok"}                               # /health/live

HTTP/1.1 200 OK
{"status":"ok","database":"ok","rls":"ok","tenant_guc":"ok"}   # /health/ready

HTTP/1.1 503 Service Unavailable
{"status":"unhealthy","broker":"ok","database":"error","worker":"error",...}  # /health/worker
```

### 2) Broker unavailable (Postgres down)

Action:
```powershell
pg_ctl -D .tmp\b057_pgdata stop -m immediate
pg_isready -h 127.0.0.1 -p 5432
```

Observed:
- `/health/live` remained 200
- `/health/ready` became 503 with `"database":"error"`
- `/health/worker` became 503 with `"broker":"error"`
- `/metrics` continued to return 200 and preserved last-good broker-truth gauges, incrementing `celery_queue_stats_refresh_errors_total`

Representative output (during Postgres down):
```text
pg_isready: 127.0.0.1:5432 - no response

HTTP/1.1 200 OK
{"status":"ok"}  # /health/live

HTTP/1.1 503 Service Unavailable
{"status":"unhealthy","database":"error","rls":"ok","tenant_guc":"ok"}  # /health/ready

HTTP/1.1 503 Service Unavailable
{"status":"unhealthy","broker":"error","database":"error","worker":"error",...}  # /health/worker

celery_queue_stats_refresh_errors_total 1.0  # /metrics (still 200)
```

### 3) Exporter unavailable

Action:
```powershell
Stop-Process -Id <exporter_pid> -Force
```

Observed:
- `http://127.0.0.1:9108/metrics` became unreachable (`curl: (7) Failed to connect...`)
- API `/metrics` remained 200

Representative output:
```text
curl: (7) Failed to connect to 127.0.0.1 port 9108 ...  # exporter
HTTP/1.1 200 OK                                          # API /metrics
```

---

## Hypothesis Truth Table (A–J)

Legend: **TRUE** = validated by code/runtime/CI config; **FALSE** = falsified; **UNKNOWN** = not provable from this run without new code/tests or missing harness.

### A) Repo Ground Truth & Governance
- **H-A1** Golden Master anchor exists: **TRUE** — `docs/forensics/INDEX.md` includes B0.5.6 Phase 8 “evidence closure” row.
- **H-A2** Evidence packs exist as claimed: **TRUE** — `docs/forensics/` contains `b056_*` evidence packs and `INDEX.md` references them.
- **H-A3** B0.5.7 artifacts already exist on `main`: **FALSE** — no `B0.5.7`/`b057` artifacts found pre-change (ripgrep no matches).

### B) Integration Harness / Orchestration
- **H-B1** Compose harness exists and starts topology: **FALSE** — `docker-compose.component-dev.yml` references missing Dockerfiles; mocks compose exists but is mocks-only.
- **H-B2** Documented local run path exists and works: **FALSE** — no single authoritative “start full topology” runbook/harness verified pre-change; this evidence pack documents a working local run path, but it did not exist before this addition.
- **H-B3** Service boundaries are production-like (API/DB/broker/worker/exporter separate): **TRUE** — runtime observed separate processes (API + Postgres + Celery worker + exporter).

### C) Database, Migrations, and RLS
- **H-C1** Postgres-only enforced (no Redis/Kafka): **TRUE** — Celery broker/backend configured as Postgres (`sqla+` and `db+`); no Redis dependency in Python requirements (note: Redis referenced in `Procfile` and `empirical-validation.yml`).
- **H-C2** Migrations authoritative and apply cleanly from empty DB: **TRUE** — `alembic upgrade heads` succeeds from empty DB when Postgres cluster encoding is UTF8 (fails under WIN1252 due to Unicode in migration text).
- **H-C3** RLS is active and enforced: **TRUE** — readiness enforces RLS on `attribution_events`; tenant isolation empirically validated via RLS-filtered counts.
- **H-C4** Tenant isolation testable: **TRUE** — empirical RLS test shown (tenant A sees rows; tenant B sees 0; no tenant sees 0).

### D) Webhook Ingestion Reality
- **H-D1** Exactly four webhook endpoints exist: **FALSE** — implementation exposes 5 webhook paths; contracts expose more.
- **H-D2** Schemas are B0.4-compatible: **UNKNOWN** — full webhook ingestion cannot execute end-to-end under current `app_user` grants; compatibility not validated in runtime here.
- **H-D3** Auth/tenant resolution mechanism exists and is testable: **FALSE** — mechanism exists in code (`X-Skeldir-Tenant-Key` + `tenants.api_key_hash`), but runtime returns 500 due to missing `SELECT` grant on `tenants` for `app_user`.

### E) Worker/Task Topology & Queue Semantics
- **H-E1** Celery topology matches doctrine (real worker + Postgres broker/backend): **TRUE** — `/health/worker` proves API→broker→worker→backend round-trip when healthy.
- **H-E2** Queues/routing explicit: **TRUE** — queue names centralized (`backend/app/core/queues.py`) and routing configured in `backend/app/celery_app.py`.
- **H-E3** Timeouts/budgets exist and enforced: **TRUE** — global soft/hard time limits configured in `backend/app/core/config.py` and applied in `backend/app/celery_app.py`.

### F) Matview Registry & Refresh Chain
- **H-F1** Matviews exist + enumerated canonically: **TRUE** — `backend/app/matviews/registry.py` lists 5 views.
- **H-F2** Refresh task exists: **TRUE** — `app.tasks.matviews.refresh_all_for_tenant` exists and runs.
- **H-F3** Refresh correctness observable: **TRUE** — refresh returns per-view success payload + exporter `matview_refresh_*` metrics.

### G) LLM Stub Integration
- **H-G1** LLM stubs exist and do not require external providers: **TRUE** — deterministic worker stubs exist in code.
- **H-G2** LLM audit rows exist and are empirically verifiable: **FALSE** — schema exists but runtime cannot write `llm_api_calls` due to missing grants; `SELECT count(*) FROM llm_api_calls = 0` after attempted runs and worker DLQ shows permission errors.

### H) Observability & Truthfulness
- **H-H1** No worker HTTP sidecar: **TRUE** — worker has no bound HTTP port; exporter serves `/metrics` on 9108.
- **H-H2** Scrape target is unambiguous: **TRUE** — exporter is the worker metrics surface; API `/metrics` remains available even when exporter is down.
- **H-H3** Health semantics split correctly: **TRUE** — observed truthful liveness/readiness/worker degradation across worker-down and broker-down states.
- **H-H4** Queue depth/max age from broker truth: **TRUE** — `celery_queue_*` gauges derived from kombu tables, cached; survives broker outage with error counter increment.
- **H-H5** Cardinality/privacy tests enforced in CI: **TRUE** (CI-config evidence) — `ci.yml` runs metrics/privacy gate tests (pytest entries present). Not re-run locally in this evidence pack.
- **H-H6** Structured worker logs runtime-accurate: **TRUE** — observed JSON worker logs include `tenant_id` and correlation fields on real task executions.

### I) CI Reality
- **H-I1** Dedicated CI job for E2E exists: **TRUE** — R3/R4 workflows exist and run runtime harnesses.
- **H-I2** CI provisions DB and runs migrations: **TRUE** — multiple workflows provision Postgres service and run `alembic upgrade heads`.
- **H-I3** CI truth matches local truth: **FALSE** — CI R3 harness uses a non-least-privilege DB user (`postgresql://r3:r3...`) while local runtime using `app_user` surfaces hard failures (webhooks/LLM grants). Local Windows runtime also surfaced encoding and async loop issues not represented in CI’s ubuntu runners.

### J) Controlled Failure Evidence
- **H-J1** Failure injection pathway exists today: **TRUE** — `app.tasks.r4_failure_semantics.poison_pill` (and `fail` flags) provide controlled failures.
- **H-J2** Failed job persistence exists: **TRUE** — `worker_failed_jobs` contains rows for controlled failures with error payloads.

---

## Operational Readiness Snapshot

**What works today (empirically)**
- `/health/live`, `/health/ready`, `/health/worker` semantics are truthful under broker/worker degradation.
- Celery Postgres-only broker/backend functions; `/metrics` exposes broker-truth queue gauges with caching.
- Worker/task metrics are exporter-only (`9108/metrics`); API `/metrics` excludes worker task metrics.
- Matview refresh chain works end-to-end and is observable via exporter metrics and task result payloads.
- Failed-job persistence (`worker_failed_jobs`) works and is tenant-filterable under RLS.

**What breaks today (empirically)**
- Webhook ingestion endpoints return **500** under `app_user` due to missing `SELECT` privileges on `tenants`.
- LLM stub tasks cannot persist audit rows due to missing privileges on `llm_api_calls`; additional Windows async loop errors were observed under DB connectivity loss.

**What is unsafe today**
- Least-privilege role grants for `app_user` appear incomplete for required runtime features (webhooks + LLM auditing), leading to hard 500s rather than controlled 401/4xx paths.

---

## Blocked Implementation Inputs (Binary Questions)

1. Should `app_user` (or `app_rw`) have `SELECT` on `public.tenants` to support webhook tenant lookup, or should webhook tenant lookup use a dedicated SECURITY DEFINER path?
2. Should `app_user` (or `app_rw`) have `INSERT/SELECT` on `public.llm_api_calls` and related LLM tables to allow deterministic stub execution?
3. Is Windows a supported local runtime for Celery+asyncpg worker loops? If yes, should the worker enforce `WindowsSelectorEventLoopPolicy` or an equivalent to avoid the observed `'NoneType' object has no attribute 'send'` failures during DB loss/reconnect?

---

## Cleanup (Local)

This run started local processes for evidence collection and then stopped them.

Commands executed:
```powershell
Stop-Process -Id 78028 -Force   # uvicorn (API on 18000)
Stop-Process -Id 110736 -Force  # celery worker
Stop-Process -Id 100316 -Force  # worker metrics exporter (9108)
pg_ctl -D .tmp\b057_pgdata stop -m immediate  # Postgres (5432)
```

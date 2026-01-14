# B055 Phase 5 Full-Stack Integrity Context Gathering Evidence

## Section A - Chain-of-custody
- Branch: b055-phase5-context-gathering
- git rev-parse HEAD: 56e81e83ceed8f7f1f4b3287d8cd26af7174c0ac
- PR: https://github.com/Muk223/skeldir-2.0/pull/21
- Timestamp: 2026-01-14T12:15:01.9453590-06:00

## Section B - Provider creep audit

### B1. Forbidden provider SDK scan (repo-wide)
Command:
```
rg -n "openai|anthropic|google.generativeai|vertexai|bedrock|boto3" backend/app scripts
```
Output:
```
(no matches)
```

### B2. Network client scan (backend runtime surface)
Command:
```
rg -n "requests|httpx|aiohttp|urllib|socket" backend/app
```
Output:
```
backend/app/core/tenant_context.py:85:    Canonical algorithm for deriving tenant_id from API requests.
backend/app/db/session.py:15:from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
backend/app/middleware/pii_stripping.py:32:from starlette.requests import Request
backend/app/middleware/pii_stripping.py:133:        # Only process ingestion-boundary requests.
backend/app/middleware/pii_stripping.py:137:        # Only process POST/PUT/PATCH requests with JSON content
backend/app/tasks/r6_resource_governance.py:12:from urllib.parse import urlsplit
```
Reachability classification:
- Reachable runtime: `backend/app/db/session.py` uses `urllib.parse` for DSN parsing (no egress); `backend/app/tasks/r6_resource_governance.py` uses `urlsplit` (parse only). No HTTP client usage detected in worker/task modules.
- Unreachable (non-runtime): matches above are comments/Starlette Request usage; no outbound HTTP libs.

### B3. Network client scan (repo-wide scripts)
Command:
```
rg -n "requests|httpx|aiohttp|urllib|socket" backend/app scripts
```
Output:
```
scripts/measure-latency.sh:25:# Make requests and collect response times
scripts/measure-latency.sh:60:echo "  Total requests: $NUM_REQUESTS"
scripts/measure-latency.sh:81:  "requests": $NUM_REQUESTS
scripts/phase_gates/generate_value_trace_proof_pack.py:25:import urllib.request
scripts/phase_gates/generate_value_trace_proof_pack.py:51:    req = urllib.request.Request(url)
scripts/phase_gates/generate_value_trace_proof_pack.py:55:    with urllib.request.urlopen(req, timeout=30) as resp:
scripts/test-response-parity.sh:92:import requests
scripts/test-response-parity.sh:99:resp = requests.post("http://localhost:4010/api/auth/login", headers=headers, json=payload)
scripts/r6/r6_context_gathering.py:22:from urllib.parse import urlsplit
scripts/r5/r5_verification.py:28:from urllib.parse import urlsplit
scripts/r4/worker_failure_semantics.py:20:from urllib.parse import urlsplit
scripts/r5/r5_probes.py:27:from urllib.parse import urlsplit
backend/app/db/session.py:15:from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
scripts/r3/ingestion_under_fire.py:26:import httpx
scripts/r3/ingestion_under_fire.py:170:    client: httpx.AsyncClient,
scripts/r3/ingestion_under_fire.py:171:    requests: list[tuple[str, dict[str, str], bytes]],
scripts/r3/ingestion_under_fire.py:187:            except (httpx.TimeoutException, asyncio.TimeoutError):
scripts/r3/ingestion_under_fire.py:190:            except httpx.RequestError:
scripts/r3/ingestion_under_fire.py:194:    await asyncio.gather(*[_one(url, headers, body) for (url, headers, body) in requests])
scripts/r3/ingestion_under_fire.py:198:async def _wait_for_http_ready(client: httpx.AsyncClient, base_url: str, *, attempts: int = 10, delay_s: float = 1.0) -> None:
scripts/r3/ingestion_under_fire.py:206:        except httpx.RequestError:
scripts/r3/ingestion_under_fire.py:364:    client: httpx.AsyncClient,
scripts/r3/ingestion_under_fire.py:422:    client: httpx.AsyncClient,
scripts/r3/ingestion_under_fire.py:482:    client: httpx.AsyncClient,
scripts/r3/ingestion_under_fire.py:542:    client: httpx.AsyncClient,
scripts/r3/ingestion_under_fire.py:612:    client: httpx.AsyncClient,
scripts/r3/ingestion_under_fire.py:683:    client: httpx.AsyncClient,
scripts/r3/ingestion_under_fire.py:863:    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
scripts/r3/ingestion_under_fire.py:864:    async with httpx.AsyncClient(limits=limits) as client:
backend/app/middleware/pii_stripping.py:32:from starlette.requests import Request
backend/app/middleware/pii_stripping.py:133:        # Only process ingestion-boundary requests.
backend/app/middleware/pii_stripping.py:137:        # Only process POST/PUT/PATCH requests with JSON content
backend/app/tasks/r6_resource_governance.py:12:from urllib.parse import urlsplit
backend/app/core/tenant_context.py:85:    Canonical algorithm for deriving tenant_id from API requests.
```
Reachability classification:
- Reachable runtime risk: none detected (no HTTP client usage in `backend/app/tasks/llm.py`, `backend/app/workers/llm.py`, or `backend/app/celery_app.py`).
- Unreachable (scripts/bench): httpx/requests/urllib.request used in scripts under `scripts/` for validations or local tooling.

### B4. Dynamic import scan
Commands:
```
rg -n "importlib|__import__" backend/app
rg -n "importlib|__import__" scripts
```
Outputs:
```
(no matches)
```
```
scripts/generate-models.sh.backup:265:import importlib
scripts/generate-models.sh.backup:281:        importlib.import_module(module_name)
scripts/phase_gates/_bootstrap.py:57:        import importlib
scripts/phase_gates/_bootstrap.py:59:        importlib.import_module("scripts.phase_gates")
scripts/phase_gates/_bootstrap.py:60:        importlib.import_module("app")
scripts/validate_model_usage.py:28:            module = __import__(f'backend.app.schemas.{module_name}', fromlist=models)
scripts/phase_gates/run_gate.py:17:from importlib import import_module
scripts/ci/zero_drift_v3_2.sh:67:import importlib
scripts/ci/zero_drift_v3_2.sh:68:mod = importlib.import_module("app.tasks.maintenance")
```
Classification: dynamic imports exist only in scripts; none in backend runtime modules.

### B5. CI enforcement audit (provider creep / network egress)
Command:
```
rg -n "forbidden|provider|egress|network" .github/workflows/ci.yml
```
Output:
```
(no matches)
```
Notes:
- Network isolation appears in `r0-preflight-validation.yml` (podman network egress probe), but there is no equivalent enforcement in the main PR `ci.yml` workflow. CI does not currently block provider/network imports at PR time.

### B6. Reachability map for LLM worker/task entry points
Entry points and imports (direct):
- `backend/app/tasks/llm.py` imports: `app.celery_app`, `app.db.session.get_session`, `app.observability.context`, `app.schemas.llm_payloads`, `app.tasks.context`, `app.workers.llm`.
- `backend/app/workers/llm.py` imports: `app.models.llm`, `app.schemas.llm_payloads`, SQLAlchemy (no HTTP clients).
- `backend/app/celery_app.py` includes tasks and routes (no provider SDKs).
Conclusion: no direct/indirect provider SDK or HTTP client usage in reachable runtime LLM task/worker path.

## Section C - Full-stack cohesion map (B0.1 -> B0.5.5)

### C1. API contracts -> broker serialization (B0.1 -> B0.5.1)
Code-defined authority:
- API contracts live in `api-contracts/openapi/v1/` (includes `llm-explanations.yaml`, `llm-investigations.yaml`, `llm-budget.yaml`).
- Backend API routers present in `backend/app/api/` (auth, attribution, health, webhooks). No LLM API router present in `backend/app/api/`.
- Celery serialization config in `backend/app/celery_app.py`:
```
rg -n "task_serializer|accept_content|result_serializer" backend/app/celery_app.py
134:        task_serializer="json",
135:        result_serializer="json",
136:        accept_content=["json"],
```
Evidence of enqueue callsites:
```
rg -n "apply_async|delay\(" backend/app -S
backend/app/services/attribution.py:64:    return recompute_window.apply_async(
backend/app/tasks/matviews.py:354:            matview_refresh_all_for_tenant.delay(
```
Status: LLM task enqueue path not found in code; API -> broker path for LLM remains unproven.

### C2. Topology -> workers (B0.5.2 -> B0.5.3)
Queue constants and routing:
```
rg -n "task_queues|task_routes|QUEUE_LLM" backend/app/celery_app.py
20:from app.core.queues import QUEUE_LLM
175:        task_queues=[
178:            Queue(QUEUE_LLM, routing_key='llm.#'),
181:        task_routes={
185:            'app.tasks.llm.*': {'queue': QUEUE_LLM, 'routing_key': 'llm.task'},
```
LLM task registrations:
```
rg -n "app\.tasks\.llm" backend/app/tasks/llm.py
75:    name="app.tasks.llm.route",
129:@celery_app.task(bind=True, name="app.tasks.llm.explanation", max_retries=3, default_retry_delay=30)
183:@celery_app.task(bind=True, name="app.tasks.llm.investigation", max_retries=3, default_retry_delay=30)
237:@celery_app.task(bind=True, name="app.tasks.llm.budget_optimization", max_retries=3, default_retry_delay=30)
```
DLQ handling:
- `backend/app/celery_app.py` task_failure signal persists failures into `worker_failed_jobs` using psycopg2 (DLQ path).
Tests present:
- `backend/tests/test_b052_queue_topology_and_dlq.py` and `backend/tests/test_b051_celery_foundation.py` (routing + registration assertions).
Status: basic topology is covered; concurrency routing not proven.

### C3. Ingestion <-> MatView (B0.4 <-> B0.5.4)
Matview scheduling + execution:
- Beat schedule: `backend/app/tasks/beat_schedule.py` uses `app.tasks.matviews.pulse_matviews_global`.
- Tasks: `backend/app/tasks/matviews.py` dispatches `refresh_all_for_tenant`.
- Refresh executor: `backend/app/matviews/executor.py` uses `REFRESH MATERIALIZED VIEW CONCURRENTLY` via registry entries:
```
rg -n "REFRESH MATERIALIZED VIEW" backend/app/matviews/registry.py
13:REFRESH_SQL_CONCURRENTLY = "REFRESH MATERIALIZED VIEW CONCURRENTLY {qualified_name}"
```
Status: refresh SQL is limited to matviews by registry, but there is no explicit evidence that ingestion tables are read-only beyond convention; DB role enforcement is not demonstrated here.

### C4. Schema <-> stubs (B0.3 <-> B0.5.5)
LLM table migrations:
- `alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py`
- `alembic/versions/004_llm_subsystem/202512081510_add_llm_rls_policies.py`
- `alembic/versions/004_llm_subsystem/202601131610_add_llm_api_call_idempotency.py`
ORM models + constraints:
```
rg -n "__tablename__ = "llm_api_calls"|uq_llm_api_calls_tenant_request_endpoint" backend/app/models/llm.py
30:    __tablename__ = "llm_api_calls"
69:            name="uq_llm_api_calls_tenant_request_endpoint",
```
Stub write path + markers:
```
rg -n "_STUB_MODEL|request_metadata" backend/app/workers/llm.py
28:_STUB_MODEL = "llm_stub"
58:            model=_STUB_MODEL,
64:            request_metadata={
```
Tests:
- `backend/tests/test_b055_llm_worker_stubs.py` asserts stub markers, cost=0, and idempotency behaviors.
Status: LLM stub writes are constrained and tested, but coverage of all domain invariants beyond LLM tables is unproven.

### C5. RLS / tenant enforcement (cross-cutting)
Tenant session context:
- `backend/app/db/session.py` `get_session()` sets `app.current_tenant_id` for RLS.
RLS tests:
```
rg -n "pg_policies|RLS" backend/tests/test_b055_llm_worker_stubs.py
32:    assert engine.dialect.name == "postgresql", "RLS tests must run on Postgres"
164:                FROM pg_policies
181:        }, f"Missing RLS policies: {policy_tables}"
185:        assert blocked is None, "RLS failed: tenant B read tenant A investigation"
```
Status: RLS enforcement is proven for LLM stub path; other Celery tasks remain unproven in this evidence pass.

## Section D - Risk register (H-PC*, H-SC*)

| Hypothesis | Status | Evidence pointer | Missing evidence / gap if UNPROVEN |
| --- | --- | --- | --- |
| H-PC1 (provider SDK imports in runtime paths) | PROVEN FALSE | `rg` provider scan returned no matches in `backend/app` and reachability tree excludes provider libs. | N/A |
| H-PC2 (HTTP clients in reachable worker/task paths) | PROVEN FALSE | `rg` network scan in `backend/app` shows only urllib.parse usage; no httpx/requests in task/worker modules. | N/A |
| H-PC3 (dynamic import allows provider creep) | PROVEN FALSE | No `importlib`/`__import__` in `backend/app`; dynamic imports only in scripts. | N/A |
| H-PC4 (CI does not enforce hermeticity) | PROVEN TRUE | `rg` in `.github/workflows/ci.yml` shows no forbidden-import or network-egress enforcement. | N/A |
| H-SC1 (contract mutates across API -> broker serialization) | UNPROVEN | No API enqueue path found for LLM tasks; no encode->broker->decode test. | Add a Celery roundtrip test that enqueues LLM payload via API layer (or task producer) and validates schema fidelity on worker side. |
| H-SC2 (routing + DLQ not proven under concurrency) | UNPROVEN | Routing tests exist, but no concurrency or mixed-workload routing evidence. | Add concurrency routing/queue saturation tests + DLQ under load. |
| H-SC3 (matview refresh violates ingestion boundaries) | UNPROVEN | Refresh uses registry + REFRESH MATERIALIZED VIEW, but no explicit read-only enforcement for ingestion tables. | Add DB role/perms audit or test proving refresh runs with read-only permissions for ingestion tables. |
| H-SC4 (stub outputs violate schema/domain invariants) | UNPROVEN | Stub markers tested for LLM tables, but not a full invariants audit across all relevant columns/constraints. | Expand tests to assert full column invariants and semantic markers beyond LLM tables. |
| H-SC5 (RLS bypass in Celery runtime) | UNPROVEN | RLS tests present for LLM stubs only; other Celery tasks not proven. | Add cross-tenant negative tests for additional worker types (matviews/attribution/etc.). |

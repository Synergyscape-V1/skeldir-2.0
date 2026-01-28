# B0.6 Realtime Revenue Context Pack

## Repo state
- Branch: main (from `git branch --show-current`)
- Commit: 09048cb1af81886c7138cf898ed0f4d765756fb6 (from `git rev-parse HEAD`)
- Dirty: clean (from `git status --porcelain=v1` produced no output)

Command outputs:
```text
git status --porcelain=v1
(no output)

git rev-parse HEAD
09048cb1af81886c7138cf898ed0f4d765756fb6

git branch --show-current
main
```

## System startability notes
- Component dev stack: `docker-compose -f docker-compose.component-dev.yml up` (file comment and usage). Evidence: `docker-compose.component-dev.yml:5`.
- Not executed in this forensic pass (no runtime audit performed).

## Hypothesis table
| Hypothesis | Status | Evidence (file:line / command output) | Notes |
|---|---|---|---|
| H01: B0.6 "realtime revenue" endpoint already exists (router + handler) | SUPPORTED | `backend/app/api/attribution.py:23`, `backend/app/api/attribution.py:31`, `backend/app/main.py:62` | Handler `get_realtime_revenue` is defined and router is included under `/api/attribution`. |
| H02: Endpoint path+method matches explicit OpenAPI route | SUPPORTED | `api-contracts/dist/openapi/v1/attribution.bundled.yaml:23`, `api-contracts/dist/openapi/v1/attribution.bundled.yaml:29`, `backend/app/api/attribution.py:23` | OpenAPI declares `GET /api/attribution/revenue/realtime`; router path is `/revenue/realtime` under `/api/attribution`. |
| H03: Response schema includes tenant_id, interval, currency, revenue_total, data_as_of, verified=false, source/platform identifiers | REFUTED | `backend/app/schemas/attribution.py:13`, `backend/app/schemas/attribution.py:34`, `backend/app/api/attribution.py:60`, `api-contracts/dist/openapi/v1/attribution.bundled.yaml:75` | Schema/contract require `total_revenue`, `event_count`, `last_updated`, `data_freshness_seconds`, `verified`, `tenant_id`. No `interval`, `currency`, `revenue_total`, `data_as_of`, or platform/source fields. |
| H04: Endpoint enforces JWT Bearer auth; rejects missing/invalid tokens | REFUTED | `backend/app/api/attribution.py:31`, `backend/app/main.py:30`, `api-contracts/dist/openapi/v1/attribution.bundled.yaml:32` | Handler only requires `X-Correlation-ID`; no auth dependency/middleware is wired. OpenAPI requires bearerAuth but enforcement not present in code. |
| H05: Tenant identity derived from JWT claim and used to set DB/RLS context | REFUTED | `backend/app/api/attribution.py:53`, `backend/app/api/attribution.py:67`, `backend/app/core/tenant_context.py:81`, `backend/app/main.py:30`, `backend/app/db/session.py:87` | Handler uses `TEST_TENANT_ID` env var; no DB session used. Tenant context middleware exists but is not registered in `main.py`. |
| H06: Live platform fetch implemented at request time (subject to cache) | REFUTED | `backend/app/api/attribution.py:60` | Handler returns stub constants (`total_revenue`, `event_count`) without any outbound call or platform client. |
| H07: Platform credentials/config defined in authoritative settings layer | REFUTED | `backend/app/core/config.py:21`, `.env.example:10` | No platform credential fields in settings or `.env.example`. |
| H08: Tenant -> platform account identifier mapping exists | REFUTED | Command output below (no matches) | No model/service references for ad account IDs found in backend code. |
| H09: Data integrity check vs platform API exists | REFUTED | `backend/app/api/attribution.py:60` | No comparison logic; only stub values. |
| H10: Postgres cache table exists with tenant_id + key dims + payload + TTL | REFUTED | `alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py:170`, `backend/app/models/llm.py:52` | Only `explanation_cache` exists (LLM subsystem). No revenue cache table identified. |
| H11: Cache read/write happens on request path for B0.6 | REFUTED | `backend/app/api/attribution.py:60` | No cache access in handler. |
| H12: Burst protection singleflight exists for B0.6 | REFUTED | `backend/app/api/health.py:135`, `backend/app/api/attribution.py:31` | Singleflight logic exists only for health probes, not for realtime revenue handler. |
| H13: Cache is tenant-safe under RLS | REFUTED | `backend/app/db/session.py:87`, `alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py:170` | No realtime revenue cache table exists; tenant-safe cache for this endpoint is absent. |
| H14: Upstream failure -> 503 + Retry-After | REFUTED | `backend/app/api/attribution.py:31`, `backend/app/api/health.py:283` | Realtime handler has no upstream call or 503 logic. 503 handling exists in health endpoint only. |
| H15: data_as_of reflects successful platform fetch time | REFUTED | `backend/app/api/attribution.py:64`, `backend/app/schemas/attribution.py:22` | No `data_as_of` field; `last_updated` set to `datetime.utcnow()` at request time. |
| H16: Logs do not leak tokens/PII; metrics cardinality bounded | INCONCLUSIVE | `backend/app/middleware/observability.py:15`, `backend/app/middleware/pii_stripping.py:61`, `backend/app/observability/celery_task_lifecycle.py:144` | API handler does not log, and PII stripping only applies to `/api/webhooks`. Celery logging allowlist exists, but no explicit guarantee for this API path. |
| H17: Request/trace correlation exists | SUPPORTED | `backend/app/middleware/observability.py:21`, `backend/app/api/attribution.py:31`, `backend/app/main.py:48` | Middleware sets `X-Correlation-ID` and handler requires it. |

## Phase 3 update (post-remediation)
- H04/H05 (Auth + tenant derivation): **SUPPORTED** — attribution and v1 endpoints now depend on `get_auth_context` and `get_db_session` to derive tenant_id and set RLS GUC. Evidence: `backend/app/api/attribution.py`, `backend/app/api/revenue.py`, `backend/app/db/deps.py`.
- H10/H11/H13 (Postgres cache + tenant-safe RLS): **SUPPORTED** — new `revenue_cache_entries` table with RLS policy and grants; request path reads/writes via shared service. Evidence: `alembic/versions/007_skeldir_foundation/202601281230_b060_phase3_realtime_revenue_cache.py`, `backend/app/services/realtime_revenue_cache.py`.
- H12 (stampede prevention): **SUPPORTED** — advisory-lock singleflight with follower polling implemented in service layer. Evidence: `backend/app/services/realtime_revenue_cache.py`.
- H14 (failure semantics): **SUPPORTED** — endpoints return 503 with `Retry-After` on refresh failure or cooldown. Evidence: `backend/app/api/attribution.py`, `backend/app/api/revenue.py`.

Command output (H08 evidence):
```text
rg -n "ad_account|ad account|account_id|platform_account" backend\\app\\models backend\\app\\core backend\\app\\services
(no output)
```

## Evidence links (key files)
- `backend/app/api/attribution.py:23` (route), `backend/app/api/attribution.py:60` (stub response)
- `backend/app/schemas/attribution.py:13` (RealtimeRevenueCounter schema)
- `api-contracts/dist/openapi/v1/attribution.bundled.yaml:23` (OpenAPI route and security)
- `backend/app/main.py:61` (router inclusion), `backend/app/main.py:48` (ObservabilityMiddleware)
- `backend/app/core/tenant_context.py:81` (tenant derivation), `backend/app/db/session.py:87` (RLS GUC setting)
- `backend/app/middleware/observability.py:21` (correlation id), `backend/app/middleware/pii_stripping.py:61` (PII strip scope)
- `alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py:170` (explanation_cache only)
- `backend/app/api/health.py:135` (singleflight cache in health)
- `docker-compose.component-dev.yml:5` (start command comment)

## Risk register (code-defined ambiguities)
1) Auth/tenant boundary not enforced in realtime revenue handler; OpenAPI claims bearerAuth but code does not enforce it. Risk: cross-tenant leakage or unauthenticated access. Evidence: `backend/app/api/attribution.py:31`, `api-contracts/dist/openapi/v1/attribution.bundled.yaml:32`.
2) Realtime revenue values are hardcoded stubs and not tenant-scoped beyond `TEST_TENANT_ID`. Risk: incorrect data and misleading verified semantics. Evidence: `backend/app/api/attribution.py:53`, `backend/app/api/attribution.py:60`.
3) No Postgres cache or burst protection on request path. Risk: platform fetch stampede when implemented. Evidence: `backend/app/api/attribution.py:60`, `backend/app/api/health.py:135` (singleflight exists elsewhere only).
4) Contract claims ETag/Cache-Control and 30s TTL, but handler does not emit headers or cache. Risk: contract drift. Evidence: `api-contracts/dist/openapi/v1/attribution.bundled.yaml:27`, `backend/app/api/attribution.py:31`.
5) No platform credential/config mapping or account binding. Risk: cannot satisfy "source of truth" requirements. Evidence: `backend/app/core/config.py:21`, `.env.example:10`.

## Exit gates (G1-G10)
- G1 Endpoint existence proven: PASS. Evidence: `backend/app/api/attribution.py:23`.
- G2 Exact endpoint contract captured: PASS (from OpenAPI + handler). Evidence: `api-contracts/dist/openapi/v1/attribution.bundled.yaml:23`, `backend/app/api/attribution.py:23`.
- G3 Auth mechanism proven in code: FAIL (no JWT enforcement in handler). Evidence: `backend/app/api/attribution.py:31`.
- G4 Tenant resolution path proven: FAIL (tenant derived from env var, not JWT; middleware not wired). Evidence: `backend/app/api/attribution.py:53`, `backend/app/main.py:30`.
- G5 Truth source proven: FAIL (no platform client or outbound fetch). Evidence: `backend/app/api/attribution.py:60`.
- G6 Cache mechanism proven: FAIL (no PG cache table or request-path cache). Evidence: `alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py:170`, `backend/app/api/attribution.py:60`.
- G7 Burst protection proven: FAIL (no singleflight on this endpoint). Evidence: `backend/app/api/health.py:135` (unrelated singleflight), `backend/app/api/attribution.py:31`.
- G8 Failure semantics proven: FAIL (no 503 + Retry-After in handler). Evidence: `backend/app/api/attribution.py:31`.
- G9 Config surface captured: PARTIAL (core DB/Celery settings only; no platform creds). Evidence: `backend/app/core/config.py:21`, `.env.example:10`.
- G10 Evidence pack written: PASS (this document).

## Runtime audit
Not executed. No OpenAPI runtime inspection performed. Startability reference only: `docker-compose -f docker-compose.component-dev.yml up` (`docker-compose.component-dev.yml:5`).

# Phase 3 Context Delta Notes (B0.6)

Date: 2026-01-28
Repo: C:\Users\ayewhy\II SKELDIR II

## Step A — Current repo truth

Commands:
- `git rev-parse HEAD`
- `git status --porcelain`

Findings:
- HEAD: `09048cb1af81886c7138cf898ed0f4d765756fb6`
- Working tree: clean (no output from `git status --porcelain`)

## Step B — Discover existing cache patterns

Commands:
- `rg -n "revenue_cache|cache" -S .`
- `rg -n "advisory|pg_try_advisory|SKIP LOCKED|FOR UPDATE|singleflight|single-flight|single flight" backend -S`
- `rg -n "Retry-After|cooldown|stampede|singleflight|single-flight" backend -S`

Findings:
- No revenue cache table or model found.
  - Alembic search shows only `explanation_cache` in LLM subsystem; no `revenue_cache` / `revenue_cache_entries`. Ref: `alembic/versions/004_llm_subsystem/202512081500_create_llm_tables.py`.
  - Backend models include `AttributionEvent` with `revenue_cents` but no cache model. Ref: `backend/app/models/attribution_event.py`.
- Singleflight exists only in-memory:
  - Health worker probe cache + singleflight lock. Ref: `backend/app/api/health.py`.
  - Broker queue stats TTL cache + async singleflight. Ref: `backend/app/observability/broker_queue_stats.py`.
- Postgres advisory lock helper exists, scoped to matview refresh (xact lock). Ref: `backend/app/core/pg_locks.py` and `backend/app/matviews/executor.py`.
- No Retry-After or cooldown logic found in backend for realtime revenue paths.

Hypothesis checks (B0.6 Phase 3 blockers):
- H3-1 (No revenue cache table): **CONFIRMED TRUE** — no table/migration/model.
- H3-2 (No request-path cache read/write): **CONFIRMED TRUE** — realtime revenue handlers are stub responses only.
  - Attribution endpoint: `backend/app/api/attribution.py`.
  - Canonical v1 endpoint: `backend/app/api/revenue.py`.
- H3-3 (No stampede prevention on this endpoint): **CONFIRMED TRUE** — only in-memory singleflight exists in health/metrics, not reused for revenue endpoints.
- H3-5 (Failure stampede not addressed): **CONFIRMED TRUE** — no Retry-After/cooldown enforcement or DB-coordinated failure suppression on revenue endpoints.

## Step C — Confirm endpoint contract expectations

Commands:
- `Get-Content -Path api-contracts/openapi/v1/attribution.yaml`
- `Get-Content -Path backend/app/api/attribution.py`

Contract expectations (GET /api/attribution/revenue/realtime):
- Headers on 200: `ETag`, `Cache-Control` (example `max-age=30`), `X-Correlation-ID`. Ref: `api-contracts/openapi/v1/attribution.yaml`.
- 304 supported with ETag. Ref: `api-contracts/openapi/v1/attribution.yaml`.
- Response schema fields required: `total_revenue`, `event_count`, `last_updated`, `data_freshness_seconds`, `verified`, `tenant_id` with optional `confidence_score`, `upgrade_notice`. Ref: `api-contracts/openapi/v1/attribution.yaml`.

Implementation status:
- `backend/app/api/attribution.py` sets `ETag` + `Cache-Control: max-age=30` and supports `If-None-Match` -> 304. However it returns stub data, does **not** read/write any cache table, and does **not** emit `X-Correlation-ID` header.

Hypothesis check:
- H3-4 (Contract/cache headers not implemented): **PARTIALLY REFUTED** — ETag/Cache-Control implemented, but cache semantics and correlation echo are not enforced, and payload freshness is stubbed.

## Step D — Confirm CI adjudication wiring

Commands:
- `Get-Content -Path .github/workflows/ci.yml`
- `Get-Content -Path docs/phases/phase_manifest.yaml`
- `Get-Content -Path .github/workflows/b060_phase2_adjudication.yml`

Findings:
- Primary required workflow appears to be `CI` (`.github/workflows/ci.yml`) running on push/PR to `main`.
- Phase gates are executed inside the `CI` workflow via the `phase-gates` job, which runs `python scripts/phase_gates/run_phase.py` for each phase in `docs/phases/phase_manifest.yaml`.
- `docs/phases/phase_manifest.yaml` currently lists B0.1–B0.4 and VALUE_* phases only; **no B0.6 Phase 3 gate exists**, so Phase 3 tests are not automatically executed by the phase-gates matrix.
- A dedicated workflow exists for B0.6 Phase 2 (`.github/workflows/b060_phase2_adjudication.yml`) running `pytest -v tests/test_b060_phase2_platform_connections.py`, but this is Phase 2 only.

Implication for Phase 3:
- To make Phase 3 tests merge-blocking, they must be wired into an existing required job (likely `CI` / `phase-gates`) or a new required check must be added in repository branch protection (not visible in repo). Further evidence from GitHub branch protection settings is required to prove required checks.

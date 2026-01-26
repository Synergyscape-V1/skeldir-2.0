# B0.6.0 Phase 0 Remediation Evidence Note

Date: 2026-01-26
Scope: Phase 0 only (canonical contract + route + schema alignment)

## Objective
Establish a canonical, versioned API surface for realtime revenue (`GET /api/v1/revenue/realtime`) with a truthful contract and implementation alignment, while preserving the legacy `/api/attribution/revenue/realtime` path as a deprecated alias to avoid breaking existing dependencies.

## Repo State (Post-Remediation)
- Commit SHA: cc35d09 (main)
- CI run URL (G0.5): https://github.com/Muk223/skeldir-2.0/actions/runs/21372639645

## Summary of Implementations (What Changed)

### 1) Canonical v1 revenue API (new)
**Intent:** Create the authoritative B0.6 interim endpoint and align its schema with a B0.6-compatible contract.
- Added new router: `backend/app/api/revenue.py`
  - `GET /api/v1/revenue/realtime` implemented.
  - Response model: `RealtimeRevenueV1Response` (new model file).
  - Interim semantics: `verified=false`, placeholder `tenant_id`, `data_as_of` present, no platform fetch, no caching.
  - Minimal auth guard: require `Authorization: Bearer <token>` (presence only).

**Evidence:**
- Router definition + handler: `backend/app/api/revenue.py:1`.
- Router mounted under `/api/v1`: `backend/app/main.py:63`.

### 2) Canonical revenue contract (new)
**Intent:** Provide contract-first spec for the canonical v1 endpoint.
- New contract source: `api-contracts/openapi/v1/revenue.yaml`.
  - Defines `GET /api/v1/revenue/realtime` with required fields: `tenant_id`, `interval`, `currency`, `revenue_total`, `verified`, `data_as_of` (nullable), `sources`.
  - Does **not** claim caching headers (ETag/Cache-Control) to stay truthful.

**Evidence:**
- Contract source: `api-contracts/openapi/v1/revenue.yaml:1`.

### 3) Schema alignment (new)
**Intent:** Ensure backend response model matches the new canonical contract.
- New model: `backend/app/schemas/revenue.py` with `RealtimeRevenueV1Response`.
- Model imported in schema registry: `backend/app/schemas/__init__.py`.
- Model check added to stub generator checklist: `scripts/generate-models.sh`.

**Evidence:**
- Model definition: `backend/app/schemas/revenue.py:1`.
- Schema registry import: `backend/app/schemas/__init__.py:11`.
- Stub model checklist: `scripts/generate-models.sh:43`.

### 4) Contract toolchain updated to include revenue bundle
**Intent:** Ensure Redocly bundling and CI bundle completeness include the new revenue contract.
- Added `revenue` to `api-contracts/redocly.yaml`.
- Updated bundling script to emit `revenue.bundled.yaml`: `scripts/contracts/bundle.sh`.
- Updated bundle completeness check list: `scripts/contracts/check_dist_complete.py`.
- Updated integration test pipeline expected bundle count: `scripts/integration_test_pipeline.sh`.
- Updated workflow summary message: `.github/workflows/contracts.yml`.

**Evidence:**
- Redocly config: `api-contracts/redocly.yaml:9`.
- Bundler: `scripts/contracts/bundle.sh:34`.
- Completeness list: `scripts/contracts/check_dist_complete.py:11`.
- Expected bundle count: `scripts/integration_test_pipeline.sh:17`.
- Workflow summary: `.github/workflows/contracts.yml:87`.

### 5) Legacy endpoint preserved, marked deprecated, and made truthful
**Intent:** Retain `/api/attribution/revenue/realtime` due to existing dependencies, but make the contract claims true and mark legacy as deprecated.
- OpenAPI deprecation flag: `api-contracts/openapi/v1/attribution.yaml`.
- Runtime behavior updated to match contract claims:
  - Minimal auth guard (`Authorization` required).
  - ETag + Cache-Control headers on 200.
  - 304 Not Modified when `If-None-Match` matches.
  - 401 Problem Details response (RFC7807) with `application/problem+json`.
- Added shared Problem Details helper: `backend/app/api/problem_details.py`.

**Evidence:**
- Deprecated flag: `api-contracts/openapi/v1/attribution.yaml:29`.
- Legacy handler headers + 304 + auth guard: `backend/app/api/attribution.py:32`.
- Problem details helper: `backend/app/api/problem_details.py:1`.

### 6) Contract scope mapping updated
**Intent:** Ensure contract enforcement recognizes the new v1 revenue surface.
- Added `/api/v1/revenue` to in-scope prefixes and spec mapping.

**Evidence:**
- Scope config: `backend/app/config/contract_scope.yaml:5`.

### 7) Tests added/adjusted
**Intent:** Verify canonical v1 schema and minimal auth; keep legacy contract test passing after auth guard.
- New test for v1 response shape + 401 auth: `backend/tests/test_b06_realtime_revenue_v1.py`.
- Updated contract semantics test to include Authorization header for legacy endpoint: `tests/contract/test_contract_semantics.py`.

**Evidence:**
- New test: `backend/tests/test_b06_realtime_revenue_v1.py:1`.
- Updated test header: `tests/contract/test_contract_semantics.py:195`.

## Evidence of Investigation (BH/RH)

### Blocker hypotheses (BH)
- **BH01 (Canonical path mismatch)**: Supported. No `/api/v1` route existed prior to change.
  - Evidence: `backend/app/main.py:61` (only `/api/attribution` before changes).
- **BH02 (Legacy schema mismatch)**: Supported.
  - Evidence: `backend/app/schemas/attribution.py:13`, `api-contracts/openapi/v1/attribution.yaml:63`.
- **BH03 (Toolchain anchored to attribution bundle)**: Supported (contract-first bundling from source YAMLs).
  - Evidence: `api-contracts/redocly.yaml:1`, `scripts/contracts/bundle.sh:1`.
- **BH04 (Header claims vs runtime)**: Supported (legacy contract claims ETag/Cache-Control, runtime did not).
  - Evidence: `api-contracts/openapi/v1/attribution.yaml:45`, `backend/app/api/attribution.py:31` (pre-change).

### Root-cause hypotheses (RH)
- **RH01 (Existing /api/v1 topology)**: Refuted (no /api/v1 routes found).
  - Evidence: `rg -n "api/v1" backend/app` (no routes found prior to adding).
- **RH02 (Contract-first bundling)**: Supported.
  - Evidence: `api-contracts/redocly.yaml:1`, `scripts/contracts/bundle.sh:1`.
- **RH03 (Code-first OpenAPI generation)**: Refuted (no FastAPI OpenAPI generation scripts used for bundle).
  - Evidence: `scripts/contracts/bundle.sh:1` and CI workflow references.
- **RH04 (Legacy endpoint dependencies)**: Supported; many references across frontend/tests/docs.
  - Evidence: `rg -n "/api/attribution/revenue/realtime" frontend tests docs`.
- **RH05 (Security mismatch enforced by validators)**: Inconclusive (validators run, but only checked bundles used in this pass).

## Commands Run (local)
- `git status --porcelain=v1`
- `git rev-parse HEAD`
- `git branch --show-current`
- `rg -n "include_router|APIRouter|@router" backend/app`
- `rg -n "api/v1|/api/v1" backend/app`
- `rg -n "/api/attribution/revenue/realtime" frontend tests docs`
- `npx @redocly/cli bundle attribution --config=redocly.yaml --output=dist/openapi/v1/attribution.bundled.yaml --ext yaml --dereferenced`
- `npx @redocly/cli bundle revenue --config=redocly.yaml --output=dist/openapi/v1/revenue.bundled.yaml --ext yaml --dereferenced`
- `npx @openapitools/openapi-generator-cli validate -i api-contracts/dist/openapi/v1/revenue.bundled.yaml`
- `npx @openapitools/openapi-generator-cli validate -i api-contracts/dist/openapi/v1/attribution.bundled.yaml`
- `python -c "... app.openapi() ..."` (verified `/api/v1/revenue/realtime` route is present)
- ASGI request to `/api/v1/revenue/realtime` (validated response keys)

## Gate Checks (Phase 0)
- **G0.1 Routing gate:** PASS. `/api/v1/revenue/realtime` appears in OpenAPI (`python -c` in backend).
- **G0.2 Schema gate:** PASS. Response contains `tenant_id`, `interval`, `currency`, `revenue_total`, `verified`, `data_as_of`, `sources` (ASGI request).
- **G0.3 OpenAPI alignment gate:** PASS for revenue + attribution bundles (openapi-generator-cli validate).
- **G0.4 Drift gate:** PASS as **legacy retained and deprecated**; references remain intentionally.
- **G0.5 CI gate:** PASS. https://github.com/Muk223/skeldir-2.0/actions/runs/21372639645

## Files Added / Modified
**Added**
- `backend/app/api/problem_details.py`
- `backend/app/api/revenue.py`
- `backend/app/schemas/revenue.py`
- `api-contracts/openapi/v1/revenue.yaml`
- `api-contracts/dist/openapi/v1/revenue.bundled.yaml`
- `backend/tests/test_b06_realtime_revenue_v1.py`

**Modified**
- `backend/app/api/attribution.py`
- `backend/app/main.py`
- `backend/app/schemas/__init__.py`
- `backend/app/config/contract_scope.yaml`
- `api-contracts/openapi/v1/attribution.yaml` (deprecated legacy path)
- `api-contracts/redocly.yaml`
- `scripts/contracts/bundle.sh`
- `scripts/contracts/check_dist_complete.py`
- `scripts/generate-models.sh`
- `scripts/integration_test_pipeline.sh`
- `.github/workflows/contracts.yml`
- `.github/workflows/mock-contract-validation.yml`
- `tests/contract/test_contract_semantics.py`

## Known Limitations / Non-Goals (Phase 0)
- No JWT validation, tenant derivation, or RLS enforcement added (minimal auth presence only).
- No platform fetch or Postgres caching for realtime revenue.
- No runtime for 429/500 paths added (contract already defines them).
- Only the new revenue bundle was added under `api-contracts/dist/` to satisfy phase gates; other bundles remain as previously tracked artifacts.

## Compatibility Decision
- Legacy endpoint `/api/attribution/revenue/realtime` kept to avoid breaking existing code/tests. It is explicitly marked `deprecated: true` in the attribution contract.

## Evidence Pointers (High-signal)
- Canonical v1 handler: `backend/app/api/revenue.py:1`
- Canonical v1 contract: `api-contracts/openapi/v1/revenue.yaml:1`
- Canonical model: `backend/app/schemas/revenue.py:1`
- Contract scope mapping: `backend/app/config/contract_scope.yaml:5`
- Legacy deprecation: `api-contracts/openapi/v1/attribution.yaml:29`
- Legacy headers/auth guard: `backend/app/api/attribution.py:32`
- Problem Details helper: `backend/app/api/problem_details.py:1`
- Bundler changes: `scripts/contracts/bundle.sh:34`
- Redocly config: `api-contracts/redocly.yaml:9`

## Next Required Actions (outside Phase 0)
- Run full contract bundle + validation pipeline in CI.
- Decide whether to add a Prism revenue mock and update mock docs if needed.
- Implement Phase 1+ behaviors (auth/JWT/tenant/RLS, platform fetch, PG cache) only after contract surface is stable.

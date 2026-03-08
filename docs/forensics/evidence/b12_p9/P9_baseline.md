# B1.2-P9 Baseline Forensic Map

Date: 2026-03-08  
Scope: pre-implementation inventory for P9 only.

## Inputs
- `docs/forensics/B1.2_Context_Inventory_Report.md`
- `C:\Users\ayewhy\Box\Delete Now\CI Pipleine Resart\49. Linearly hierarchical B1.2 implementation plan.md`
- Runtime captures in `docs/forensics/evidence/b12_p9/runtime/`

## 1) Existing integration infrastructure

### What exists today
- Docker E2E topology exists with Postgres + API + worker in `docker-compose.e2e.yml`:
  - `postgres` service: `docker-compose.e2e.yml:2`
  - `api` service (`uvicorn`): `docker-compose.e2e.yml:34`, `docker-compose.e2e.yml:63`
  - `worker` service (`celery -A app.celery_app worker`): `docker-compose.e2e.yml:80`, `docker-compose.e2e.yml:106`
- CI has multiple integration/security jobs with Postgres service + migration bootstrapping:
  - `Phase 1 Runtime Conformance`: `.github/workflows/ci.yml:384`
  - `JWT Tenant Context Invariants`: `.github/workflows/ci.yml:411`
  - `B1.2 P6 RBAC Proofs`: `.github/workflows/ci.yml:463`
  - `B1.2 P7 Worker Coherence Proofs`: `.github/workflows/ci.yml:507`
  - `B1.2 P8 Error Contract Proofs`: `.github/workflows/ci.yml:558`
  - Postgres services / migrations in those jobs: `.github/workflows/ci.yml:416`, `.github/workflows/ci.yml:448`, `.github/workflows/ci.yml:468`, `.github/workflows/ci.yml:500`, `.github/workflows/ci.yml:512`, `.github/workflows/ci.yml:545`, `.github/workflows/ci.yml:596`
- Existing tests prove subsystems, but no single dedicated P9 composed suite/job yet.

### H01 status
- **Validated**: there is no dedicated one-run P9 system-proof suite named/structured as EG9 authority.

## 2) Is Celery run as a real subprocess in CI?

- Yes, real subprocess topology is exercised by integration tests that call `subprocess.Popen(...)` for a worker process:
  - `backend/tests/test_b12_p1_tenant_context_safety.py:149`
  - `backend/tests/integration/test_b12_p7_worker_revocation_runtime.py:85`
- Those tests are included in CI:
  - `backend/tests/integration/test_b12_p7_worker_revocation_runtime.py` in P7 job: `.github/workflows/ci.yml:554`

### H04 status
- **Refuted** (for capability): real subprocess worker execution exists.
- **Still open for P9**: this is not yet composed with auth/RBAC/webhook in one orchestrated EG9 run.

## 3) Deterministic seed helpers for two tenants + multi-tenant user + tenant-scoped data

- Two-tenant/multi-tenant role-divergence seeding exists in RBAC tests:
  - Seed helper: `backend/tests/test_b12_p6_rbac_enforcement.py:40`
  - Explicit multi-tenant divergence scenario (same user, tenant A admin, tenant B viewer): `backend/tests/test_b12_p6_rbac_enforcement.py:591`
- Tenant-scoped worker side-effect table operation exists:
  - Task write path: `backend/app/tasks/observability_test.py:82`
  - Task entrypoints used for worker proofs: `backend/app/tasks/observability_test.py:113`, `backend/app/tasks/observability_test.py:128`

### H03 status
- **Partial**: seed ingredients exist and are deterministic, but not yet assembled into one P9 scenario.

## 4) Stable endpoint candidates for RBAC and tenant isolation proofs

- Admin-only RBAC proof endpoint (403 for viewer):
  - `/api/auth/admin/rbac-check`: `backend/app/api/auth.py:310`
- Tenant-scoped read candidates:
  - `/api/attribution/revenue/realtime`: `backend/app/api/attribution.py:35`
  - `/api/v1/revenue/realtime`: `backend/app/api/revenue.py:31`
- Tenant-scoped write candidate:
  - `/api/auth/admin/membership-role`: `backend/app/api/auth.py:334`
- Token issuance/refresh endpoints:
  - `/api/auth/login`: `backend/app/api/auth.py:71`
  - `/api/auth/refresh`: `backend/app/api/auth.py:162`

## 5) Webhook signed-accept / signed-deny readiness

- Tenant-key + HMAC auth is explicit:
  - `tenantKeyAuth` header auth: `backend/app/api/webhooks.py:53`
  - central verifier path: `backend/app/api/webhooks.py:140`
  - Stripe webhook endpoint: `backend/app/api/webhooks.py:415`
- Runtime tests already prove signed accept and signed reject:
  - Stripe success + invalid signature: `backend/tests/test_b045_webhooks.py:238`, `backend/tests/test_b045_webhooks.py:272`, `backend/tests/test_b045_webhooks.py:274`
  - Shopify invalid signature 401: `backend/tests/test_b045_webhooks.py:148`, `backend/tests/test_b045_webhooks.py:162`

### H05 status
- **Refuted** (capability): non-JWT webhook modality is operational and test-covered.
- **Still open for P9**: not yet proven in the same composed EG9 system run.

## 6) Live branch protection required checks on `main` (GitHub enforcement plane)

Source of truth (live API, captured 2026-03-08):
- `docs/forensics/evidence/b12_p9/runtime/main_required_status_checks_live.json`
- `docs/forensics/evidence/b12_p9/runtime/main_branch_protection_live.json`

Observed:
- `strict = true`
- Current required contexts include:
  - `Phase 1 Runtime Conformance`
  - `JWT Tenant Context Invariants`
  - `B1.2 P6 RBAC Proofs`
  - `B1.2 P7 Worker Coherence Proofs`
  - `B1.2 P8 Error Contract Proofs`
  - plus existing non-B1.2 platform checks
- **Missing:** `B1.2 P9 E2E System Proofs` (not present in live required checks as of capture time).

### H06 status
- **Validated**: EG9 required status check is not present in live main branch protection.

## Baseline conclusion

- P9 is **not complete** at baseline.
- Blocking deltas:
  1. No single composed EG9 suite/job that proves all required invariants in one run.
  2. No EG9 required status check on live `main` branch protection.

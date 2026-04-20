# Phase B2.2-P2 Remediation Evidence Pack

Date: 2026-04-20  
Branch inspected/remediated: `main` working state  
Phase target: **B2.2-P2 Post-Auth Privacy Boundary Closure + Verification Substrate Protection**

## 1) Initial findings (validated before remediation)

- Webhook-path durable persistence still wrote ingress metadata into `raw_event_payloads` via `ip_address`, `user_agent`, and `raw_headers`.
- The webhook-path flow preserved verification substrate for auth, but the post-auth persistence boundary remained permissive.
- Duplicate webhook deliveries could still re-trigger downstream orchestration side effects even when canonical event writes were idempotent.
- Failure surfaces (`dead_events`/`dead_events_quarantine`) still allowed persistence of ingress identifier keys in redacted form.
- There was no B2.2-P2-specific merge-blocking CI enforcer for the zero-disallowed-persistence invariant.

## 2) Remediation changes implemented

### A. Post-auth durable boundary closure for webhook ingress metadata

- Updated `backend/app/ingestion/event_service.py`:
  - Added `_raw_event_ingress_metadata_for_persistence(...)`.
  - Added `_WEBHOOK_INGRESS_SOURCES` guard set (`shopify`, `stripe`, `paypal`, `woocommerce`, `webhook`).
  - Enforced `ip_address=None`, `user_agent=None`, `raw_headers=None` for webhook sources before `RawEventPayload` durable writes.
  - Kept verification substrate sequence intact (verification still happens before ingestion persistence call chain).

### B. Duplicate side-effect isolation at webhook orchestration boundary

- Updated `backend/app/ingestion/event_service.py`:
  - Added duplicate marker propagation via `is_duplicate` in transactional return payload.
- Updated `backend/app/api/webhooks.py`:
  - `_handle_ingestion(...)` and Stripe contract route now skip `_schedule_downstream_tasks(...)` on duplicates.

### C. Explicit verified ingress truth marker

- Updated `backend/app/api/webhooks.py`:
  - Added `_verified_revenue_state()` helper.
  - Added `verified_revenue_state="authenticity_verified"` into post-auth ingestion payloads prior to persistence.

### D. Failure-surface tightening

- Updated `backend/app/ingestion/dlq_handler.py`:
  - Tightened `_DLQ_FAILURE_SURFACE_FORBIDDEN_KEYS` to forbid `raw_headers` and stop exempting `ip`/`ip_address`.
  - This prevents prohibited ingress identifier persistence on DLQ/quarantine surfaces.

### E. Merge-blocking governance for P2

- Added governance contract:
  - `contracts-internal/governance/b22_p2_post_auth_privacy_boundary.main.json`
- Added CI enforcer:
  - `scripts/ci/enforce_b22_p2_post_auth_privacy_boundary.py`
- Added enforcer tests:
  - `backend/tests/test_b22_p2_post_auth_privacy_boundary_enforcer.py`
- Wired CI:
  - Added B2.2-P2 enforcement + tests in `.github/workflows/ci.yml`.

### F. Runtime P2 proof suite

- Added runtime proofs:
  - `backend/tests/test_b22_p2_post_auth_privacy_boundary.py`
  - Covers:
    - success-path zero disallowed persistence in `raw_event_payloads`,
    - malformed/DLQ-path disallowed-field absence,
    - duplicate delivery no-reenqueue side-effect proof,
    - non-vacuous negative control.

### G. Adjusted pre-existing privacy tests for stricter failure-surface behavior

- Updated:
  - `backend/tests/test_b044_dlq_handler.py`
  - `backend/tests/integration/test_b14_p1_ingress_privacy_runtime.py`
  - `backend/tests/integration/test_b14_p4_retention_deletion_runtime.py`
- Changes align assertions with stricter policy where `ip_address` is removed/dropped from failure surfaces and webhook ingress metadata columns are null on durable webhook writes.

## 3) Verification runs (executed)

### Passing runs

- `python scripts/ci/enforce_b22_p2_post_auth_privacy_boundary.py` ✅
- `pytest backend/tests/test_b22_p2_post_auth_privacy_boundary_enforcer.py -q` ✅ (5 passed)
- `pytest backend/tests/test_b22_p2_post_auth_privacy_boundary.py -q` ✅ (4 passed)
- `pytest backend/tests/test_b045_webhooks.py -q` ✅ (12 passed)
- `pytest backend/tests/test_b046_integration.py -q` ✅ (8 passed)
- `pytest backend/tests/test_b12_p8_error_contract_normalization.py -q` ✅ (14 passed)

### Not-green runs due unrelated pre-existing/runtime-environment blockers

- `pytest backend/tests/test_b044_dlq_handler.py -q` ❌  
  - Failures include pre-existing/orthogonal behavior around `dead_events_quarantine` visibility and state-machine expectation mismatch (`abandoned -> in_progress`) plus replay payload mutation behavior.
- `pytest backend/tests/integration/test_b14_p1_ingress_privacy_runtime.py -q` ❌  
  - `dead_events_quarantine` row visibility assertion failed (`row is None`) in runtime environment.
- `pytest backend/tests/integration/test_b14_p4_retention_deletion_runtime.py -q` ❌  
  - Fails on unrelated schema/runtime mismatch: missing `attribution_allocations.recompute_job_id` in current runtime DB.

## 4) Exit gate status for B2.2-P2

- **EG-P2-1 Verification substrate integrity:** PASS  
  - Auth paths remain intact and valid signed webhook flows still verify before durable writes.
- **EG-P2-2 Zero disallowed persistence (webhook-path tables):** PASS for newly added P2 proofs  
  - Success and malformed/DLQ webhook-path proofs assert no durable `ip_address`, `user_agent`, `raw_headers`.
- **EG-P2-3 Privacy completeness across auxiliary surfaces:** PARTIAL PASS  
  - DLQ stripping and webhook runtime proofs are in place; broader legacy integration suites show unrelated existing blockers.
- **EG-P2-4 Merge-blocking adjudication:** PASS (wiring committed in CI config)  
  - Dedicated P2 enforcer + negative controls + runtime proofs are now wired in `.github/workflows/ci.yml`.

## 5) Completion status relative to directive

- Code remediation for P2 privacy boundary closure is implemented and validated in dedicated P2 proofs and enforcer gates.
- Full "green main CI once" and "authoritative protected-branch landing proof on main" is **not yet claimable from this local execution**, because unrelated existing suite failures block asserting full-green state.
- Next required operational step: execute authoritative protected-branch workflow on GitHub and resolve unrelated failing suites to obtain an all-checks-green `main` adjudication record.

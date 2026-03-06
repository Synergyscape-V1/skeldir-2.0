# P7 v2 Baseline (Pre-Remediation)

Date: 2026-03-06  
Branch inspected: `b12-p6-v5-default-deny-schemes`  
Scope: Worker-plane authority/revocation enforcement, envelope transport, tenant-task signature purity, and zero-I/O revocation proof quality.

## Hypothesis Validation Summary

- H01 (`TESTING`/env legacy bypass in `TenantTask`): **Validated**.
- H02 (envelope in kwargs + tenant/user reinjection into business kwargs): **Validated**.
- H03 (revocation enforcement conditionally disabled in tests/env): **Validated**.
- H04 (zero-I/O steady-state proof ambiguity): **Validated (partial proof exists, but gap remains)**.

## 1) Env-Gated Bypass Locations

### A. TenantTask legacy envelope bypass (H01)

- `backend/app/tasks/tenant_base.py:29`
  - `legacy_mode = os.getenv("TESTING") == "1" and os.getenv("SKELDIR_B12_P7_STRICT_ENVELOPE") != "1"`
- `backend/app/tasks/tenant_base.py:30-34`
  - Envelope absence is tolerated in `legacy_mode`; otherwise raises.

### B. Revocation enforcement bypasses (H03)

- `backend/app/security/auth.py:357` (`revocation_enforcement_enabled`)
- `backend/app/security/auth.py:358`
  - bypass when `CONTRACT_TESTING=1`
- `backend/app/security/auth.py:360`
  - bypass when `SKELDIR_B12_P5_DISABLE_REVOCATION_CHECKS=1`
- `backend/app/security/auth.py:362`
  - bypass when `TESTING=1` unless `SKELDIR_B12_P5_ENABLE_REVOCATION_IN_TESTS=1`

### C. CI/test harness dependency on bypass flags

- `.github/workflows/ci.yml:485,530`
  - sets `SKELDIR_B12_P5_ENABLE_REVOCATION_IN_TESTS=1`
- `.github/workflows/ci.yml:531`
  - sets `SKELDIR_B12_P7_STRICT_ENVELOPE=1`
- `backend/tests/integration/test_b12_p7_worker_revocation_runtime.py:40-41`
  - sets both strict/revocation test toggles
- `backend/tests/test_b12_p7_enqueue_and_envelope.py:63-64`
  - strict envelope test relies on env flag

## 2) Current Envelope Transport + Injection Path (H02)

### A. Producer transport is kwargs, not headers

- `backend/app/tasks/enqueue.py:40-42`
  - `authority_envelope` inserted into `task_kwargs`
- `backend/app/tasks/enqueue.py:57-58`
  - `tenant_task_signature` calls `task.si(**task_kwargs)` / `task.s(**task_kwargs)`
- `backend/app/tasks/enqueue.py:72-75`
  - `enqueue_tenant_task` calls `task.apply_async(kwargs=task_kwargs, ...)`

### B. Worker consumes kwargs, then reinjects authority-derived fields into kwargs

- `backend/app/tasks/tenant_base.py:27`
  - reads `authority_envelope` from `kwargs.pop(...)`
- `backend/app/tasks/tenant_base.py:60-62`
  - reinjects `tenant_id`, `user_id`, `correlation_id` into business kwargs
- `backend/app/tasks/tenant_base.py:66`
  - uses injected `kwargs["user_id"]` for GUC binding

### C. No header-driven authority path currently used by TenantTask

- `backend/app/tasks/tenant_base.py` contains no `self.request.headers` read for authority envelope extraction.

## 3) Tenant-Scoped Task Signature Audit (H02/H03 follow-on)

Audit source of truth: `backend/app/tasks/enqueue.py::TENANT_SCOPED_TASK_NAMES`.

All 10 tenant-scoped tasks currently include authority fields in function signatures (`tenant_id` and usually `user_id`):

1. `app.tasks.attribution.recompute_window`
- `backend/app/tasks/attribution.py:499-507`
- params include `tenant_id`, `user_id`

2. `app.tasks.llm.route`
- `backend/app/tasks/llm.py:89-98`
- params include `tenant_id`, `user_id`

3. `app.tasks.llm.explanation`
- `backend/app/tasks/llm.py:147-156`
- params include `tenant_id`, `user_id`

4. `app.tasks.llm.investigation`
- `backend/app/tasks/llm.py:209-218`
- params include `tenant_id`, `user_id`

5. `app.tasks.llm.budget_optimization`
- `backend/app/tasks/llm.py:271-280`
- params include `tenant_id`, `user_id`

6. `app.tasks.maintenance.refresh_matview_for_tenant`
- `backend/app/tasks/maintenance.py:120-125`
- params include `tenant_id`, `user_id`

7. `app.tasks.maintenance.scan_for_pii_contamination`
- `backend/app/tasks/maintenance.py:198-202`
- params include `tenant_id`, `user_id`

8. `app.tasks.maintenance.enforce_data_retention`
- `backend/app/tasks/maintenance.py:272-276`
- params include `tenant_id`, `user_id`

9. `app.tasks.matviews.refresh_single`
- `backend/app/tasks/matviews.py:228-236`
- params include `tenant_id`, `user_id`

10. `app.tasks.matviews.refresh_all_for_tenant`
- `backend/app/tasks/matviews.py:281-287`
- params include `tenant_id`, `user_id`

Observation: this confirms signature pollution is systemic for all tenant-scoped task bodies.

## 4) Zero-I/O Revocation Proof Audit (H04)

### A. Positive zero-DB assertions exist (in-process)

- `backend/tests/test_b12_p5_revocation_substrate.py:333`
  - `test_http_revocation_hot_path_has_zero_db_lookups_after_warmup`
- `backend/tests/test_b12_p5_revocation_substrate.py:350`
  - `test_worker_revocation_hot_path_has_zero_db_lookups_after_warmup`
- shared SQL counter helper:
  - `backend/tests/test_b12_p5_revocation_substrate.py:317`

### B. Real-worker-process coverage gap for zero-I/O proof

- Existing P7 real-worker revocation integration test:
  - `backend/tests/integration/test_b12_p7_worker_revocation_runtime.py`
- This test proves pre-side-effect revocation block in subprocess worker, but does **not** assert zero revocation-table DB lookups after warmup.

### C. Negative-control gap for forced DB hot path

- `assert_access_token_active` contains forced DB path flag:
  - `backend/app/security/auth.py:370` (`SKELDIR_B12_P5_FORCE_DB_REVOCATION_HOT_PATH`)
- No test usage found for this flag in `backend/tests` (repo grep), so there is no explicit failing/positive paired proof for zero-I/O vs forced DB mode.

## Baseline Conclusion

Current state confirms the two disqualifiers raised in this directive:

1. Env-gated legacy execution bypass and env-gated revocation relaxation paths are real and active.
2. Authority transport is kwargs-based with base-task reinjection into business kwargs, and tenant-scoped task signatures are authority-polluted.

Additionally, while zero-I/O hot-path assertions exist, they are not coupled to a real worker-process proof and lack an explicit forced-DB negative-control pair for the same proof objective.

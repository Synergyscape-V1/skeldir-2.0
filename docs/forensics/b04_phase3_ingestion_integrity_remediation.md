# B0.4 Phase 3 Remediation Ledger: Privacy Ingestion Integrity + Customer-Profile Performance

## 1) Authority Update (2026-02-11)
- EG3.4 is redefined to customer-centric sustained-rate tests:
  - `EG3_4_Test1_Month6`: `29 rps` for `60s`, `p95 < 2s`, `0% errors`, integrity preserved.
  - `EG3_4_Test2_Month18`: `46 rps` for `60s`, same pass criteria.
  - `EG3_4_Test3_SustainedOps`: `5 rps` for `300s`, same pass criteria plus no degradation.
- Legacy gate `10k < 10s` is removed from CI gate authority and harness logic.

## 2) Hypothesis Closure Matrix

### H3-1 Contract drift
- **Result:** CONFIRMED then remediated.
- **Evidence before remediation:** `scripts/r3/ingestion_under_fire.py` and `.github/workflows/r3-ingestion-under-fire.yml` encoded `R3_PERF_N=10000` + `R3_PERF_MAX_SECONDS=10`.
- **Remediation:** replaced with explicit EG3.4 profile env vars and scenario names in:
  - `scripts/r3/ingestion_under_fire.py`
  - `.github/workflows/r3-ingestion-under-fire.yml`
  - `.github/workflows/r7-final-winning-state.yml`
  - `scripts/r3/render_r3_summary.py`

### H3-2 Harness mismatch
- **Result:** CONFIRMED then remediated.
- **Remediation details:**
  - Added first-class scenarios:
    - `EG3_4_Test1_Month6`
    - `EG3_4_Test2_Month18`
    - `EG3_4_Test3_SustainedOps`
  - Added per-request latency collection (`p50`, `p95`) under sustained-rate load generation.
  - Added per-test DB truth checks bound to each test window:
    - PII hit scan
    - duplicate canonical key scan
    - canonical and DLQ counts for profile keyset
    - malformed/PII DLQ totals and replay idempotency checks

### H3-3 Measurement validity
- **Result:** CONFIRMED then remediated.
- **Remediation details:**
  - Added `EG3_5_NullBenchmark` scenario.
  - Null benchmark now uses the same client stack/concurrency model as EG3.4 tests (`httpx.AsyncClient` + asyncio semaphore).
  - Gate semantics:
    - pass: environment can sustain configured null benchmark floor (`>=50 rps`, `60s`, zero errors).
    - fail: verdict marked `invalid_measurement_environment` and harness exits with measurement-invalid status.

### H3-4 Throughput-integrity coupling risk
- **Result:** Addressed in harness logic; requires runtime execution proof.
- **Implemented checks per EG3.4 scenario:**
  - idempotency uniqueness under replay load
  - malformed and PII routing to DLQ
  - zero PII persistence scan
  - duplicate key audit in canonical table for test window
  - resource snapshots via `pg_stat_activity` before/after each profile test

### H3-5 Bottleneck hypotheses under revised gate
- **Result:** Instrumentation now supports falsifiable diagnosis; runtime evidence pending execution.
- **Data captured per profile test:**
  - achieved RPS
  - request counts
  - `p50`/`p95` latency
  - error counts/rate
  - connection snapshot before/after
  - degradation check for sustained profile

## 3) CI and Human-Facing Gate Authority

### CI gate surfaces updated
- `.github/workflows/r3-ingestion-under-fire.yml`
- `.github/workflows/r7-final-winning-state.yml`

### Human-readable artifacts updated
- `scripts/r3/render_r3_summary.py` now renders EG3.1-EG3.5 matrix from verdict blocks:
  - `EG3_5_NullBenchmark`
  - `EG3_4_Test1_Month6`
  - `EG3_4_Test2_Month18`
  - `EG3_4_Test3_SustainedOps`

## 4) Required Structured Verdict Fields (Enforced by Harness Output)
- `duration_s`
- `target_rps`
- `target_request_count`
- `observed_request_count`
- `achieved_rps`
- `latency_p50_ms`
- `latency_p95_ms`
- `http_error_count` and timeout/connection error counts
- DB truth counts (canonical, DLQ, duplicates, PII hits)
- `passed` boolean

## 5) Current Completion State
- Code and contract authority have been updated to revised EG3.4/EG3.5 semantics.
- Runtime adjudication for "CI green on main" is not asserted in this document and must be proven by executing CI with the updated harness/workflows.

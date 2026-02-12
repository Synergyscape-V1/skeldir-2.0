# B0.4 Phase 4 Multi-Tenancy & Security Closure Evidence

Date: 2026-02-12  
Branch target: `main`  
Execution mode: local provisioned Postgres with Phase-4 execution path enabled in `scripts/phase_gates/b0_4_gate.py`

## 1) System State Before This Corrective Pass

The prior executed state had two distinct facts:

- Phase-4 probe coverage gap had existed and was fail-closed:
  - `investigation_jobs: missing policy coverage cmds=[]`
- After that gap was fixed, B0.4 still failed in R3 aggregate with:
  - `SCENARIOS_EXECUTED=26`
  - `ALL_SCENARIOS_PASSED=False`

Immediate blocker at start of this pass:

- B0.4 summary still reported failure sourced from `python scripts/r3/ingestion_under_fire.py`.

## 2) Investigation and Root Cause Findings

### 2.1 Gate truth reproduction (CI-shaped env)
Executed:

- `python scripts/phase_gates/b0_4_gate.py`

with:

- `DATABASE_URL=postgresql://app_user:***@127.0.0.1:5432/skeldir_phase4`
- `MIGRATION_DATABASE_URL=postgresql://migration_owner:***@127.0.0.1:5432/skeldir_phase4`
- `OPS_DATABASE_URL=postgresql://app_ops:***@127.0.0.1:5432/skeldir_phase4`
- `EXPECTED_RUNTIME_DB_USER=app_user`
- `SKELDIR_TEST_SECRET=SKELDIR_TEST_SECRET_LOCAL_PHASE4`

Observed:

- Phase-4 probe artifacts were passing (EG4.1–EG4.6 pass; runtime identity verified).
- R3 failed early at `S3_MalformedStorm_N50` with:
  - `DLQ_ROWS_CREATED=100`
  - expected scenario invariant was `dlq == n` (for `n=50`).

### 2.2 Why `S3_MalformedStorm_N50` failed
Root cause isolated in `scripts/r3/ingestion_under_fire.py`:

- Scenario keys are deterministic from `candidate_sha`.
- Local default `candidate_sha` was static (`"local"`).
- Re-running against the same provisioned DB reuses identical key sets, so DLQ counts accumulate across runs and produce false negatives.

This is a clean-room reproducibility bug in local repeated execution, not a tenant boundary breach.

## 3) Corrective Changes Implemented in This Pass

### 3.1 R3 local clean-room key scoping fix
Updated: `scripts/r3/ingestion_under_fire.py`

- Changed `candidate_sha` fallback behavior:
  - before: static default `"local"`
  - now: dynamic default `"local-{epoch_seconds}"`
- CI behavior remains deterministic because `CANDIDATE_SHA`/`GITHUB_SHA` still take precedence.
- Local repeated runs now generate distinct deterministic key spaces, preventing stale-row accumulation from invalidating scenarios.

## 4) Post-Fix Execution Evidence

### 4.1 B0.4 gate result
Artifact: `backend/validation/evidence/phases/b0_4_summary.json`

- `status = "success"`
- timestamp: `2026-02-12T20:13:10.271081+00:00`

### 4.2 R3 harness aggregate
Artifact: `backend/validation/evidence/phases/b0_4_r3_harness.log`

- `SCENARIOS_EXECUTED=26`
- `ALL_SCENARIOS_PASSED=True`
- Logged run scope confirms non-static local candidate seed:
  - `candidate_sha: "local-1770920486"`

### 4.3 Phase-4 probe remains passing under app runtime identity
Artifact: `backend/validation/evidence/security/phase4_gate_summary.json`

- `eg4_1_table_discovery.pass = true`
- `eg4_2_rls_force_coverage.pass = true`
- `eg4_3_runtime_identity.pass = true`
- `eg4_4_context_fail_closed.pass = true`
- `eg4_5_secret_scan.pass = true`
- `eg4_6_dlq_two_lane.pass = true`

Runtime identity evidence in artifact:

- runtime: `app_user` (non-superuser, no bypass)
- ops: `app_ops` (segregated role)
- migration: `migration_owner`

### 4.4 Explicit discovery proof for required tables
Artifact: `backend/validation/evidence/security/phase4_tenant_tables.json`

Verified:

- `llm_api_calls` present with:
  - `scope="tenant_id"`, `rls_enabled=true`, `force_rls=true`, `policy_cmds=["ALL"]`
- `investigation_jobs` present with:
  - `policy_cmds=["ALL"]`, `policy_count=1`, `rls_enabled=true`, `force_rls=true`

## 5) CI Adjudication (Clean-Room Evidence)

Canonical CI run (GitHub Actions clean-room):

- Run ID: `21962179752`
- URL: `https://github.com/Muk223/skeldir-2.0/actions/runs/21962179752`
- Head SHA: `2377a75bbcbc5dd588dd93d771b88f03824fa9e7`
- Conclusion: `success`

Captured from CI artifact store (`phase-B0.4-evidence`):

- `backend/validation/evidence/security/phase4_tenant_tables.json`
- `backend/validation/evidence/security/phase4_gate_summary.json`
- `backend/validation/evidence/phases/b0_4_summary.json`

Final gate values from CI artifact `phase4_gate_summary.json`:

- `eg4_1_table_discovery.pass = true` (tenant_table_count=`30`)
- `eg4_2_rls_force_coverage.pass = true`
- `eg4_3_runtime_identity.pass = true` (`runtime=app_user`, `ops=app_ops`, `migration=migration_owner`; all non-superuser and no bypass RLS)
- `eg4_4_context_fail_closed.pass = true`
- `eg4_5_secret_scan.pass = true` (`db_hit_count=0`, `file_hit_count=0`)
- `eg4_6_dlq_two_lane.pass = true`
- `eg4_7_phase3_perf_non_regression.pass = true` (delegated to R3 harness from B0.4 gate)

Explicit required-table verification from CI artifact `phase4_tenant_tables.json`:

- `llm_api_calls` is present in catalog discovery with `scope=tenant_id`, `rls_enabled=true`, `force_rls=true`, `policy_cmds=["ALL"]`.
- `investigation_jobs` is present with `policy_cmds=["ALL"]`, `policy_count=1`, `rls_enabled=true`, `force_rls=true`.

Global coherence checks in this same run are green, including prior red vectors:

- `validate-schema-authority`: `success`
- `b0545-convergence`: `success`
- `Phase Gates (B0.3)`: `success`
- `Phase Chain (B0.4 target)`: `success`
- workflow `CI`: `success`

## 6) Completion Status (Current Truth)

Program-level closure state:

- Remediation branch CI is fully green in clean-room adjudication.
- PR to `main` is open and merge-clean: `https://github.com/Muk223/skeldir-2.0/pull/81`.
- Phase 4 is technically closed at enforcement/probe level and system-coherent at repository CI level on the remediation head.

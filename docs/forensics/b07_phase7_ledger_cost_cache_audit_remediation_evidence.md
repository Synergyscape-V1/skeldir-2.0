# B0.7 Phase 7 Remediation Evidence: Ledger, Cost, Cache, and Audit Sufficiency

## Scope

This remediation closes Phase 7 blockers for:

- runtime identity access to tenant-scoped LLM ledger/audit tables
- complete ledger and audit emission across provider-boundary outcomes
- deterministic cost correctness and unit invariants
- raw-to-rollup reconciliation proof
- semantic cache functional plus performance-bound behavior
- explicit no-raw-prompt persistence-by-default proof

## Findings

1. Runtime-role grant coverage for LLM tables was environment-sensitive and not explicitly guaranteed for `app_user` in all runtime paths.
2. `llm_api_calls` write-path was centralized, but `llm_call_audit` was not emitted for all boundary outcomes.
3. Existing tests covered many controls, but did not provide a unified Phase 7 proof bundle for reconciliation and cache performance thresholds with anti-cheat controls.

## Remediations Implemented

1. Runtime grants migration
- File: `alembic/versions/007_skeldir_foundation/202602141530_b07_p7_llm_runtime_grants.py`
- Adds explicit grants on required LLM tenant tables:
  - `app_rw`: `SELECT, INSERT, UPDATE`
  - `app_user`: `SELECT, INSERT, UPDATE`
  - `app_ro`: `SELECT`
- Applies to:
  - `llm_api_calls`
  - `llm_call_audit`
  - `llm_monthly_costs`
  - `llm_breaker_state`
  - `llm_hourly_shutoff_state`
  - `llm_monthly_budget_state`
  - `llm_budget_reservations`
  - `llm_semantic_cache`

2. Ledger + audit write-path unification
- File: `backend/app/llm/provider_boundary.py`
- Adds `_write_call_audit(...)` and invokes it on all terminal outcomes:
  - provider kill switch blocked
  - hourly shutoff blocked
  - monthly cap blocked
  - breaker-open blocked
  - cache-hit success
  - provider success
  - timeout failed
  - provider exception failed
- Uses prompt fingerprint + minimal metadata only. No raw prompt text persisted.

3. Phase 7 proof harness
- File: `backend/tests/test_b07_p7_ledger_cost_cache_audit.py`
- Adds non-vacuous tests for:
  - dynamic runtime discovery of tenant-scoped `llm_%` tables with insert/select and cross-tenant isolation checks
  - outcome matrix completeness across success/blocked/failed/cache-hit paths for both `llm_api_calls` and `llm_call_audit`
  - no raw prompt persistence assertion via canary
  - golden cost vectors and cents unit regression traps
  - rollup reconciliation: `SUM(llm_api_calls.cost_cents) == SUM(llm_monthly_costs.total_cost_cents)` for controlled bucket
  - semantic cache performance gate with anti-cheat controls:
    - repeated workload hit-rate threshold
    - unique-prompt near-zero hit rate
    - cache-disabled provider-call parity
    - output-to-prompt correspondence

4. CI adjudication integration
- File: `.github/workflows/ci.yml`
- Adds gate step:
  - `Run B0.7 P7 ledger-cost-cache-audit gate`
- Adds required artifact checks:
  - `p7_ledger_cost_cache.log`
  - `p7_runtime_probe.json`
  - `p7_outcome_matrix_summary.json`
  - `p7_rollup_reconciliation.json`
  - `p7_cache_performance.json`
- Adds non-vacuity log assertions for Phase 7 named tests.

5. Existing RLS test alignment
- File: `backend/tests/test_b07_p1_llm_user_rls.py`
- Updated audit-count assertion to `>= 1` because provider boundary now emits audit rows for additional outcome classes.

## Expected CI Artifacts (Adjudicated Environment)

From `artifacts/b07-p2/` in the CI run:

- `p7_runtime_probe.json`
- `p7_outcome_matrix_summary.json`
- `p7_rollup_reconciliation.json`
- `p7_cache_performance.json`
- `p7_ledger_cost_cache.log`

## Adjudication Rule

Phase 7 is considered complete only when this change-set is merged to `main` after green CI on PR, with the artifact set above produced from the clean-room runtime identity environment.

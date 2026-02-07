# B0.7-P3 Remediation Evidence (Provider Choke Point + Reservation/Breaker/Timeout/Cache/Distillation)

Date: 2026-02-07
Branch: `main`
Scope authority: code on `main` + CI run outcome

## Scientific Method

### Hypotheses under test
1. H-P3-01/H-P3-02/H-P3-03: provider calls are not exclusively routed through one choke point.
2. H-P3-04/H-P3-05: `llm_api_calls` does not encode full governance write-shape.
3. H-P3-06: monthly gating is check-then-call and overspends under concurrency.
4. H-P3-07: hourly emergency shutoff is absent or conflated with monthly cap.
5. H-P3-08: retry idempotency is not enforced at debit boundary.
6. H-P3-09/H-P3-10: breaker + hard timeout not enforced at choke point.
7. H-P3-11: cache exists but does not prevent provider calls or invalidate deterministically.
8. H-P3-12: distillation capture and explicit `distillation_eligible=false` are missing.

### Experiments
1. Static scans on backend for provider imports/call sites.
2. Static scans for `llm_api_calls` insert path.
3. Execution tests in `backend/tests/test_b07_p3_provider_controls.py`.
4. Enforcement scanner in `backend/tests/test_b07_p0_provider_boundary_enforcement.py`.

## Remediations Applied

### 1) Single provider choke point with aisuite boundary
- Implemented full provider boundary in `backend/app/llm/provider_boundary.py`.
- Provider-enabled path routes through `aisuite` via `_call_aisuite`.
- Worker functions route all LLM operations through `_PROVIDER_BOUNDARY.complete(...)` in `backend/app/workers/llm.py`.

### 2) Reservation -> Call -> Settlement with separated DB transactions
- `complete()` now commits pre-call state (claim + shutoff check + reservation + cache/breaker prechecks) before provider network call.
- Provider call executes with no active DB transaction, then settlement/release/finalization executes in a new transaction and commits.
- This removes the throughput-killing defect of holding a transaction open during network latency.

### 3) Budget + shutoff + breaker + timeout + cache + distillation together
- Atomic reservation state via `llm_monthly_budget_state` + `llm_budget_reservations`.
- Distinct hourly emergency shutoff state in `llm_hourly_shutoff_state`.
- Breaker state transitions in `llm_breaker_state` (3 failures -> open by configured threshold).
- Hard timeout around provider call with `asyncio.wait_for`.
- Postgres semantic cache in `llm_semantic_cache` with deterministic watermark invalidation.
- Distillation traces persisted in `reasoning_trace_ref`; `distillation_eligible` remains explicitly false.

### 4) Schema/model additions for governance write-shape
- Migration: `alembic/versions/003_data_governance/202602071100_b07_p3_llm_provider_controls.py`.
- Added governance fields to `llm_api_calls`: status/block/failure/breaker/provider_attempted/reservation/settlement/cache metadata.
- Added new tables: monthly budget state, budget reservations, semantic cache.
- Extended hourly shutoff table for threshold/window semantics.

## Static Analysis Results

### Provider call-site scan
Command:
```powershell
rg -n "\baisuite\b|openai|anthropic|bedrock|vertex|mistral|groq" backend/
```
Result summary:
1. Runtime provider integration references are in `backend/app/llm/provider_boundary.py`.
2. Non-runtime references are test fixtures/tests and model default config.

### `llm_api_calls` write-path scan
Command:
```powershell
rg -n "insert\(LLMApiCall\)|INSERT INTO llm_api_calls" backend/app
```
Result:
1. Single runtime insert path: `backend/app/llm/provider_boundary.py`.

### Retry/idempotency scan
Command:
```powershell
rg -n "autoretry|retry|acks_late|max_retries|task_acks_late" backend/
```
Result summary:
1. LLM Celery tasks remain bounded (`max_retries=3`).
2. P3 idempotency is enforced at `llm_api_calls` unique key + reservation row uniqueness.

### Budget/hourly controls scan
Command:
```powershell
rg -n "monthly|hourly|shutoff|panic|budget" backend/
```
Result summary:
1. Monthly reservation/settlement and hourly shutoff logic are both present in `backend/app/llm/provider_boundary.py` and `backend/app/models/llm.py`.

## Test Evidence

### Boundary exclusivity gate (local)
Command:
```powershell
pytest backend/tests/test_b07_p0_provider_boundary_enforcement.py -q
```
Observed:
1. `2 passed` (scanner negative control + repo-state check).

### P3 provider controls suite (local)
Command:
```powershell
pytest backend/tests/test_b07_p3_provider_controls.py -q
```
Observed:
1. Local run is blocked by DB authentication against external Postgres in this environment.
2. This does not falsify the code changes; authoritative adjudication is CI on `main`.

## Key Falsifications Claimed
1. Concurrency overspend risk: addressed by atomic reservation SQL and tested by parallel request gate (`test_p3_reservation_concurrency_safety`).
2. Hourly shutoff omission/conflation: addressed with distinct hourly state + dedicated test (`test_p3_hourly_shutoff_distinct_from_monthly`).
3. Retry double-debit: addressed with request_id idempotency + reservation uniqueness (`test_p3_retry_idempotency_no_double_debit`).
4. Open-transaction during provider call: addressed with explicit commit before network call + dedicated test (`test_p3_reservation_and_settlement_use_separate_transactions`).
5. Breaker/timeout/cache/distillation: covered by dedicated P3 tests in `backend/tests/test_b07_p3_provider_controls.py`.

## Files Changed (P3)
1. `alembic/versions/003_data_governance/202602071100_b07_p3_llm_provider_controls.py`
2. `backend/app/core/config.py`
3. `backend/app/models/llm.py`
4. `backend/app/models/__init__.py`
5. `backend/app/llm/provider_boundary.py`
6. `backend/app/workers/llm.py`
7. `backend/app/tasks/llm.py`
8. `backend/tests/test_b07_p3_provider_controls.py`
9. `backend/tests/test_b055_llm_worker_stubs.py`
10. `backend/tests/test_b07_p0_provider_boundary_stub.py`
11. `backend/tests/test_b07_p1_llm_user_rls.py`
12. `backend/tests/test_b055_llm_model_parity.py`
13. `docs/forensics/b07_p3_remediation_evidence.md`

## CI Adjudication (Mainline Authority)

### Main commit evidence
1. Main merge commit: `4ffd6be4a4e1703df19c7770033c4bdf3a3cea76` (`Merge pull request #55 from Muk223/codex/b07-p3-remediation-20260207`).
2. Primary remediation commit sequence:
   - `309dbc6` (`feat: enforce b07 p3 provider controls at aisuite choke point`)
   - `941f119` (`ci: execute b07 p3 provider controls in runtime proof job`)
   - `9a53317` (`ci: grant runtime table privileges before b07 p3 gate`)
   - `7cbdfe1` (`fix: pass typed month/uuid params in p3 budget sql`)
   - `0f4a225` (`fix: reapply tenant/user guc across p3 tx boundaries`)
   - `807e814` (`test: wait for terminal llm_api_calls status in b07 p2 chain`)

### Main CI run
1. Run ID: `21786102869`
2. Run URL: `https://github.com/Muk223/skeldir-2.0/actions/runs/21786102869`
3. Event/branch: `push` on `main`
4. Head SHA: `4ffd6be4a4e1703df19c7770033c4bdf3a3cea76`
5. Target job: `B0.7 P2 Runtime Proof (LLM + Redaction)` -> **success**
6. Target job URL: `https://github.com/Muk223/skeldir-2.0/actions/runs/21786102869/job/62857781344`

### Required P3 test proof from CI log
1. Step executed: `pytest -q backend/tests/test_b07_p3_provider_controls.py`.
2. Result: `10 passed, 136 warnings in 2.78s`.
3. Gate-level outcomes in the same step:
   - concurrency safety test passed
   - hourly shutoff distinctness test passed
   - retry idempotency/no double-debit test passed
   - breaker and timeout tests passed
   - cache invalidation test passed
   - transaction separation test passed
   - distillation capture test passed
   - secret non-leak failure-path test passed

### Artifact/redaction proof
1. Artifact name: `b07-p2-runtime-proof`
2. Artifact ID: `5418646754`
3. Artifact URL: `https://github.com/Muk223/skeldir-2.0/actions/runs/21786102869/artifacts/5418646754`
4. Redaction scanner output: `B0.7 P2 redaction hygiene scan passed`

## Verdict
B0.7-P3 exit criteria are satisfied on `main` with CI-backed execution proof for `backend/tests/test_b07_p3_provider_controls.py`.

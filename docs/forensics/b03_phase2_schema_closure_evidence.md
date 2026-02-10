# B0.3 Phase 2 Schema Closure Evidence

Date: 2026-02-10
Phase: B0.3
Execution status: PASS (`2026-02-10T19:51:48.189577+00:00`)
Provenance:
- Commit: `34ddb0d2c`
- Branch: `b03-phase2-runtime-proof`
- PR: `https://github.com/Muk223/skeldir-2.0/pull/71`

## Scope

This evidence pack captures EG2.1-EG2.5 for schema authority closure:
- canonical parity,
- migration determinism,
- tenant/RLS structural integrity,
- mandatory ledger table presence + runtime-role privileges (including append-only constraints),
- schema-to-write-shape binding via versioned ledger contract.

## CI/Local Gate Entry

- Gate runner: `scripts/phase_gates/b0_3_gate.py`
- Enforcement engine: `scripts/ci/phase2_schema_closure_gate.py`
- Contract: `contracts-internal/llm/b03_phase2_ledger_schema_contract.json`
- Summary: `backend/validation/evidence/database/phase2_b03/phase2_b03_summary.json`

## Artifacts

- EG2.1 parity diff: `backend/validation/evidence/database/phase2_b03/artifacts/eg2_1_parity.diff`
- EG2.2 determinism diff: `backend/validation/evidence/database/phase2_b03/artifacts/eg2_2_determinism.diff`
- Runtime-vs-migrated diff: `backend/validation/evidence/database/phase2_b03/artifacts/runtime_vs_migrated.diff`
- EG2.3/EG2.4 structural probe: `backend/validation/evidence/database/phase2_b03/artifacts/eg2_3_eg2_4_structural_probe.json`
- EG2.5 contract probe + negative control: `backend/validation/evidence/database/phase2_b03/artifacts/eg2_5_contract_probe.json`
- Migration adding prompt fingerprint + append-only control: `alembic/versions/007_skeldir_foundation/202602101300_b03_phase2_ledger_prompt_fingerprint.py`

## Runtime Physics Proof

- Runtime was executed against a live local PostgreSQL instance (`postgresql-x64-18`) with isolated identities:
  - migration identity: `phase2_migrator`
  - runtime identity: `phase2_runtime` (non-owner, `app_rw`/`app_ro` membership)
- Gate execution command:
  - `python scripts/phase_gates/run_gate.py B0.3`
- Gate result:
  - `backend/validation/evidence/database/phase2_b03/phase2_b03_summary.json` reports all gates passed.

## EG2.4 Assertions Verified

- Mandatory ledger tables present: `public.llm_api_calls`, `public.llm_call_audit`.
- Runtime privilege posture:
  - `llm_api_calls`: insert/select/update allowed, delete denied.
  - `llm_call_audit`: insert/select allowed, update/delete denied.
- Append-only enforcement:
  - no append-only privilege violations,
  - trigger-layer enforcement present for append-only table,
  - prompt fingerprint structural checks passed.
- Source: `backend/validation/evidence/database/phase2_b03/artifacts/eg2_3_eg2_4_structural_probe.json`.

## Non-Vacuity Control

The gate writes a negative-control record proving the contract check fails on a meaningful violation (missing required ledger column) in:

- `backend/validation/evidence/database/phase2_b03/artifacts/eg2_5_contract_probe.json`

This ensures gate logic is not trivially always-green.

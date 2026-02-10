# Phase 2 Hypothesis Matrix (B0.3 Schema Closure)

Date: 2026-02-10
Scope: EG2.1-EG2.5 (schema authority, determinism, tenant/RLS, ledger contract)
Execution anchor: `backend/validation/evidence/database/phase2_b03/phase2_b03_summary.json` at `2026-02-10T19:51:48.189577+00:00` with overall `status=success`.

## H2 Status

| Hypothesis | Status | Evidence |
|---|---|---|
| H2.1 Ledger tables exist at runtime but are not migration-defined | Refuted (EG2.1 + runtime mutation check passed) | `backend/validation/evidence/database/phase2_b03/artifacts/eg2_1_parity.diff`, `backend/validation/evidence/database/phase2_b03/artifacts/runtime_vs_migrated.diff` |
| H2.2 Canonical parity check is vacuous | Refuted (migrated-vs-runtime diff empty and canonical parity enforced) | `backend/validation/evidence/database/phase2_b03/artifacts/runtime_vs_migrated.diff`, `backend/validation/evidence/database/phase2_b03/artifacts/eg2_1_parity.diff` |
| H2.3 Migration determinism is not proven | Refuted (clean-schema apply/apply cycle stable) | `backend/validation/evidence/database/phase2_b03/artifacts/eg2_2_cycle_a.normalized.sql`, `backend/validation/evidence/database/phase2_b03/artifacts/eg2_2_cycle_b.normalized.sql`, `backend/validation/evidence/database/phase2_b03/artifacts/eg2_2_determinism.diff` |
| H2.4 Tenant/RLS structure incomplete on tenant-scoped tables | Refuted (tenant/RLS/policy + append-only controls passed) | `backend/validation/evidence/database/phase2_b03/artifacts/eg2_3_eg2_4_structural_probe.json` |
| H2.5 Mandatory ledger tables exist but required columns mismatch contract | Refuted (`prompt_fingerprint` required columns validated) | `backend/validation/evidence/database/phase2_b03/artifacts/eg2_5_contract_probe.json`, `contracts-internal/llm/b03_phase2_ledger_schema_contract.json` |
| H2.6 Privilege/ownership inconsistent with runtime identity | Refuted (runtime role privileges validated under non-owner identity) | `backend/validation/evidence/database/phase2_b03/artifacts/eg2_3_eg2_4_structural_probe.json` |
| H2.7 Schema-to-write-shape binding is missing | Refuted (versioned contract enforced + non-vacuous negative control passed) | `contracts-internal/llm/b03_phase2_ledger_schema_contract.json`, `backend/validation/evidence/database/phase2_b03/artifacts/eg2_5_contract_probe.json` |

## Notes

- All statuses are determined by `scripts/ci/phase2_schema_closure_gate.py` output summary.
- Final adjudication file: `backend/validation/evidence/database/phase2_b03/phase2_b03_summary.json`.

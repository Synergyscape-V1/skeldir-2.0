# B0.3 Phase 2 Schema Closure Evidence

Date: 2026-02-10
Phase: B0.3
Execution status: PASS (`2026-02-10T21:50:11Z`)
Provenance:
- Commit: `ce6cd1c05`
- Branch: `b03-phase2-runtime-proof`
- PR: `https://github.com/Muk223/skeldir-2.0/pull/71`
- CI run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21884348957` (pull_request, SUCCESS)

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
- Branch-protection contract: `contracts-internal/governance/b03_phase2_required_status_checks.main.json`
- Branch-protection CI probe: `scripts/ci/enforce_required_status_checks.py`
- Summary (local ephemeral runtime proof): `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/phase2_b03_summary.json`
- CI confirmations:
  - `Governance Guardrails` job `63175246212`: PASS
  - `Phase Gates (B0.3)` job `63175274639`: PASS
  - `Phase Chain (B0.4 target)` job `63175274510`: PASS

## Artifacts

- EG2.1 parity diff: `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/artifacts/eg2_1_parity.diff`
- EG2.2 determinism diff: `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/artifacts/eg2_2_determinism.diff`
- Runtime-vs-migrated diff: `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/artifacts/runtime_vs_migrated.diff`
- EG2.3/EG2.4 structural probe: `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/artifacts/eg2_3_eg2_4_structural_probe.json`
- EG2.5 contract probe + negative control: `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/artifacts/eg2_5_contract_probe.json`
- Migration adding prompt fingerprint + append-only control: `alembic/versions/007_skeldir_foundation/202602101300_b03_phase2_ledger_prompt_fingerprint.py`

## Runtime Physics Proof

- Runtime was executed against a live local PostgreSQL instance (`postgresql-x64-18`) with isolated identities:
  - migration identity: `phase2_migrator_b03_20260210`
  - runtime identity: `phase2_runtime_b03_20260210` (non-owner, `app_rw`/`app_ro` membership)
- Gate execution command:
  - `python scripts/ci/phase2_schema_closure_gate.py --evidence-dir backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210`
- Gate result:
  - `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/phase2_b03_summary.json` reports all gates passed.
  - CI run `21882485535` completed green end-to-end with B0.3 and chain gates passing.

## Branch Protection Enforcement Remediation

- Hypothesis under test: B0.3/B0.6 Phase 2 checks are advisory because branch protection does not require them.
- Pre-remediation probe:
  - `gh api repos/Muk223/skeldir-2.0/branches/main/protection/required_status_checks --jq '.contexts'`
  - Result: missing `B0.6 Phase 2 Adjudication` and `Phase Gates (B0.3)`.
- Remediation action:
  - Updated `main` required contexts via GitHub API to include both checks.
- Post-remediation probe:
  - `gh api repos/Muk223/skeldir-2.0/branches/main/protection/required_status_checks --jq '.contexts'`
  - Result includes:
    - `B0.6 Phase 2 Adjudication`
    - `Phase Gates (B0.3)`
- Regression guard:
  - CI now runs `python scripts/ci/enforce_required_status_checks.py` using contract `contracts-internal/governance/b03_phase2_required_status_checks.main.json`.
  - In PR contexts where branch-protection API is not readable (`403` from integration token), the guard uses check-run fallback to ensure required contexts are emitted for the adjudicated SHA.

## EG2.4 Assertions Verified

- Mandatory ledger tables present: `public.llm_api_calls`, `public.llm_call_audit`.
- Runtime privilege posture:
  - `llm_api_calls`: insert/select/update allowed, delete denied.
  - `llm_call_audit`: insert/select allowed, update/delete denied.
- Append-only enforcement:
  - no append-only privilege violations,
  - trigger-layer enforcement present for append-only table,
  - prompt fingerprint structural checks passed.
- Source: `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/artifacts/eg2_3_eg2_4_structural_probe.json`.

## Non-Vacuity Control

The gate writes a negative-control record proving the contract check fails on a meaningful violation (missing required ledger column) in:

- `backend/validation/evidence/database/phase2_b03_local_ephemeral_20260210/artifacts/eg2_5_contract_probe.json`

This ensures gate logic is not trivially always-green.

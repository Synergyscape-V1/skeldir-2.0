# Value Trace Proof Pack (Main-Anchored)

- Candidate SHA: `f86c62e` (Phase Gates VALUE_01..VALUE_05 all ✅)
- CI run (authoritative): `https://github.com/Muk223/skeldir-2.0/actions/runs/20492480929`
- Anchor mechanism:
  - Each phase summary JSON includes `candidate_sha` + `ci_run_url`:
    - `backend/validation/evidence/phases/<phase>_summary.json`
  - Emitted from `GITHUB_SHA` + `GITHUB_RUN_ID` at runtime.

This proof pack is satisfied by the `Phase Gates (VALUE_01..VALUE_05)` matrix jobs on `main`, plus the per-job `phase-VALUE_0X-evidence` artifacts uploaded by CI.

## Migration Chain Verified

The forensic migrations are properly linked:
- `202512231000_add_ghost_revenue_columns.py` (VALUE_01 support)
- `202512231010_add_llm_call_audit.py` (VALUE_03 support)
- `202512231020_add_investigation_jobs.py` (VALUE_05 support)

All downgrades include `# CI:DESTRUCTIVE_OK` markers for intentional destructive operations.

## EG-VT-01 (VALUE_01)

- Actions job: `https://github.com/Muk223/skeldir-2.0/actions/runs/20492480929/job/58887018338`
- Artifact: `phase-VALUE_01-evidence` (id `4963263672`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4963263672/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_01_summary.json`
  - `docs/evidence/value_traces/value_01_revenue_trace.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_01_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_01_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-02 (VALUE_02)

- Actions job: `https://github.com/Muk223/skeldir-2.0/actions/runs/20492480929/job/58887018321`
- Artifact: `phase-VALUE_02-evidence` (id `4963263783`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4963263783/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_02_summary.json`
  - `docs/evidence/value_traces/value_02_constraint_trace.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_02_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_02_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-03 (VALUE_03)

- Actions job: `https://github.com/Muk223/skeldir-2.0/actions/runs/20492480929/job/58887018327`
- Artifact: `phase-VALUE_03-evidence` (id `4963263869`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4963263869/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_03_summary.json`
  - `docs/evidence/value_traces/value_03_provider_handshake.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_03_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_03_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-04 (VALUE_04)

- Actions job: `https://github.com/Muk223/skeldir-2.0/actions/runs/20492480929/job/58887018329`
- Artifact: `phase-VALUE_04-evidence` (id `4963263518`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4963263518/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_04_summary.json`
  - `docs/evidence/value_traces/value_04_registry_trace.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_04_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_04_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-05 (VALUE_05) - NEW

- Actions job: `https://github.com/Muk223/skeldir-2.0/actions/runs/20492480929/job/58887018324`
- Artifact: `phase-VALUE_05-evidence` (id `4963263023`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4963263023/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_05_summary.json`
  - `docs/evidence/value_traces/value_05_centaur_enforcement.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_05_pytest.log` should contain `2 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_05_summary.json` has `status=success` and `missing_artifacts=[]`
- Invariants proven:
  - Minimum hold enforced (cannot skip 45s wait)
  - Approval gate enforced (cannot auto-complete)
  - State machine integrity (PENDING -> READY_FOR_REVIEW -> COMPLETED)

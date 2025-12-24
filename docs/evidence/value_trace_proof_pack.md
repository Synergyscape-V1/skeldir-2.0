# Value Trace Proof Pack (Main-Anchored)

- Source of truth: **GitHub Actions CI run on `main` for the candidate SHA**
- Anchors:
  - The candidate SHA and CI run URL are emitted into each phase summary JSON at:
    - `backend/validation/evidence/phases/<phase>_summary.json`
  - These are populated from `GITHUB_SHA` and `GITHUB_RUN_ID` at runtime.

This proof pack is satisfied by the `Phase Gates (VALUE_01..VALUE_05)` matrix jobs on `main`, plus the per-job `phase-VALUE_0X-evidence` artifacts uploaded by CI.

## Migration Chain Verified

The forensic migrations are properly linked:
- `202512231000_add_ghost_revenue_columns.py` (VALUE_01 support)
- `202512231010_add_llm_call_audit.py` (VALUE_03 support)
- `202512231020_add_investigation_jobs.py` (VALUE_05 support)

All downgrades include `# CI:DESTRUCTIVE_OK` markers for intentional destructive operations.

## EG-VT-01 (VALUE_01)

- Actions job: https://github.com/Muk223/skeldir-2.0/actions/runs/20470980951/job/58826036615
- Artifact: `phase-VALUE_01-evidence` (id `4956646661`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4956646661/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_01_summary.json`
  - `docs/evidence/value_traces/value_01_revenue_trace.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_01_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_01_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-02 (VALUE_02)

- Actions job: https://github.com/Muk223/skeldir-2.0/actions/runs/20470980951/job/58826036632
- Artifact: `phase-VALUE_02-evidence` (id `4956645058`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4956645058/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_02_summary.json`
  - `docs/evidence/value_traces/value_02_constraint_trace.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_02_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_02_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-03 (VALUE_03)

- Actions job: https://github.com/Muk223/skeldir-2.0/actions/runs/20470980951/job/58826036614
- Artifact: `phase-VALUE_03-evidence` (id `4956645062`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4956645062/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_03_summary.json`
  - `docs/evidence/value_traces/value_03_provider_handshake.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_03_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_03_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-04 (VALUE_04)

- Actions job: https://github.com/Muk223/skeldir-2.0/actions/runs/20470980951/job/58826036630
- Artifact: `phase-VALUE_04-evidence` (id `4956645181`, zip `https://api.github.com/repos/Muk223/skeldir-2.0/actions/artifacts/4956645181/zip`)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_04_summary.json`
  - `docs/evidence/value_traces/value_04_registry_trace.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_04_pytest.log` contains `1 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_04_summary.json` has `status=success` and `missing_artifacts=[]`

## EG-VT-05 (VALUE_05) - NEW

- Actions job: _Pending CI run on commit 8604f8d_
- Artifact: `phase-VALUE_05-evidence` (pending)
- Evidence outputs:
  - `backend/validation/evidence/value_traces/value_05_summary.json`
  - `docs/evidence/value_traces/value_05_centaur_enforcement.md`
- Log anchor (within artifact): `backend/validation/evidence/phases/value_05_pytest.log` should contain `2 passed`
- Gate enforcement (within artifact): `backend/validation/evidence/phases/value_05_summary.json` has `status=success` and `missing_artifacts=[]`
- Invariants proven:
  - Minimum hold enforced (cannot skip 45s wait)
  - Approval gate enforced (cannot auto-complete)
  - State machine integrity (PENDING -> READY_FOR_REVIEW -> COMPLETED)

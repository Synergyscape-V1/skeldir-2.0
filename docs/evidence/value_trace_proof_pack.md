# Value Trace Proof Pack (Main-Anchored)

- main commit: `da714b80298277908facd070d57d12e8a9373acb`
- CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/20470980951

This proof pack is satisfied by the `Phase Gates (VALUE_01..VALUE_04)` matrix jobs on `main`, plus the per-job `phase-VALUE_0X-evidence` artifacts uploaded by CI.

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

# Value Trace Proof Pack (Authoritative = CI Artifact)

This file is intentionally **NOT** the authoritative proof pack.

Why: see `docs/forensics/evidence/EG5_TEMPORAL_PARADOX.md` (EG-5 temporal incoherence).

## Where the authoritative proof pack lives

The authoritative EG-5 proof pack is generated inside GitHub Actions and uploaded as a CI artifact:

- **Artifact name**: `value-trace-proof-pack`
- **Contents**:
  - `backend/validation/evidence/proof_pack/value_trace_proof_pack.json` (machine-verifiable)
  - `docs/forensics/proof_pack/value_trace_proof_pack.md` (human-readable)

## What it contains (required fields)

- `candidate_sha` (must equal `GITHUB_SHA`)
- `run_id` (must equal `GITHUB_RUN_ID`)
- `run_url`
- `value_gates[]`: `{ gate_id, job_url, artifact_name, artifact_id }` for VALUE_01..VALUE_05

## How to retrieve it

1. Open GitHub Actions for the commit SHA you care about: `https://github.com/Muk223/skeldir-2.0/actions`
2. Open the **CI** run for that SHA.
3. Download the artifact **`value-trace-proof-pack`**.

## How EG-5 is enforced

CI fails the `proof-pack` job if:
- the proof pack’s `candidate_sha` ≠ `GITHUB_SHA`, or
- the proof pack’s `run_id` ≠ `GITHUB_RUN_ID`, or
- any of the five VALUE gate evidence artifacts are missing from the run.

## Migration Chain Verified

The forensic migrations are properly linked:
- `202512231000_add_ghost_revenue_columns.py` (VALUE_01 support)
- `202512231010_add_llm_call_audit.py` (VALUE_03 support)
- `202512231020_add_investigation_jobs.py` (VALUE_05 support)

All downgrades include `# CI:DESTRUCTIVE_OK` markers for intentional destructive operations.

Detailed per-run job URLs and artifact IDs are emitted into the CI-generated proof pack artifact.

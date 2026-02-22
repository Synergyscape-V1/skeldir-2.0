# B1.1-P4 Findings and Remediations (PR #119 Corrective)

Date: 2026-02-22  
Phase: `B1.1-P4 - DB Credentials + Provider Keys Migration + CI/CD Audited Retrieval`  
Branch: `b11-p4-db-provider-migration`  
Target: `main`

## Scope of This Corrective

This corrective addresses the explicit blockers:

- `H01` shadow DB secret pathways via direct env fallback reads
- `H02` scanner scope false negatives for `scripts/` and `backend/tests/`
- `H06` vacuous DB rotation drill
- `H07` vacuous provider-key rotation drill
- `H09` non-immutable proof mapping

## Hypothesis Adjudication

1. `H01` TRUE -> REMEDIATED  
Evidence:
- `scripts/security/b11_p4_generate_static_scans.py` now scans `backend/app`, `backend/tests`, `scripts`, `alembic`.
- `docs/forensics/evidence/b11_p4/db_dsn_fallback_scan.txt` now reports `violations=0`.
- DB fallback callsites remediated to choke-point retrieval in:
  - `scripts/validate_channel_fks.py`
  - `scripts/validate_channel_integrity.py`
  - `scripts/validate-schema-compliance.py`
  - `scripts/database/run_query_performance.py`
  - `scripts/ci/b055_evidence_bundle.py`
  - `scripts/ci/phase2_schema_closure_gate.py`
  - `scripts/phase8/llm_background_load.py`
  - `scripts/r2/runtime_scenario_suite.py`
  - `scripts/r5/r5_probes.py`
  - `backend/tests/conftest.py`
  - `backend/check_webhook_columns.py`

2. `H02` TRUE -> REMEDIATED  
Evidence:
- Scanner coverage expanded in `scripts/security/b11_p4_generate_static_scans.py`.
- Negative control hardened in `backend/tests/test_b11_p4_static_scans.py` with explicit `os.getenv('DATABASE_URL')` canary.
- Local execution result: `backend/tests/test_b11_p4_static_scans.py` passed (`2 passed`).

3. `H06` TRUE -> REMEDIATED  
Evidence:
- Non-vacuous DB drill implemented in `scripts/security/b11_p4_rotation_drills_ci.py`:
  - creates disposable DB/user pair,
  - validates old credential success pre-rotation,
  - rotates to new credential,
  - proves old credential fails (`role ... is not permitted to log in`),
  - proves new credential succeeds.
- Artifacts:
  - `docs/forensics/evidence/b11_p4/rotation_drill_db_credentials_ci.txt`
  - `docs/forensics/evidence/b11_p4/rotation_drill_db_credentials.txt`

4. `H07` TRUE -> REMEDIATED  
Evidence:
- Non-vacuous provider key drill implemented in `scripts/security/b11_p4_rotation_drills_ci.py`:
  - old key initially accepted (`200`),
  - after rotation old key rejected (`401`),
  - new key accepted (`200`).
- Artifacts:
  - `docs/forensics/evidence/b11_p4/rotation_drill_provider_key_ci.txt`
  - `docs/forensics/evidence/b11_p4/rotation_drill_provider_key.txt`

5. `H09` TRUE -> REMEDIATED (CI mapping now deterministic; final immutability pending PR run IDs)  
Evidence:
- Immutable checksum updater added: `scripts/security/b11_p4_update_proof_index.py`.
- Workflow now updates proof index during CI before artifact upload:
  - `.github/workflows/b11-p4-db-provider-ci-audit-adjudication.yml`
- Checksum section present in:
  - `docs/forensics/evidence/b11_p4/PROOF_INDEX.md`

## Additional Security Remediations

1. CI pre-merge adjudication hardening retained on `main` from PR #118:
- P4 checks required in branch protection:
  - `docs/forensics/evidence/b11_p4/branch_protection_required_checks.json`

2. Rotation drill secret masking:
- Temporary credentials/keys are explicitly masked with GitHub Actions command `::add-mask::` in `scripts/security/b11_p4_rotation_drills_ci.py`.

3. DDL/DML credential separation preserved:
- Runtime and migration retrieval remain separated via:
  - `backend/app/core/secrets.py`
  - `alembic/env.py`
  - `scripts/ci/phase2_schema_closure_gate.py` (now reads both through choke point helpers).

4. Gate 4 forensic durability remediation:
- Replaced stale Windows-local placeholder artifacts with CI-generated Ubuntu artifacts for:
  - `docs/forensics/evidence/b11_p4/ci_oidc_assume_role_log.txt`
  - `docs/forensics/evidence/b11_p4/ci_secret_retrieval_log.txt`
  - `docs/forensics/evidence/b11_p4/cloudtrail_ci_secret_reads.txt`
  - `docs/forensics/evidence/b11_p4/cloudtrail_stage_secret_reads.txt`
- Corrected `PROOF_INDEX.md` artifact digest mappings to canonical GitHub artifact digests for run `22285543552`.
- Verified committed CloudTrail files now contain:
  - CI identity tether: `identity_tether=skeldir-ci-deploy`
  - Stage runtime identity tether: `identity_tether=skeldir-app-runtime-stage`

## Validation Executed Locally

1. Static scan gate:
- Command: `python scripts/security/b11_p4_generate_static_scans.py --out-dir docs/forensics/evidence/b11_p4`
- Result: PASS (`exit_code=0`, zero DB/provider/workflow violations).

2. Non-vacuous static canary:
- Command: `cd backend; pytest tests/test_b11_p4_static_scans.py -q`
- Result: PASS (`2 passed`).

3. DB/provider contract tests:
- Command: `cd backend; pytest tests/test_b11_p4_db_provider_contract.py -q`
- Result: PASS (`4 passed`).

4. Rotation drills:
- Command: `python scripts/security/b11_p4_rotation_drills_ci.py --out-dir docs/forensics/evidence/b11_p4`
- Result: PASS (old DB credential rejected post-rotation, new accepted; old provider key rejected post-rotation, new accepted).

## Completion State

Code remediation status for requested blockers (`H01/H02/H06/H07/H09`): **COMPLETE**.  
Phase closure on `main`: **COMPLETE**.

Mainline closure evidence:
- PR merged: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/119`
- Merge timestamp (UTC): `2026-02-22T20:05:22Z`
- Merge commit: `32904d835fa8142060bb1f40de3501948176763f`
- P4 adjudication on merged commit: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22284347436` (`success`)
- Main CI adjudication on merged commit: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22284347431` (`success`)

Gate 4 durable-evidence refresh on latest mainline:
- Merge commit: `97a6b88f95208e2175a4739bee39da6d93989f13`
- P4 adjudication run: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22285543552` (`success`)
- Main CI run: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22285543559` (`success`)

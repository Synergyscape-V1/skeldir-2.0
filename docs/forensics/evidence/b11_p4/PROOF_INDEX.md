# B1.1-P4 Proof Index

Date: 2026-02-22  
Branch: `b11-p4-db-provider-migration`  
Target branch: `main`

## Exit Gate A - Shadow DB DSN Reads Eliminated

- `docs/forensics/evidence/b11_p4/db_dsn_callsite_scan.txt`
- `docs/forensics/evidence/b11_p4/db_dsn_fallback_scan.txt`
- `backend/tests/test_b11_p4_static_scans.py`
- `scripts/security/b11_p4_generate_static_scans.py`

Definition evidence:
- scanner now includes `scripts/`, `backend/tests/`, `alembic/`
- zero DB fallback violations
- negative control fails on injected `os.getenv('DATABASE_URL')`

## Exit Gate B - CI CloudTrail Tether Proof

- `docs/forensics/evidence/b11_p4/ci_oidc_assume_role_log.txt`
- `docs/forensics/evidence/b11_p4/ci_secret_retrieval_log.txt`
- `docs/forensics/evidence/b11_p4/cloudtrail_ci_secret_reads.txt`

## Exit Gate C - Stage CloudTrail Tether Proof

- `docs/forensics/evidence/b11_p4/cloudtrail_stage_secret_reads.txt`

## Exit Gate D - CI-Safe DB Rotation Drill (Non-Vacuous)

- `docs/forensics/evidence/b11_p4/rotation_drill_db_credentials_ci.txt`
- `docs/forensics/evidence/b11_p4/rotation_drill_db_credentials.txt`
- Harness: `scripts/security/b11_p4_rotation_drills_ci.py`

## Exit Gate E - Provider Key Rotation Drill (Non-Vacuous)

- `docs/forensics/evidence/b11_p4/rotation_drill_provider_key_ci.txt`
- `docs/forensics/evidence/b11_p4/rotation_drill_provider_key.txt`
- Harness: `scripts/security/b11_p4_rotation_drills_ci.py`

## Exit Gate F - Non-Bypassable Adjudication

- Required checks evidence: `docs/forensics/evidence/b11_p4/branch_protection_required_checks.json`
- Workflow gate: `.github/workflows/b11-p4-db-provider-ci-audit-adjudication.yml`

## Exit Gate G - Evidence Pack Coherence

- Findings: `docs/forensics/evidence/b11_p4/B11_P4_FINDINGS_AND_REMEDIATIONS.md`
- Hypothesis adjudication: `docs/forensics/evidence/b11_p4/B11_P4_CORRECTIVE_HYPOTHESIS_ADJUDICATION.md`
- Checksum updater: `scripts/security/b11_p4_update_proof_index.py`

## CI Run Mapping (Merged Mainline Deterministic References)

- pr_url=https://github.com/Synergyscape-V1/skeldir-2.0/pull/120
- pr_merged_at_utc=2026-02-22T21:18:21Z
- merge_commit_sha=97a6b88f95208e2175a4739bee39da6d93989f13
- p4_workflow_run_id=22285543552
- p4_workflow_run_attempt=1
- p4_workflow_run_url=https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22285543552
- p4_workflow_status=completed
- p4_workflow_conclusion=success
- main_ci_run_id=22285543559
- main_ci_run_attempt=1
- main_ci_run_url=https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22285543559
- main_ci_status=completed
- main_ci_conclusion=success

## Artifact Bundle Immutability (GitHub Actions Artifacts)

- run_id=22285543552 artifact_id=5609341659 name=b11-p4-ci-audit-evidence sha256_zip=86A7A2940AD692C51CCBC27A234672E3E24712818DC82AFBE8281CCDF34D7571
- run_id=22285543552 artifact_id=5609344195 name=b11-p4-static-runtime-evidence sha256_zip=5FB02623605547D4F123F7B9B0F768EB769ED064A2ABED53903CECF4F320501B

## Artifact Checksums

- db_dsn_callsite_scan.txt: sha256=80a431543f2a579cce7c37f78ad6ce25496b42de398fa5b55a99b8ef17c55a5e bytes=43
- db_dsn_fallback_scan.txt: sha256=df2f5dd4cffd00063dbae68f242473fc3293375df6accbac9ecd98c686cb48a8 bytes=43
- provider_key_callsite_scan.txt: sha256=50269078fad5555be0505ed0d7d6bb04c0fd180cc067c97d10557a29799c2afc bytes=49
- workflow_plaintext_secret_scan.txt: sha256=78ad893410439ace8fc763409f2b3f9b6046de6ad5a46ba7b16ce9f38916110d bytes=53
- rotation_drill_db_credentials_ci.txt: sha256=2a0d78ed44e9103286eacc17e3235fca6b305edc8637f50b45692edd5b48ce71 bytes=384
- rotation_drill_provider_key_ci.txt: sha256=fc379eeb1fc79db69e12b26685b1331f734b08cb8b631d86438aa918860849ff bytes=138
- ci_oidc_assume_role_log.txt: sha256=5d45a321afaac556745d9a07b23bbf2810499717319c84f284eba1c51815106c bytes=342
- ci_secret_retrieval_log.txt: sha256=862e295d1608a459c7e072241dc1774c5a135c2661d8ffc95e9f8c53730babdb bytes=415
- cloudtrail_ci_secret_reads.txt: sha256=e4b10dc03a52ef9013251171ce6c7ff32b0ac1617413a5d21aaaa81832367bde bytes=287
- cloudtrail_stage_secret_reads.txt: sha256=174356fc2afb83712c6c701ad99020e1da51732930ea7fa237de27346e703d38 bytes=458

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

## CI Run Mapping (to be populated by PR #119 adjudication run)

- run_id=PENDING_PR119
- run_attempt=PENDING_PR119
- run_url=PENDING_PR119
- head_sha=PENDING_PR119

## Artifact Checksums

- db_dsn_callsite_scan.txt: sha256=80a431543f2a579cce7c37f78ad6ce25496b42de398fa5b55a99b8ef17c55a5e bytes=43
- db_dsn_fallback_scan.txt: sha256=df2f5dd4cffd00063dbae68f242473fc3293375df6accbac9ecd98c686cb48a8 bytes=43
- provider_key_callsite_scan.txt: sha256=50269078fad5555be0505ed0d7d6bb04c0fd180cc067c97d10557a29799c2afc bytes=49
- workflow_plaintext_secret_scan.txt: sha256=78ad893410439ace8fc763409f2b3f9b6046de6ad5a46ba7b16ce9f38916110d bytes=53
- rotation_drill_db_credentials_ci.txt: sha256=2a0d78ed44e9103286eacc17e3235fca6b305edc8637f50b45692edd5b48ce71 bytes=384
- rotation_drill_provider_key_ci.txt: sha256=fc379eeb1fc79db69e12b26685b1331f734b08cb8b631d86438aa918860849ff bytes=138
- ci_oidc_assume_role_log.txt: sha256=e90899112ea7c75521ec856ba8d166dac26f29bea0b77bea02a6806cf1a90f9e bytes=342
- ci_secret_retrieval_log.txt: sha256=3263d81ffbcc15c3de3d7dbfc365324f57629707a7afe0a2055293c6ab8ae358 bytes=415
- cloudtrail_ci_secret_reads.txt: sha256=f5c767ba73676c7f7f8ca181473578114c5aeedcd445ceaebc9d8b93fc046bdf bytes=287
- cloudtrail_stage_secret_reads.txt: sha256=0cb88df527a203af1fd55238aa4eb3ed43d8690713003965c00a9f8a19bd22c4 bytes=458

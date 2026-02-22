# B1.1-P4 Proof Index

## Scope
- Phase: `B1.1-P4 - DB Credentials + Provider Keys Migration + CI/CD Audited Retrieval`
- Primary workflow: `.github/workflows/b11-p4-db-provider-ci-audit-adjudication.yml`
- Local verification date: `2026-02-21`
- Corrective adjudication table: `docs/forensics/evidence/b11_p4/B11_P4_CORRECTIVE_HYPOTHESIS_ADJUDICATION.md`

## Exit Gate 1 - DB Credentials Migrated + Choke Point Enforced
- DB call-site static scan: `docs/forensics/evidence/b11_p4/db_dsn_callsite_scan.txt`
- Runtime contract tests: `docs/forensics/evidence/b11_p4/rotation_drill_db_credentials.txt`
- Choke-point implementation: `backend/app/core/secrets.py`
- Migration source-of-truth enforcement: `alembic/env.py`

## Exit Gate 2 - Provider Keys Migrated + Fail-Closed Semantics
- Provider call-site static scan: `docs/forensics/evidence/b11_p4/provider_key_callsite_scan.txt`
- Provider fail-closed runtime tests: `docs/forensics/evidence/b11_p4/rotation_drill_provider_key.txt`
- Control-plane contract updates: `backend/app/core/managed_settings_contract.py`

## Exit Gate 3 - CI Secret Flow Audited (No Plaintext YAML)
- Workflow plaintext scan: `docs/forensics/evidence/b11_p4/workflow_plaintext_secret_scan.txt`
- CI OIDC + retrieval workflow: `.github/workflows/b11-p4-db-provider-ci-audit-adjudication.yml`
- Production schema deploy migration to OIDC/AWS retrieval: `.github/workflows/schema-deploy-production.yml`

## Exit Gate 4 - Audit Tether Proof (CI + Runtime)
- CI OIDC assume-role evidence: `docs/forensics/evidence/b11_p4/ci_oidc_assume_role_log.txt`
- CI secret retrieval evidence: `docs/forensics/evidence/b11_p4/ci_secret_retrieval_log.txt`
- CloudTrail CI tether output: `docs/forensics/evidence/b11_p4/cloudtrail_ci_secret_reads.txt`
- CloudTrail stage runtime tether output: `docs/forensics/evidence/b11_p4/cloudtrail_stage_secret_reads.txt`

## Exit Gate 5 - Rotation Readiness Drill
- DB credential drill (restart contract + DSN reload): `docs/forensics/evidence/b11_p4/rotation_drill_db_credentials.txt`
- Provider key drill (stage/provider fail-closed semantics): `docs/forensics/evidence/b11_p4/rotation_drill_provider_key.txt`

## Exit Gate 6 - Evidence Pack Published
- This index: `docs/forensics/evidence/b11_p4/PROOF_INDEX.md`
- Branch protection evidence: `docs/forensics/evidence/b11_p4/branch_protection_required_checks.json`
- Required files present:
  - `docs/forensics/evidence/b11_p4/workflow_plaintext_secret_scan.txt`
  - `docs/forensics/evidence/b11_p4/db_dsn_callsite_scan.txt`
  - `docs/forensics/evidence/b11_p4/provider_key_callsite_scan.txt`
  - `docs/forensics/evidence/b11_p4/ci_oidc_assume_role_log.txt`
  - `docs/forensics/evidence/b11_p4/ci_secret_retrieval_log.txt`
  - `docs/forensics/evidence/b11_p4/cloudtrail_ci_secret_reads.txt`
  - `docs/forensics/evidence/b11_p4/cloudtrail_stage_secret_reads.txt`
  - `docs/forensics/evidence/b11_p4/rotation_drill_db_credentials.txt`
  - `docs/forensics/evidence/b11_p4/rotation_drill_provider_key.txt`

## CI Run Mapping
- run_id=22281720456
- run_attempt=1
- run_url=https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22281720456
- workflow=b11-p4-db-provider-ci-audit-adjudication
- event=workflow_dispatch
- head_sha=948957aec71f5a412801863d6eb65048efc982fc
- generated_utc=2026-02-22T17:20:32.627208+00:00

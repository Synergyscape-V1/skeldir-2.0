# B1.1-P4 Corrective Hypothesis Adjudication

Date: 2026-02-22
Branch basis: `main` head `948957aec71f5a412801863d6eb65048efc982fc`
Scope: Adjudication of H01-H09 from directive + corrective actions applied

## Hypothesis Table

| ID | Hypothesis | Status | Evidence |
|---|---|---|---|
| H01 | DB DSNs are still readable outside choke point via direct env fallback | TRUE (repo-wide), FALSE (stage/prod runtime paths) | `scripts/validate_channel_integrity.py`, `scripts/validate_channel_fks.py`, `scripts/validate-schema-compliance.py`, `backend/tests/conftest.py`; runtime code paths remain choke-pointed in `backend/app/core/secrets.py`, `backend/app/db/session.py`, `backend/app/celery_app.py`, `alembic/env.py`. |
| H02 | P4 static scan scope is insufficient (false negatives) | TRUE | `scripts/security/b11_p4_generate_static_scans.py` defaults to `backend/app` + `alembic/env.py` only. |
| H03 | Committed CloudTrail proofs are stale/placeholder | FALSE | Refreshed by run `22281720456`; `docs/forensics/evidence/b11_p4/cloudtrail_stage_secret_reads.txt` now includes `identity_tether=skeldir-app-runtime-stage`. |
| H04 | CI CloudTrail proof generation is broken/non-reproducible | FALSE | Run `22281720456` `b11-p4-ci-audit-gate` passed with `--strict`; CI used `aws-actions/configure-aws-credentials@v4` and generated proofs. |
| H05 | Stage tether absent because no stage trigger event occurred | FALSE | Stage runtime CloudTrail event present in run `22281720456` artifact and committed evidence file (`identity_tether=skeldir-app-runtime-stage`). |
| H06 | DB rotation drill is vacuous | TRUE | `backend/tests/test_b11_p4_db_provider_contract.py::test_database_rotation_contract_reloads_on_process_restart` is monkeypatch + module reload, not authority-level old-dead/new-works proof. |
| H07 | Provider key rotation drill is vacuous | TRUE | No explicit old-key reject/new-key accept runtime proof harness exists in P4 artifacts. |
| H08 | P4 adjudication is bypassable | WAS TRUE, NOW REMEDIATED | Branch protection updated to require `b11-p4-static-and-runtime-gate` and `b11-p4-ci-audit-gate`; see `docs/forensics/evidence/b11_p4/branch_protection_required_checks.json`. |
| H09 | PROOF_INDEX lacks immutable/verifiable mapping | PARTIAL | `PROOF_INDEX.md` includes run ID/url/head SHA/timestamp; artifact IDs/checksums still not embedded. |

## Corrective Actions Applied

1. Enforced P4 checks in branch protection on `main`:
- Added required contexts:
  - `b11-p4-static-and-runtime-gate`
  - `b11-p4-ci-audit-gate`
- Evidence: `docs/forensics/evidence/b11_p4/branch_protection_required_checks.json`

2. Removed PR skip-bypass for P4 CI-audit context:
- Updated `.github/workflows/b11-p4-db-provider-ci-audit-adjudication.yml` so `b11-p4-ci-audit-gate` runs on `pull_request` (pre-merge policy context) and on `main` push/dispatch (authoritative AWS proof context).

## Remaining True Blockers

- H01/H02: Repo-wide shadow DB env reads remain in `scripts/` and `backend/tests/`; scanner scope is still narrower than full directive intent.
- H06/H07: Rotation drills remain contract-level and do not yet prove old credential/key rejection vs new acceptance at authority boundary.
- H09: PROOF_INDEX does not yet include artifact IDs/checksums.

## Current Gate Outlook (Directive Framing)

- Gate 4 (CloudTrail tether): CLOSED empirically by run `22281720456`.
- Gate 6 (non-bypassable adjudication): CLOSED by branch protection update + PR-context P4 CI-audit status availability.
- Gate 1 + Gate 5 + Gate 7 (strict directive interpretation): still need additional remediation work.

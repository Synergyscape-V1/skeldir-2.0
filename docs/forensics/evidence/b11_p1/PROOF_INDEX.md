# B11-P1 Proof Index

Detailed reports:
- `docs/forensics/evidence/b11_p1/B11_P1_FINDINGS_AND_REMEDIATIONS.md`
- `docs/forensics/evidence/b11_p1/B11_P1_CORRECTIVE_REMEDIATION_REPORT.md`

Generated: 2026-02-20 (post-GitHub-analyst corrective cycle)

## Corrective Cycle Outcome

- Gate 3: MET (CI-proven on `main`)
- Gate 5: REMEDIATED (control-plane + workflow hardening applied; awaiting fresh adjudication run on latest commit)
- Gate 4: BLOCKED (CI role denied `cloudtrail:LookupEvents`)
- Gates 1/2: MET (non-regressed)

## Last Fully Green Historical Run

- Run URL: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22240863314`
- Result: SUCCESS
- Jobs:
  - `ssot-contract-gate`: PASS
  - `env-boundary-gate`: PASS
  - `terraform-control-plane-gate`: PASS
  - `aws-proof-gate`: PASS

## Gate Mapping (Final)

1. Exit Gate 1 - SSOT Contract Enforced
- Status: MET
- Evidence:
  - `docs/forensics/evidence/b11_p1/ssot_contract_snapshot.json`

2. Exit Gate 2 - Environment Namespace Boundary Proven
- Status: MET
- Evidence:
  - `docs/forensics/evidence/b11_p1/deny_proof_cross_env.txt`

3. Exit Gate 3 - IaC State Exists + Imports Completed
- Status: MET
- Evidence:
  - `docs/forensics/evidence/b11_p1/iac_state_proof.txt`
- Required proof present in run `22240863314`:
  - remote backend init (no `-backend=false`)
  - non-empty state after import
  - state show entries for OIDC + 4 roles
  - no-op plan

4. Exit Gate 4 - Audit Evidence Produced
- Status: BLOCKED
- Evidence:
  - `docs/forensics/evidence/b11_p1/cloudtrail_audit_proof.txt`
- Blocker (CI-role-tethered, reproducible):
  - `docs/forensics/evidence/b11_p1/cloudtrail_audit_proof.txt` shows `AccessDeniedException` for `cloudtrail:LookupEvents` under `arn:aws:sts::326730685463:assumed-role/skeldir-ci-deploy/GitHubActions`.
- Minimum unblock request:
  - Add `cloudtrail:LookupEvents` allow for role `skeldir-ci-deploy` (identity policy within existing boundary scope), then rerun `b11-p1-control-plane-adjudication` on `main`.

5. Exit Gate 5 - CI Adjudication Non-Bypassable on `main`
- Status: REMEDIATED (awaiting re-adjudication on updated workflow)
- Evidence:
  - `docs/forensics/evidence/b11_p1/branch_protection_main.json`
  - `docs/forensics/evidence/b11_p1/branch_protection_required_checks.json`
- Required checks enforced:
  - `ssot-contract-gate`
  - `env-boundary-gate`
  - `terraform-control-plane-gate`
  - `aws-proof-gate`
- Additional non-bypass controls now enforced:
  - `required_pull_request_reviews.required_approving_review_count=1` on `main`
  - b11 workflow PR adjudication hardened to remove PR-mode `terraform init -backend=false`

## Residual Notes

Historical blocker artifacts retained for audit trail:
- `docs/forensics/evidence/b11_p1/iac_backend_blocker.txt`

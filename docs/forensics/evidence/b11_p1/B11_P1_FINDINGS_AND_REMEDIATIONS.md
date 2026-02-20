# B1.1-P1 Findings and Remediations

Date: 2026-02-20
Scope: Corrective closure after GitHub analyst adjudication + main re-adjudication

## Executive Status

- Gate 1: MET
- Gate 2: MET
- Gate 3: MET
- Gate 4: MET
- Gate 5: MET

B1.1-P1 corrective directive is COMPLETE.

## Final Adjudication Evidence

Authoritative `main` run:
- `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22242378414`

Observed:
- `ssot-contract-gate`: PASS
- `env-boundary-gate`: PASS
- `terraform-control-plane-gate`: PASS
- `aws-proof-gate`: PASS

## What Closed Gate 3

1. Remote backend was made CI-real (S3 + DynamoDB configured and reachable).
2. CI Terraform proof path remained backend-authoritative (no `-backend=false` in main path).
3. IaC proof harness was hardened for operational determinism:
- empty-state bootstrap handling before first imports
- non-interactive import path with required vars
- stale lock recovery (force-unlock + retry)
4. IAM read permissions required by Terraform import/refresh were extended to include role/OIDC/policy read surfaces.

## What Was Remediated for Gate 5

Branch protection on `main` requires all b11-p1 adjudication checks:
- `ssot-contract-gate`
- `env-boundary-gate`
- `terraform-control-plane-gate`
- `aws-proof-gate`

Evidence:
- `docs/forensics/evidence/b11_p1/branch_protection_main.json`
- `docs/forensics/evidence/b11_p1/branch_protection_required_checks.json`

Additional control-plane hardening applied:
- `required_pull_request_reviews.required_approving_review_count=1` on `main` (direct-push bypass closed).
- Workflow updated to run authoritative backend/state proof in PR adjudication path (removed PR-mode `-backend=false` route).

## Gate 4 Closure (Audit Tether)

- `cloudtrail:LookupEvents` permission was added to `skeldir-ci-deploy` (`tf-backend-access` inline policy).
- `aws-proof-gate` is now passing with CI-role-tethered CloudTrail events:
  - identity includes `arn:aws:sts::326730685463:assumed-role/skeldir-ci-deploy/GitHubActions`
  - lookup execution returns `exit_code=0`
  - proof artifact evaluates `RESULT=PASS`

## Evidence Inventory

- `docs/forensics/evidence/b11_p1/PROOF_INDEX.md`
- `docs/forensics/evidence/b11_p1/B11_P1_CORRECTIVE_REMEDIATION_REPORT.md`
- `docs/forensics/evidence/b11_p1/ssot_contract_snapshot.json`
- `docs/forensics/evidence/b11_p1/deny_proof_cross_env.txt`
- `docs/forensics/evidence/b11_p1/cloudtrail_audit_proof.txt`
- `docs/forensics/evidence/b11_p1/iac_state_proof.txt`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-ci-deploy.json`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-app-runtime-prod.json`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-app-runtime-stage.json`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-rotation-lambda.json`
- `docs/forensics/evidence/b11_p1/branch_protection_main.json`
- `docs/forensics/evidence/b11_p1/branch_protection_required_checks.json`

## Conclusion

All corrective gates are now adjudicated as passing on `main` with CI-derived evidence.

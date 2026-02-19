# B1.1-P1 Findings and Remediations

Date: 2026-02-19
Scope: Secret taxonomy SSOT, environment namespacing, AWS control-plane IaC skeleton, adjudication proofs

## Executive Result

B1.1-P1 is remediated and evidenced for Gates 1-5, including CI adjudication on `main`.

- Gate 1 (SSOT Contract): MET
- Gate 2 (Namespace Boundary + non-vacuous deny): MET
- Gate 3 (IaC state/import evidence): MET (local)
- Gate 4 (CloudTrail audit evidence): MET
- Gate 5 (CI adjudication on `main`): MET

## Findings (Empirical)

1. Initial credential package was invalid
- Symptom: `SignatureDoesNotMatch` / `InvalidSignatureException` across STS/IAM/SSM/CloudTrail.
- Impact: No AWS proof execution possible.

2. Second credential package was valid but under-privileged
- Symptom: STS identity succeeded, but IAM/CloudTrail actions denied by permission boundary.
- Impact: Could not complete IAM introspection, CloudTrail evidence, or Terraform IAM data reads.

3. V3 remediation resolved both credential validity and permission boundary ceiling
- Symptom after V3: live checks pass for identity, IAM role read, CloudTrail lookup, SSM allow/deny probes.
- Impact: Gates 2 and 4 became provable and reproducible.

## Remediations Implemented

### A) Contract-as-Code SSOT (no dual-source taxonomy)
- Added `backend/app/core/managed_settings_contract.py`
- Added `backend/app/core/managed_settings_guard.py`
- Added `scripts/security/b11_p1_ssot_guard.py`
- Added `backend/tests/test_b11_p1_ssot_contract.py`

What this enforces:
- Every `Settings` key must have SSOT metadata.
- Classification must be `secret|config`.
- Path templates must be canonical and env-scoped.
- Snapshot drift is detected (`--check-drift`).

### B) Runtime environment boundary + fail-closed control plane
- Added `backend/app/core/control_plane.py`
- Updated `backend/app/core/config.py`

What this enforces:
- Allowed envs: `prod|stage|ci|dev|local`.
- Canonical path resolution only: `/skeldir/{env}/(config|secret)/*`.
- Optional control-plane preloading/hydration for managed keys.

### C) IaC control-plane skeleton with importable state resources
- Updated `infra/b11_p1/terraform/main.tf`
- Updated `infra/b11_p1/terraform/variables.tf`
- Updated `infra/b11_p1/terraform/outputs.tf`
- Updated `infra/b11_p1/terraform/README.md`

What this enforces:
- Importable resources for OIDC + required IAM roles.
- Env-scoped IAM allow and explicit deny policy skeletons.
- Deterministic placeholder SSM/Secrets namespace resources.
- Role tag drift suppression for imported legacy roles (`lifecycle.ignore_changes` on tags).
- OIDC URL normalization for Terraform provider constraints.

### D) Adjudication and proof harnessing
- Added `.github/workflows/b11-p1-control-plane-adjudication.yml`
- Added `scripts/security/b11_p1_generate_proofs.py`
- Added `scripts/security/b11_p1_iac_state_proof.py`
- Added/updated evidence under `docs/forensics/evidence/b11_p1/`

## Scientific Verification Summary

### Gate 1: SSOT Contract Enforced
Commands:
- `python scripts/security/b11_p1_ssot_guard.py --check-drift`
- `pytest backend/tests/test_b11_p1_ssot_contract.py -q`

Observed:
- Guard PASS (`keys=51`)
- Tests PASS (`3 passed`)

Evidence:
- `docs/forensics/evidence/b11_p1/ssot_contract_snapshot.json`

### Gate 2: Namespace Boundary Proven (non-vacuous)
Commands:
- Allow read: `aws ssm get-parameters-by-path --path /skeldir/ci/config/ --recursive --max-results 1`
- Deny read: `aws ssm get-parameters-by-path --path /skeldir/prod/config/ --recursive --max-results 1`

Observed:
- Allow succeeded.
- Deny returned `AccessDeniedException` with explicit deny text.

Evidence:
- `docs/forensics/evidence/b11_p1/deny_proof_cross_env.txt`

### Gate 3: IaC State + Imports
Commands:
- `terraform fmt -check`
- `terraform init -backend=false`
- `terraform validate`
- `terraform import aws_iam_openid_connect_provider.github_actions ...`
- `terraform import aws_iam_role.runtime_prod ...`
- `terraform import aws_iam_role.runtime_stage ...`
- `terraform import aws_iam_role.ci_deploy ...`
- `terraform import aws_iam_role.rotation_lambda ...`
- `terraform state list`

Observed:
- fmt/init/validate PASS.
- Imports succeeded for OIDC + 4 roles.
- State list includes imported resources.

Evidence:
- `docs/forensics/evidence/b11_p1/iac_state_proof.txt`

### Gate 4: Audit Evidence Produced
Commands:
- `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=GetParametersByPath --max-results 5`
- `aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue --max-results 5`

Observed:
- CloudTrail returns `GetParametersByPath` events for controlled reads, including explicit deny events.

Evidence:
- `docs/forensics/evidence/b11_p1/cloudtrail_audit_proof.txt`

### Gate 5: CI adjudication on `main`
Observed:
- PR merged to `main`: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/101`
- Merge commit on `main`: `b47cab2756adc1196f79b9d34e5c127666ef2bca`
- Main push run passed: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22202994436`
- Job results on that main run:
  - `ssot-contract-gate`: PASS
  - `terraform-control-plane-gate`: PASS
  - `aws-proof-gate`: PASS (OIDC auth + deny proof enforcement + artifact upload)

Status:
- MET

## Evidence Inventory

- `docs/forensics/evidence/b11_p1/PROOF_INDEX.md`
- `docs/forensics/evidence/b11_p1/ssot_contract_snapshot.json`
- `docs/forensics/evidence/b11_p1/deny_proof_cross_env.txt`
- `docs/forensics/evidence/b11_p1/cloudtrail_audit_proof.txt`
- `docs/forensics/evidence/b11_p1/iac_state_proof.txt`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-ci-deploy.json`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-app-runtime-prod.json`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-app-runtime-stage.json`
- `docs/forensics/evidence/b11_p1/iam_policy_skeldir-rotation-lambda.json`
- `docs/forensics/evidence/b11_p1/hypothesis_validation_session_credentials.txt`

## Residual Risk and Closure Action

No unresolved gate blocker remains for B1.1-P1. Follow-on risk is operational drift outside this phase scope; controls are now codified and adjudicated in CI.

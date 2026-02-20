# B11_P1_CORRECTIVE_REMEDIATION_REPORT

Date: 2026-02-20
Branch context: `main` + corrective PRs `#104`, `#105`

## Hypothesis Validation (H01-H05)

### H01 - CI Terraform gate structurally incapable of proving import/state
- Status: VALIDATED
- Evidence:
  - Workflow previously used `terraform init -backend=false` in adjudication path.
  - Script path previously used `-backend=false`.
- Remediation:
  - Main adjudication path now uses remote backend init (no `-backend=false`).

### H02 - Imports were local-only and not reproducible in CI
- Status: VALIDATED
- Evidence:
  - Prior evidence relied on local/import context; CI path with `-backend=false` could not prove state.
- Remediation:
  - Added authoritative main path that requires remote backend and CI state proof script.

### H03 - Remote backend absent/not wired for CI OIDC
- Status: VALIDATED (backend absent)
- Evidence:
  - Main run `22231473702` error: `NoSuchBucket` for `skeldir-b11-p1-tfstate-326730685463-us-east-2`.
  - Main run `22230862590` also showed bootstrap permission mismatch when attempting `CreateBucket` under CI role.
- Remediation attempted:
  - Removed privileged bootstrap mutation from routine CI path.
  - Left explicit preflight + authoritative backend init/state proof path.
- Current state:
  - BLOCKED pending backend creation and backend permissions.

### H04 - Branch protection omitted b11-p1 checks
- Status: VALIDATED then CLOSED
- Evidence:
  - Branch protection now contains required checks in `docs/forensics/evidence/b11_p1/branch_protection_required_checks.json`.
- Remediation:
  - Added required status checks for all four b11-p1 gates.

### H05 - Insufficient GitHub privilege to close Gate 5
- Status: REFUTED (in active execution context)
- Evidence:
  - Active GitHub context had admin capability to patch branch protection.

## Exact Remediation Performed

1. Workflow and script corrections
- `.github/workflows/b11-p1-control-plane-adjudication.yml`
  - PR path: static terraform preflight only.
  - Main path: OIDC + remote backend init + state proof script.
  - Removed per-run privileged S3/DynamoDB mutation attempts.
- `scripts/security/b11_p1_iac_state_proof.py`
  - Requires backend env vars.
  - Remote backend init.
  - Import/state show/plan no-op proof semantics.

2. Branch protection enforcement
- Updated `main` required status checks to include:
  - `ssot-contract-gate`
  - `env-boundary-gate`
  - `terraform-control-plane-gate`
  - `aws-proof-gate`
- Evidence:
  - `docs/forensics/evidence/b11_p1/branch_protection_main.json`
  - `docs/forensics/evidence/b11_p1/branch_protection_required_checks.json`

3. Evidence updates
- `docs/forensics/evidence/b11_p1/PROOF_INDEX.md`
- `docs/forensics/evidence/b11_p1/B11_P1_FINDINGS_AND_REMEDIATIONS.md`
- `docs/forensics/evidence/b11_p1/iac_backend_blocker.txt`

## Gate Statements

- Gate 3 now CI-verifiable: PARTIALLY TRUE
  - Path is CI-correct and remote-backend-based.
  - Final proof is BLOCKED by missing backend bucket/table.
- Gate 5 now non-bypassable: TRUE
  - Required checks are in branch protection and enforced on `main`.

## Minimal Unblock Request (AWS Admin)

Provision backend resources in account `326730685463`, region `us-east-2`:
- S3 bucket: `skeldir-b11-p1-tfstate-326730685463-us-east-2`
- DynamoDB table: `skeldir-b11-p1-tf-locks` with hash key `LockID` (S)

Grant role `skeldir-ci-deploy`:
- S3 bucket permissions:
  - `s3:ListBucket` on bucket ARN
  - `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on `arn:aws:s3:::skeldir-b11-p1-tfstate-326730685463-us-east-2/b11-p1/terraform.tfstate*`
- DynamoDB lock permissions:
  - `dynamodb:DescribeTable`, `GetItem`, `PutItem`, `DeleteItem`, `UpdateItem` on lock table ARN

Suggested one-time CLI (admin context):
```bash
aws s3api create-bucket \
  --bucket skeldir-b11-p1-tfstate-326730685463-us-east-2 \
  --region us-east-2 \
  --create-bucket-configuration LocationConstraint=us-east-2

aws s3api put-bucket-versioning \
  --bucket skeldir-b11-p1-tfstate-326730685463-us-east-2 \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket skeldir-b11-p1-tfstate-326730685463-us-east-2 \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block \
  --bucket skeldir-b11-p1-tfstate-326730685463-us-east-2 \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws dynamodb create-table \
  --region us-east-2 \
  --table-name skeldir-b11-p1-tf-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

## Final Phase Judgment

- Gate 5: MET (non-bypassable control-plane enforcement is in place).
- Gate 3: BLOCKED (backend infra missing).
- B1.1-P1 remains FAIL/BLOCKED until backend resources are provisioned and main adjudication re-run passes with remote state proofs.

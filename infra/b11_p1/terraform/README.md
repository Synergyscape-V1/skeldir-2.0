# B1.1-P1 Terraform Control-Plane

Authoritative IaC for managed secret/config namespace and IAM prefix boundaries.

- Account: `326730685463`
- Region: `us-east-2`
- Canonical paths:
  - Secrets Manager: `/skeldir/{env}/secret/*`
  - SSM Parameter Store: `/skeldir/{env}/config/*`

## Scope
- Env namespace policy skeleton for runtime and CI roles.
- Deterministic placeholder resources for managed Secrets/SSM keys.
- Data assertions for required pre-existing resources:
  - OIDC provider `token.actions.githubusercontent.com`
  - Roles `skeldir-app-runtime-prod`, `skeldir-app-runtime-stage`, `skeldir-ci-deploy`, `skeldir-rotation-lambda`

## Usage
1. Export context:
- `AWS_PROFILE=<profile>`
- `TF_VAR_environment=ci` (or `prod|stage|dev|local`)
- `TF_VAR_manage_prefix_policies=false` for CI state-verification runs
- `TF_VAR_manage_namespace_placeholders=false` for CI state-verification runs

2. Run plan:
```bash
terraform init \
  -backend-config="bucket=<state-bucket>" \
  -backend-config="key=b11-p1/terraform.tfstate" \
  -backend-config="region=us-east-2" \
  -backend-config="dynamodb_table=<lock-table>" \
  -backend-config="encrypt=true"
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

3. Apply only via reviewed plan:
```bash
terraform apply tfplan
```

## Import Runbook (IaC-only, no ClickOps)
Import existing IAM/OIDC resources into state before first apply:

```bash
terraform import aws_iam_openid_connect_provider.github_actions arn:aws:iam::326730685463:oidc-provider/token.actions.githubusercontent.com
terraform import aws_iam_role.runtime_prod skeldir-app-runtime-prod
terraform import aws_iam_role.runtime_stage skeldir-app-runtime-stage
terraform import aws_iam_role.ci_deploy skeldir-ci-deploy
terraform import aws_iam_role.rotation_lambda skeldir-rotation-lambda
```

Then run `terraform plan` and review managed policy attachment changes.

## CI State Verification Mode

`b11-p1-control-plane-adjudication` validates imported state deterministically with:
- remote S3 backend + DynamoDB state lock (no `-backend=false`)
- imports for OIDC + 4 IAM roles if state is missing
- `terraform state list` and `terraform state show` proof artifacts
- `terraform plan -detailed-exitcode` expected to return `0` (no changes)

This run intentionally keeps:
- `manage_prefix_policies=false`
- `manage_namespace_placeholders=false`

to verify imported control-plane skeleton state without creating non-imported placeholder resources in CI.

## Enforcement
- `environment` is fail-closed to `prod|stage|ci|dev|local`.
- IAM policies are env-prefix-scoped, preventing cross-env reads by design.
- Drift-check is monitoring only; Terraform state is the authority.

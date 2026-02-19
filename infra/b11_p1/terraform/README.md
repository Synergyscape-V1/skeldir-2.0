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

2. Run plan:
```bash
terraform init
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

## Enforcement
- `environment` is fail-closed to `prod|stage|ci|dev|local`.
- IAM policies are env-prefix-scoped, preventing cross-env reads by design.
- Drift-check is monitoring only; Terraform state is the authority.

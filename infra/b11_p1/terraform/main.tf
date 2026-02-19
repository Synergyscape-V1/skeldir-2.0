locals {
  secret_prefix = "/skeldir/${var.environment}/secret"
  config_prefix = "/skeldir/${var.environment}/config"

  env_prefixes = {
    prod  = "/skeldir/prod"
    stage = "/skeldir/stage"
    ci    = "/skeldir/ci"
    dev   = "/skeldir/dev"
    local = "/skeldir/local"
  }

  managed_secret_placeholders = {
    for env in var.provision_environments :
    env => [
      "/skeldir/${env}/secret/auth/jwt-secret",
      "/skeldir/${env}/secret/platform/token-encryption-key",
      "/skeldir/${env}/secret/database/runtime-url",
      "/skeldir/${env}/secret/celery/broker-url",
      "/skeldir/${env}/secret/celery/result-backend-url",
    ]
  }

  managed_config_placeholders = {
    for env in var.provision_environments :
    env => {
      "/skeldir/${env}/config/tenant/api-key-header"           = "X-Skeldir-Tenant-Key"
      "/skeldir/${env}/config/auth/jwt-issuer"                 = "https://issuer.skeldir.${env}"
      "/skeldir/${env}/config/auth/jwt-audience"               = "skeldir-api"
      "/skeldir/${env}/config/runtime/environment"             = env
      "/skeldir/${env}/config/ingestion/idempotency-cache-ttl" = "86400"
    }
  }

  secret_placeholder_records = flatten([
    for env, names in local.managed_secret_placeholders : [
      for name in names : {
        key  = "${env}:${name}"
        env  = env
        name = name
      }
    ]
  ])

  config_placeholder_records = flatten([
    for env, kv in local.managed_config_placeholders : [
      for name, value in kv : {
        key   = "${env}:${name}"
        env   = env
        name  = name
        value = value
      }
    ]
  ])

  github_oidc_live_url = data.aws_iam_openid_connect_provider.github_actions_live.url
  github_oidc_url      = startswith(local.github_oidc_live_url, "https://") ? local.github_oidc_live_url : "https://${local.github_oidc_live_url}"
}

data "aws_caller_identity" "current" {}

data "aws_iam_openid_connect_provider" "github_actions_live" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_role" "runtime_prod_live" {
  name = var.runtime_prod_role_name
}

data "aws_iam_role" "runtime_stage_live" {
  name = var.runtime_stage_role_name
}

data "aws_iam_role" "ci_deploy_live" {
  name = var.ci_deploy_role_name
}

data "aws_iam_role" "rotation_lambda_live" {
  name = var.rotation_lambda_role_name
}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = local.github_oidc_url
  client_id_list  = data.aws_iam_openid_connect_provider.github_actions_live.client_id_list
  thumbprint_list = data.aws_iam_openid_connect_provider.github_actions_live.thumbprint_list
}

resource "aws_iam_role" "runtime_prod" {
  name                 = data.aws_iam_role.runtime_prod_live.name
  assume_role_policy   = data.aws_iam_role.runtime_prod_live.assume_role_policy
  description          = data.aws_iam_role.runtime_prod_live.description
  max_session_duration = data.aws_iam_role.runtime_prod_live.max_session_duration
  permissions_boundary = data.aws_iam_role.runtime_prod_live.permissions_boundary
  path                 = data.aws_iam_role.runtime_prod_live.path

  lifecycle {
    ignore_changes = [
      tags,
      tags_all,
    ]
  }
}

resource "aws_iam_role" "runtime_stage" {
  name                 = data.aws_iam_role.runtime_stage_live.name
  assume_role_policy   = data.aws_iam_role.runtime_stage_live.assume_role_policy
  description          = data.aws_iam_role.runtime_stage_live.description
  max_session_duration = data.aws_iam_role.runtime_stage_live.max_session_duration
  permissions_boundary = data.aws_iam_role.runtime_stage_live.permissions_boundary
  path                 = data.aws_iam_role.runtime_stage_live.path

  lifecycle {
    ignore_changes = [
      tags,
      tags_all,
    ]
  }
}

resource "aws_iam_role" "ci_deploy" {
  name                 = data.aws_iam_role.ci_deploy_live.name
  assume_role_policy   = data.aws_iam_role.ci_deploy_live.assume_role_policy
  description          = data.aws_iam_role.ci_deploy_live.description
  max_session_duration = data.aws_iam_role.ci_deploy_live.max_session_duration
  permissions_boundary = data.aws_iam_role.ci_deploy_live.permissions_boundary
  path                 = data.aws_iam_role.ci_deploy_live.path

  lifecycle {
    ignore_changes = [
      tags,
      tags_all,
    ]
  }
}

resource "aws_iam_role" "rotation_lambda" {
  name                 = data.aws_iam_role.rotation_lambda_live.name
  assume_role_policy   = data.aws_iam_role.rotation_lambda_live.assume_role_policy
  description          = data.aws_iam_role.rotation_lambda_live.description
  max_session_duration = data.aws_iam_role.rotation_lambda_live.max_session_duration
  permissions_boundary = data.aws_iam_role.rotation_lambda_live.permissions_boundary
  path                 = data.aws_iam_role.rotation_lambda_live.path

  lifecycle {
    ignore_changes = [
      tags,
      tags_all,
    ]
  }
}

resource "aws_iam_policy" "runtime_prod_secret_read" {
  name        = "skeldir-runtime-prod-secret-read"
  description = "Least-privilege read access to /skeldir/prod config/secret namespaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowReadProdPrefix"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/prod/config/*"
      },
      {
        Sid    = "AllowReadProdSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/prod/secret/*"
      },
      {
        Sid    = "DenyReadNonProd"
        Effect = "Deny"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/stage/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/ci/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/dev/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/local/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/stage/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/ci/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/dev/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/local/*"
        ]
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_policy" "runtime_stage_secret_read" {
  name        = "skeldir-runtime-stage-secret-read"
  description = "Least-privilege read access to /skeldir/stage config/secret namespaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowReadStagePrefix"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/stage/config/*"
      },
      {
        Sid    = "AllowReadStageSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/stage/secret/*"
      },
      {
        Sid    = "DenyReadNonStage"
        Effect = "Deny"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/prod/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/ci/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/dev/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/local/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/prod/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/ci/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/dev/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/local/*"
        ]
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_policy" "ci_secret_read" {
  name        = "skeldir-ci-secret-read"
  description = "CI read access constrained to /skeldir/ci namespaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowReadCiPrefix"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/ci/config/*"
      },
      {
        Sid    = "AllowReadCiSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/ci/secret/*"
      },
      {
        Sid    = "DenyReadNonCi"
        Effect = "Deny"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/prod/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/stage/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/dev/*",
          "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter/skeldir/local/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/prod/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/stage/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/dev/*",
          "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:/skeldir/local/*"
        ]
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "runtime_prod_secret_read" {
  role       = aws_iam_role.runtime_prod.name
  policy_arn = aws_iam_policy.runtime_prod_secret_read.arn
}

resource "aws_iam_role_policy_attachment" "runtime_stage_secret_read" {
  role       = aws_iam_role.runtime_stage.name
  policy_arn = aws_iam_policy.runtime_stage_secret_read.arn
}

resource "aws_iam_role_policy_attachment" "ci_secret_read" {
  role       = aws_iam_role.ci_deploy.name
  policy_arn = aws_iam_policy.ci_secret_read.arn
}

resource "aws_secretsmanager_secret" "managed_placeholders" {
  for_each = {
    for rec in local.secret_placeholder_records :
    rec.key => rec
  }

  name        = each.value.name
  description = "B11-P1 managed placeholder for ${each.value.key}"
  tags        = merge(var.tags, { environment = each.value.env })
}

resource "aws_ssm_parameter" "managed_config_placeholders" {
  for_each = {
    for rec in local.config_placeholder_records :
    rec.key => rec
  }

  name  = each.value.name
  type  = "String"
  value = each.value.value
  tags  = merge(var.tags, { environment = each.value.env })
}

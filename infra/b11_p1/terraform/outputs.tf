output "account_id_observed" {
  value = data.aws_caller_identity.current.account_id
}

output "secret_prefix" {
  value = "/skeldir/${var.environment}/secret"
}

output "config_prefix" {
  value = "/skeldir/${var.environment}/config"
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github_actions.arn
}

output "runtime_prod_role_arn" {
  value = aws_iam_role.runtime_prod.arn
}

output "runtime_stage_role_arn" {
  value = aws_iam_role.runtime_stage.arn
}

output "ci_role_arn" {
  value = aws_iam_role.ci_deploy.arn
}

output "rotation_lambda_role_arn" {
  value = aws_iam_role.rotation_lambda.arn
}

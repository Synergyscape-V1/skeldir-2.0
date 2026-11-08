locals {
  process_authority = jsondecode(
    file("${path.module}/../../../contracts-internal/governance/b11_process_authority.v1.json")
  )

  process_role_instances = {
    for pair in setproduct(local.process_authority.environments, keys(local.process_authority.processes)) :
    "${pair[0]}:${pair[1]}" => {
      environment = pair[0]
      process     = pair[1]
      config      = local.process_authority.processes[pair[1]].config
      secrets     = local.process_authority.processes[pair[1]].secrets
    }
  }

  process_boundary = {
    prod  = data.aws_iam_role.runtime_prod_live.permissions_boundary
    stage = data.aws_iam_role.runtime_stage_live.permissions_boundary
  }
}

resource "aws_iam_role" "process_runtime" {
  for_each = local.process_role_instances

  name                 = "skeldir-${each.value.process}-${each.value.environment}"
  description          = "Process-scoped runtime role for ${each.value.process} in ${each.value.environment}"
  permissions_boundary = local.process_boundary[each.value.environment]

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECSTaskAssumption"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    environment = each.value.environment
    process     = each.value.process
  })
}

resource "aws_iam_policy" "process_runtime" {
  for_each = local.process_role_instances

  name        = "skeldir-${each.value.process}-${each.value.environment}-authority"
  description = "Exact managed-setting paths for ${each.value.process} in ${each.value.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        for path in each.value.config : {
          Sid      = "ReadConfig${substr(md5(path), 0, 20)}"
          Effect   = "Allow"
          Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
          Resource = "arn:aws:ssm:${var.aws_region}:${var.account_id}:parameter${replace(path, "{env}", each.value.environment)}"
        }
      ],
      [
        for path in each.value.secrets : {
          Sid      = "ReadSecret${substr(md5(path), 0, 20)}"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
          Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${replace(path, "{env}", each.value.environment)}-??????"
        }
      ],
      [
        {
          Sid      = "DecryptManagedSettings"
          Effect   = "Allow"
          Action   = ["kms:Decrypt", "kms:DescribeKey"]
          Resource = "arn:aws:kms:${var.aws_region}:${var.account_id}:key/*"
        }
      ]
    )
  })

  tags = merge(var.tags, {
    environment = each.value.environment
    process     = each.value.process
  })
}

resource "aws_iam_role_policy_attachment" "process_runtime" {
  for_each = local.process_role_instances

  role       = aws_iam_role.process_runtime[each.key].name
  policy_arn = aws_iam_policy.process_runtime[each.key].arn
}

output "process_runtime_role_arns" {
  value = {
    for key, role in aws_iam_role.process_runtime : key => role.arn
  }
}

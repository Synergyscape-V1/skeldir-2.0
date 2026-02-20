variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
  default     = "326730685463"
}

variable "environment" {
  description = "Deployment environment (prod|stage|ci|dev|local)"
  type        = string

  validation {
    condition     = contains(["prod", "stage", "ci", "dev", "local"], var.environment)
    error_message = "environment must be one of: prod, stage, ci, dev, local"
  }
}

variable "provision_environments" {
  description = "Environments to provision baseline placeholders for"
  type        = set(string)
  default     = ["ci", "stage", "prod", "dev"]

  validation {
    condition = alltrue([
      for env in var.provision_environments :
      contains(["prod", "stage", "ci", "dev", "local"], env)
    ])
    error_message = "provision_environments must only include: prod, stage, ci, dev, local"
  }
}

variable "runtime_prod_role_name" {
  description = "Runtime production role name"
  type        = string
  default     = "skeldir-app-runtime-prod"
}

variable "runtime_stage_role_name" {
  description = "Runtime stage role name"
  type        = string
  default     = "skeldir-app-runtime-stage"
}

variable "ci_deploy_role_name" {
  description = "CI deploy role name"
  type        = string
  default     = "skeldir-ci-deploy"
}

variable "rotation_lambda_role_name" {
  description = "Rotation lambda role name"
  type        = string
  default     = "skeldir-rotation-lambda"
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default = {
    system = "skeldir"
    phase  = "b11-p1"
  }
}

variable "manage_prefix_policies" {
  description = "Whether Terraform should create/attach env prefix IAM policies."
  type        = bool
  default     = false
}

variable "manage_namespace_placeholders" {
  description = "Whether Terraform should create SSM/Secrets placeholder resources."
  type        = bool
  default     = false
}

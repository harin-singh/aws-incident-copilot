# AWS Bedrock AgentCore Module for Incident Copilot
#
# This module deploys the incident copilot on Amazon Bedrock AgentCore Runtime.
# It creates:
# - ECR repository for the container image
# - AgentCore Runtime for the agent
# - AgentCore Gateway for MCP tool access (optional)
# - IAM roles with least-privilege permissions
# - CloudWatch log groups for observability
#
# Requirements:
# - AWS Provider >= 6.18.0 (first version with aws_bedrockagentcore_* resources)
# - Docker image must be built and pushed to ECR before creating the runtime

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.18.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  region        = data.aws_region.current.id
  name_prefix   = "${var.project_name}-${var.environment}"
  runtime_name  = replace("${local.name_prefix}_runtime", "-", "_")
  gateway_name  = "${local.name_prefix}-gateway"
  ecr_repo_name = "${local.name_prefix}-agent"
  container_uri = var.container_image_uri != "" ? var.container_image_uri : "${aws_ecr_repository.agent[0].repository_url}:${var.image_tag}"
}

# -----------------------------------------------------------------------------
# ECR Repository
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "agent" {
  count = var.create_ecr_repository ? 1 : 0

  name                 = local.ecr_repo_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "agent" {
  count = var.create_ecr_repository ? 1 : 0

  repository = aws_ecr_repository.agent[0].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# IAM Role for AgentCore Runtime Execution
# -----------------------------------------------------------------------------

resource "aws_iam_role" "runtime_execution" {
  name = "${local.name_prefix}-agentcore-runtime"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      }
    ]
  })
}

# CloudWatch Logs permissions for runtime
#checkov:skip=CKV_AWS_355:Read-only logging permissions required for investigation across all log groups
resource "aws_iam_role_policy" "runtime_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.runtime_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/agentcore/*"
        ]
      }
    ]
  })
}

# Bedrock model invocation for the agent
resource "aws_iam_role_policy" "runtime_bedrock" {
  name = "bedrock-invoke"
  role = aws_iam_role.runtime_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${local.region}::foundation-model/${var.bedrock_model_id}",
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-*"
        ]
      }
    ]
  })
}

# CloudWatch read access for investigation (read-only)
#checkov:skip=CKV_AWS_355:Read-only investigation requires access to all CloudWatch resources
resource "aws_iam_role_policy" "runtime_cloudwatch_read" {
  name = "cloudwatch-investigation"
  role = aws_iam_role.runtime_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsRead"
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
          "logs:StartQuery",
          "logs:GetQueryResults",
          "logs:StopQuery"
        ]
        Resource = [
          "arn:aws:logs:${local.region}:${local.account_id}:log-group:*"
        ]
      },
      {
        Sid    = "CloudWatchMetricsRead"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:DescribeAlarmHistory"
        ]
        Resource = "*"
      }
    ]
  })
}

# ECS read access for investigation
#checkov:skip=CKV_AWS_355:Read-only ECS investigation requires listing/describing any cluster, service, task
resource "aws_iam_role_policy" "runtime_ecs_read" {
  name = "ecs-investigation"
  role = aws_iam_role.runtime_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECSRead"
        Effect = "Allow"
        Action = [
          "ecs:DescribeClusters",
          "ecs:DescribeServices",
          "ecs:DescribeTasks",
          "ecs:DescribeTaskDefinition",
          "ecs:ListClusters",
          "ecs:ListServices",
          "ecs:ListTasks"
        ]
        Resource = "*"
      }
    ]
  })
}

# EKS read access for investigation
#checkov:skip=CKV_AWS_355:Read-only EKS investigation requires listing/describing any cluster
resource "aws_iam_role_policy" "runtime_eks_read" {
  name = "eks-investigation"
  role = aws_iam_role.runtime_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EKSDescribe"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters",
          "eks:DescribeNodegroup",
          "eks:ListNodegroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# ECR pull permissions (to pull the container image)
resource "aws_iam_role_policy" "runtime_ecr" {
  name = "ecr-pull"
  role = aws_iam_role.runtime_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
        Resource = var.create_ecr_repository ? aws_ecr_repository.agent[0].arn : "arn:aws:ecr:${local.region}:${local.account_id}:repository/${local.ecr_repo_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# IAM Role for Remediation (separate, restricted)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "remediation" {
  count = var.enable_remediation ? 1 : 0

  name = "${local.name_prefix}-agentcore-remediation"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.runtime_execution.arn
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "incident-copilot-remediation"
          }
        }
      }
    ]
  })
}

# ECS remediation (restart services, update desired count)
resource "aws_iam_role_policy" "remediation_ecs" {
  count = var.enable_remediation ? 1 : 0

  name = "ecs-remediation"
  role = aws_iam_role.remediation[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECSServiceUpdate"
        Effect = "Allow"
        Action = [
          "ecs:UpdateService"
        ]
        Resource = [
          "arn:aws:ecs:${local.region}:${local.account_id}:service/*/*"
        ]
        Condition = {
          StringEquals = {
            "aws:ResourceTag/AllowIncidentCopilot" = "true"
          }
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# AgentCore Runtime
# -----------------------------------------------------------------------------

resource "aws_bedrockagentcore_agent_runtime" "agent" {
  count = var.deploy_runtime ? 1 : 0

  agent_runtime_name = local.runtime_name
  role_arn           = aws_iam_role.runtime_execution.arn
  description        = "AWS Incident Copilot - AI-powered incident investigation agent"

  agent_runtime_artifact {
    container_configuration {
      container_uri = local.container_uri
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  environment_variables = merge(
    {
      DEMO_MODE     = var.demo_mode ? "true" : "false"
      DEMO_SCENARIO = var.demo_scenario
      LOG_LEVEL     = var.log_level
      AWS_REGION    = local.region
    },
    var.extra_environment_variables
  )

  lifecycle_configuration {
    idle_runtime_session_timeout = var.session_ttl_seconds
  }

  depends_on = [
    aws_iam_role_policy.runtime_logs,
    aws_iam_role_policy.runtime_bedrock,
    aws_iam_role_policy.runtime_cloudwatch_read,
    aws_iam_role_policy.runtime_ecs_read,
    aws_iam_role_policy.runtime_eks_read,
    aws_iam_role_policy.runtime_ecr,
  ]
}

# -----------------------------------------------------------------------------
# AgentCore Gateway (optional, for MCP tool access)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "gateway" {
  count = var.enable_gateway ? 1 : 0

  name = "${local.name_prefix}-agentcore-gateway"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      }
    ]
  })
}

resource "aws_bedrockagentcore_gateway" "main" {
  count = var.enable_gateway ? 1 : 0

  name            = local.gateway_name
  role_arn        = aws_iam_role.gateway[0].arn
  description     = "MCP Gateway for AWS Incident Copilot investigation tools"
  authorizer_type = "AWS_IAM"

  depends_on = [
    aws_iam_role.gateway
  ]
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group
# -----------------------------------------------------------------------------

#checkov:skip=CKV_AWS_158:KMS encryption optional; enable via kms_key_id variable for production
#checkov:skip=CKV_AWS_338:30-day retention is intentional default for cost; increase via log_retention_days variable
resource "aws_cloudwatch_log_group" "agentcore" {
  name              = "/aws/agentcore/${local.name_prefix}"
  retention_in_days = var.log_retention_days
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "ecr_repository_url" {
  description = "ECR repository URL for the agent container image"
  value       = var.create_ecr_repository ? aws_ecr_repository.agent[0].repository_url : null
}

output "runtime_execution_role_arn" {
  description = "IAM role ARN for the AgentCore runtime"
  value       = aws_iam_role.runtime_execution.arn
}

output "remediation_role_arn" {
  description = "IAM role ARN for remediation actions"
  value       = var.enable_remediation ? aws_iam_role.remediation[0].arn : null
}

output "agent_runtime_id" {
  description = "AgentCore Runtime ID"
  value       = var.deploy_runtime ? aws_bedrockagentcore_agent_runtime.agent[0].agent_runtime_id : null
}

output "agent_runtime_arn" {
  description = "AgentCore Runtime ARN"
  value       = var.deploy_runtime ? aws_bedrockagentcore_agent_runtime.agent[0].agent_runtime_arn : null
}

output "gateway_id" {
  description = "AgentCore Gateway ID"
  value       = var.enable_gateway ? aws_bedrockagentcore_gateway.main[0].gateway_id : null
}

output "gateway_endpoint" {
  description = "AgentCore Gateway ID (use with AWS API to invoke)"
  value       = var.enable_gateway ? aws_bedrockagentcore_gateway.main[0].gateway_id : null
}

output "log_group_name" {
  description = "CloudWatch log group for AgentCore logs"
  value       = aws_cloudwatch_log_group.agentcore.name
}

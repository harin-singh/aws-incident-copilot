# AWS Incident Copilot - Terraform Configuration
#
# This Terraform configuration deploys the infrastructure for running
# AWS Incident Copilot in live mode, including:
# - IAM roles with least-privilege permissions
# - Lambda function for Bedrock agent invocation
# - CloudWatch resources for monitoring
# - EventBridge rules for alert triggering
#
# IMPORTANT: Review and customize before deployment.
# Estimated cost: ~$5-15/month depending on usage.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Note: >= 6.18.0 required for aws_bedrockagentcore_* resources
      # Using ~> 6.18 when enable_agentcore = true
      version = ">= 5.0.0"
    }
  }

  # For production, configure remote state
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "incident-copilot/terraform.tfstate"
  #   region = "us-west-2"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aws-incident-copilot"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "incident-copilot"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID for the agent"
  type        = string
  default     = "anthropic.claude-3-sonnet-20240229-v1:0"
}

variable "eks_cluster_names" {
  description = "List of EKS cluster names to monitor"
  type        = list(string)
  default     = []
}

variable "ecs_cluster_names" {
  description = "List of ECS cluster names to monitor"
  type        = list(string)
  default     = []
}

variable "alert_sns_topic_arn" {
  description = "SNS topic ARN for sending incident alerts"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# AgentCore Configuration (Optional)
# -----------------------------------------------------------------------------

variable "enable_agentcore" {
  description = "Enable Amazon Bedrock AgentCore deployment"
  type        = bool
  default     = false
}

variable "agentcore_image_tag" {
  description = "Docker image tag for AgentCore deployment"
  type        = string
  default     = "latest"
}

variable "agentcore_demo_mode" {
  description = "Run AgentCore in demo mode (fixture data)"
  type        = bool
  default     = false
}

variable "agentcore_enable_gateway" {
  description = "Enable AgentCore Gateway for MCP tools"
  type        = bool
  default     = false
}

variable "agentcore_enable_remediation" {
  description = "Enable remediation role for AgentCore"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.id
  name_prefix = "${var.project_name}-${var.environment}"
}

# -----------------------------------------------------------------------------
# IAM Role for Incident Copilot
# -----------------------------------------------------------------------------

resource "aws_iam_role" "incident_copilot" {
  name = "${local.name_prefix}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "bedrock.amazonaws.com"
          ]
        }
      }
    ]
  })
}

# CloudWatch Logs - Read access for log investigation
resource "aws_iam_role_policy" "cloudwatch_logs" {
  name = "cloudwatch-logs-read"
  role = aws_iam_role.incident_copilot.id

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
      }
    ]
  })
}

# CloudWatch Metrics - Read access for metrics investigation
resource "aws_iam_role_policy" "cloudwatch_metrics" {
  name = "cloudwatch-metrics-read"
  role = aws_iam_role.incident_copilot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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

# EKS - Read access for cluster investigation
resource "aws_iam_role_policy" "eks_read" {
  name = "eks-read"
  role = aws_iam_role.incident_copilot.id

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

# ECS - Read access for service investigation
resource "aws_iam_role_policy" "ecs_read" {
  name = "ecs-read"
  role = aws_iam_role.incident_copilot.id

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

# Bedrock - Invoke models for AI analysis
resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "bedrock-invoke"
  role = aws_iam_role.incident_copilot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvoke"
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

# Lambda execution - Basic Lambda permissions
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.incident_copilot.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# -----------------------------------------------------------------------------
# Remediation IAM Role (separate, more restricted)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "remediation" {
  name = "${local.name_prefix}-remediation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.incident_copilot.arn
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "incident-copilot-remediation"
          }
        }
      }
    ]
  })
}

# ECS remediation actions (with explicit conditions)
resource "aws_iam_role_policy" "ecs_remediation" {
  name = "ecs-remediation"
  role = aws_iam_role.remediation.id

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
# CloudWatch Log Group for Incident Copilot
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "incident_copilot" {
  name              = "/aws/incident-copilot/${var.environment}"
  retention_in_days = 30
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms for Self-Monitoring
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "copilot_errors" {
  alarm_name          = "${local.name_prefix}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Incident Copilot Lambda errors"

  dimensions = {
    FunctionName = "${local.name_prefix}-handler"
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []
}

# -----------------------------------------------------------------------------
# EventBridge Rule for CloudWatch Alarm State Changes
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "alarm_state_change" {
  name        = "${local.name_prefix}-alarm-trigger"
  description = "Trigger incident copilot on CloudWatch alarm state changes"

  event_pattern = jsonencode({
    source      = ["aws.cloudwatch"]
    detail-type = ["CloudWatch Alarm State Change"]
    detail = {
      state = {
        value = ["ALARM"]
      }
    }
  })
}

# -----------------------------------------------------------------------------
# AgentCore Module (Optional)
# -----------------------------------------------------------------------------

module "agentcore" {
  source = "./modules/agentcore"
  count  = var.enable_agentcore ? 1 : 0

  project_name     = var.project_name
  environment      = var.environment
  bedrock_model_id = var.bedrock_model_id

  # ECR and Image
  create_ecr_repository = true
  image_tag             = var.agentcore_image_tag

  # Runtime
  deploy_runtime = true
  network_mode   = "PUBLIC"
  demo_mode      = var.agentcore_demo_mode
  demo_scenario  = "crashloop"

  # Gateway and Remediation
  enable_gateway     = var.agentcore_enable_gateway
  enable_remediation = var.agentcore_enable_remediation

  # Observability
  log_retention_days = 30
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "copilot_role_arn" {
  description = "IAM role ARN for the incident copilot"
  value       = aws_iam_role.incident_copilot.arn
}

output "remediation_role_arn" {
  description = "IAM role ARN for remediation actions"
  value       = aws_iam_role.remediation.arn
}

output "log_group_name" {
  description = "CloudWatch log group for incident copilot logs"
  value       = aws_cloudwatch_log_group.incident_copilot.name
}

output "region" {
  description = "AWS region where resources are deployed"
  value       = local.region
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost (USD)"
  value       = "~$5-15 depending on Bedrock usage"
}

# AgentCore Outputs (when enabled)
output "agentcore_ecr_repository_url" {
  description = "ECR repository URL for AgentCore container image"
  value       = var.enable_agentcore ? module.agentcore[0].ecr_repository_url : null
}

output "agentcore_runtime_id" {
  description = "AgentCore Runtime ID"
  value       = var.enable_agentcore ? module.agentcore[0].agent_runtime_id : null
}

output "agentcore_runtime_role_arn" {
  description = "AgentCore Runtime execution role ARN"
  value       = var.enable_agentcore ? module.agentcore[0].runtime_execution_role_arn : null
}

output "agentcore_gateway_endpoint" {
  description = "AgentCore Gateway endpoint URL (if enabled)"
  value       = var.enable_agentcore && var.agentcore_enable_gateway ? module.agentcore[0].gateway_endpoint : null
}

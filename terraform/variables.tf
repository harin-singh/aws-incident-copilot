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
  description = "Bedrock inference profile ID (geographic prefix required for current Claude models)"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "bedrock_foundation_model_id" {
  description = "Underlying foundation model ID without the geographic inference-profile prefix"
  type        = string
  default     = "anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "eks_cluster_names" {
  description = "EKS cluster names to grant investigation/remediation access entries"
  type        = list(string)
  default     = []
}

variable "eks_remediation_namespaces" {
  description = "Namespaces the remediation role may edit. Empty = cluster-scoped edit."
  type        = list(string)
  default     = ["production"]
}

variable "ecs_cluster_names" {
  description = "ECS cluster names the copilot is expected to investigate (documentation / tagging)"
  type        = list(string)
  default     = []
}

variable "alert_sns_topic_arn" {
  description = "SNS topic ARN for copilot Lambda error alarms"
  type        = string
  default     = ""
}

variable "remediation_external_id" {
  description = "Optional ExternalId for assuming the remediation role (cross-account). Null for same-account."
  type        = string
  default     = null
  sensitive   = true
}

variable "enable_agentcore" {
  description = "Enable Amazon Bedrock AgentCore deployment"
  type        = bool
  default     = false
}

variable "agentcore_image_tag" {
  description = "Immutable Docker image tag for AgentCore (do not use latest; ECR tags are immutable)"
  type        = string
  default     = "0.1.0"
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

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

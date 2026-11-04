# Variables for AgentCore Module

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "incident-copilot"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "bedrock_model_id" {
  description = "Bedrock inference profile ID for the agent"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "bedrock_foundation_model_id" {
  description = "Underlying foundation model ID without the geographic prefix"
  type        = string
  default     = "anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "remediation_external_id" {
  description = "Optional ExternalId for the remediation role. Null for same-account."
  type        = string
  default     = null
  sensitive   = true
}

variable "eks_cluster_names" {
  description = "EKS clusters that receive access entries for the runtime/remediation roles"
  type        = list(string)
  default     = []
}

variable "eks_remediation_namespaces" {
  description = "Namespaces the AgentCore remediation role may edit"
  type        = list(string)
  default     = ["production"]
}

# ECR Configuration
variable "create_ecr_repository" {
  description = "Whether to create an ECR repository for the agent image"
  type        = bool
  default     = true
}

variable "container_image_uri" {
  description = "Full container image URI. If empty, uses the created ECR repository"
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Immutable Docker image tag to pull from ECR"
  type        = string
  default     = "0.1.0"
}

# Runtime Configuration
variable "deploy_runtime" {
  description = "Whether to deploy the AgentCore Runtime (set false if only building image)"
  type        = bool
  default     = true
}

variable "network_mode" {
  description = "Network mode for the runtime (PUBLIC or VPC)"
  type        = string
  default     = "PUBLIC"

  validation {
    condition     = contains(["PUBLIC", "VPC"], var.network_mode)
    error_message = "network_mode must be either PUBLIC or VPC"
  }
}

variable "session_ttl_seconds" {
  description = "Idle session timeout in seconds (how long idle sessions persist)"
  type        = number
  default     = 3600

  validation {
    condition     = var.session_ttl_seconds >= 60 && var.session_ttl_seconds <= 86400
    error_message = "session_ttl_seconds must be between 60 and 86400"
  }
}

# Demo Configuration
variable "demo_mode" {
  description = "Enable demo mode (uses fixture data instead of AWS APIs)"
  type        = bool
  default     = false
}

variable "demo_scenario" {
  description = "Demo scenario to use (crashloop, oom, alb-5xx)"
  type        = string
  default     = "crashloop"

  validation {
    condition     = contains(["crashloop", "oom", "alb-5xx"], var.demo_scenario)
    error_message = "demo_scenario must be one of: crashloop, oom, alb-5xx"
  }
}

variable "log_level" {
  description = "Logging level for the agent"
  type        = string
  default     = "INFO"

  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "log_level must be one of: DEBUG, INFO, WARNING, ERROR"
  }
}

variable "extra_environment_variables" {
  description = "Additional environment variables for the runtime"
  type        = map(string)
  default     = {}
}

# Remediation Configuration
variable "enable_remediation" {
  description = "Enable remediation role and permissions"
  type        = bool
  default     = false
}

# Gateway Configuration
variable "enable_gateway" {
  description = "Enable AgentCore Gateway for MCP tool access"
  type        = bool
  default     = false
}

# Observability
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30

  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653
    ], var.log_retention_days)
    error_message = "log_retention_days must be a valid CloudWatch retention value"
  }
}

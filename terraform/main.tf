# AWS Incident Copilot infrastructure
#
# Deploys:
# - Investigation IAM role (Lambda + read APIs + Bedrock inference profiles)
# - Remediation IAM role assumed only by the investigation role
# - Lambda handler targeted by EventBridge CloudWatch Alarm state changes
# - EKS access entries / access policies when cluster names are provided
# - Optional AgentCore runtime module
#
# Estimated cost: ~$5-15/month depending on Bedrock usage.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.region
  name_prefix = "${var.project_name}-${var.environment}"

  bedrock_inference_profile_arn = "arn:aws:bedrock:${local.region}:${local.account_id}:inference-profile/${var.bedrock_model_id}"
  bedrock_foundation_model_arns = [
    "arn:aws:bedrock:us-east-1::foundation-model/${var.bedrock_foundation_model_id}",
    "arn:aws:bedrock:us-east-2::foundation-model/${var.bedrock_foundation_model_id}",
    "arn:aws:bedrock:us-west-2::foundation-model/${var.bedrock_foundation_model_id}",
    "arn:aws:bedrock:${local.region}::foundation-model/${var.bedrock_foundation_model_id}",
    "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-*",
  ]
}

#checkov:skip=CKV_AWS_158:KMS encryption is optional; enable for compliance environments
#checkov:skip=CKV_AWS_338:30-day retention is the default for cost; override via log_retention_days
resource "aws_cloudwatch_log_group" "incident_copilot" {
  name              = "/aws/incident-copilot/${var.environment}"
  retention_in_days = var.log_retention_days
}

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

module "agentcore" {
  source = "./modules/agentcore"
  count  = var.enable_agentcore ? 1 : 0

  project_name                = var.project_name
  environment                 = var.environment
  bedrock_model_id            = var.bedrock_model_id
  bedrock_foundation_model_id = var.bedrock_foundation_model_id
  create_ecr_repository       = true
  image_tag                   = var.agentcore_image_tag
  deploy_runtime              = true
  network_mode                = "PUBLIC"
  demo_mode                   = var.agentcore_demo_mode
  demo_scenario               = "crashloop"
  enable_gateway              = var.agentcore_enable_gateway
  enable_remediation          = var.agentcore_enable_remediation
  remediation_external_id     = var.remediation_external_id
  eks_cluster_names           = var.eks_cluster_names
  eks_remediation_namespaces  = var.eks_remediation_namespaces
  log_retention_days          = var.log_retention_days
}

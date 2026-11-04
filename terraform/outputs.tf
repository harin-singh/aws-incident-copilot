output "copilot_role_arn" {
  description = "IAM role ARN for the incident copilot Lambda"
  value       = aws_iam_role.incident_copilot.arn
}

output "remediation_role_arn" {
  description = "IAM role ARN for remediation actions"
  value       = aws_iam_role.remediation.arn
}

output "lambda_function_name" {
  description = "Lambda function that EventBridge invokes on alarm state changes"
  value       = aws_lambda_function.copilot.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.copilot.arn
}

output "eventbridge_rule_name" {
  description = "EventBridge rule that forwards CloudWatch alarms to the Lambda"
  value       = aws_cloudwatch_event_rule.alarm_state_change.name
}

output "log_group_name" {
  description = "CloudWatch log group for incident copilot logs"
  value       = aws_cloudwatch_log_group.incident_copilot.name
}

output "region" {
  description = "AWS region where resources are deployed"
  value       = local.region
}

output "bedrock_model_id" {
  description = "Configured Bedrock inference profile ID"
  value       = var.bedrock_model_id
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost (USD)"
  value       = "~$5-15 depending on Bedrock usage"
}

output "agentcore_ecr_repository_url" {
  description = "ECR repository URL for AgentCore container image"
  value       = var.enable_agentcore ? module.agentcore[0].ecr_repository_url : null
}

output "agentcore_runtime_id" {
  description = "AgentCore Runtime ID"
  value       = var.enable_agentcore ? module.agentcore[0].agent_runtime_id : null
}

output "agentcore_runtime_arn" {
  description = "AgentCore Runtime ARN"
  value       = var.enable_agentcore ? module.agentcore[0].agent_runtime_arn : null
}

output "agentcore_runtime_role_arn" {
  description = "AgentCore Runtime execution role ARN"
  value       = var.enable_agentcore ? module.agentcore[0].runtime_execution_role_arn : null
}

output "agentcore_gateway_endpoint" {
  description = "AgentCore Gateway ID (if enabled)"
  value       = var.enable_agentcore && var.agentcore_enable_gateway ? module.agentcore[0].gateway_endpoint : null
}

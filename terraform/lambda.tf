data "archive_file" "copilot_handler" {
  type        = "zip"
  source_file = "${path.module}/lambda/handler.py"
  output_path = "${path.module}/.build/handler.zip"
}

resource "aws_sqs_queue" "copilot_dlq" {
  name                      = "${local.name_prefix}-handler-dlq"
  sqs_managed_sse_enabled   = true
  message_retention_seconds = 1209600
}

#checkov:skip=CKV_AWS_117:Lambda stays out of VPC to match the public AgentCore default
#checkov:skip=CKV_AWS_173:Environment variables do not contain secrets; KMS is optional
#checkov:skip=CKV_AWS_116:DLQ is attached via dead_letter_config
resource "aws_lambda_function" "copilot" {
  function_name                  = "${local.name_prefix}-handler"
  role                           = aws_iam_role.incident_copilot.arn
  filename                       = data.archive_file.copilot_handler.output_path
  source_code_hash               = data.archive_file.copilot_handler.output_base64sha256
  handler                        = "handler.lambda_handler"
  runtime                        = "python3.11"
  timeout                        = 120
  memory_size                    = 512
  reserved_concurrent_executions = 5

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.copilot_dlq.arn
  }

  environment {
    variables = {
      DEMO_MODE             = "false"
      AWS_REGION_OVERRIDE   = local.region
      BEDROCK_MODEL_ID      = var.bedrock_model_id
      AGENTCORE_RUNTIME_ARN = var.enable_agentcore ? module.agentcore[0].agent_runtime_arn : ""
      REMEDIATION_ROLE_ARN  = aws_iam_role.remediation.arn
    }
  }

  depends_on = [
    aws_iam_role_policy.cloudwatch_logs,
    aws_cloudwatch_log_group.incident_copilot,
  ]
}

resource "aws_iam_role_policy" "lambda_dlq" {
  name = "lambda-dlq"
  role = aws_iam_role.incident_copilot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendToDlq"
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.copilot_dlq.arn
      },
      {
        Sid    = "XRay"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_cloudwatch_event_target" "alarm_to_lambda" {
  rule = aws_cloudwatch_event_rule.alarm_state_change.name
  arn  = aws_lambda_function.copilot.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.copilot.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.alarm_state_change.arn
}

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
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.copilot.function_name
  }

  alarm_actions = var.alert_sns_topic_arn != "" ? [var.alert_sns_topic_arn] : []
}

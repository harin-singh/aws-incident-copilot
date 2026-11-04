resource "aws_iam_role" "incident_copilot" {
  name = "${local.name_prefix}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaAssume"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

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
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:*"
      },
      {
        Sid    = "LambdaWriteOwnLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.incident_copilot.arn}:*"
      }
    ]
  })
}

#checkov:skip=CKV_AWS_355:Read-only CloudWatch metrics/alarms have no resource-level IAM
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

#checkov:skip=CKV_AWS_355:EKS Describe/List cannot be scoped tighter for investigation
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
          "eks:ListNodegroups",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      }
    ]
  })
}

#checkov:skip=CKV_AWS_355:ECS Describe/List cannot be scoped tighter for investigation
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
          "ecs:DescribeServices",
          "ecs:DescribeTasks",
          "ecs:DescribeTaskDefinition",
          "ecs:ListClusters",
          "ecs:ListServices",
          "ecs:ListTasks"
        ]
        Resource = "*"
      },
      {
        Sid      = "ECSDescribeClusters"
        Effect   = "Allow"
        Action   = ["ecs:DescribeClusters"]
        Resource = local.ecs_cluster_arns
      }
    ]
  })
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name = "bedrock-invoke"
  role = aws_iam_role.incident_copilot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InferenceProfileAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:GetInferenceProfile",
          "bedrock:ListInferenceProfiles"
        ]
        Resource = [
          local.bedrock_inference_profile_arn,
          "arn:aws:bedrock:${local.region}:${local.account_id}:inference-profile/*",
          "arn:aws:bedrock:${local.region}:${local.account_id}:application-inference-profile/*"
        ]
      },
      {
        Sid    = "FoundationModelViaProfile"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = local.bedrock_foundation_model_arns
        Condition = {
          StringLike = {
            "bedrock:InferenceProfileArn" = [
              local.bedrock_inference_profile_arn,
              "arn:aws:bedrock:${local.region}:${local.account_id}:inference-profile/*"
            ]
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "assume_remediation" {
  name = "assume-remediation"
  role = aws_iam_role.incident_copilot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AssumeRemediationRole"
        Effect   = "Allow"
        Action   = "sts:AssumeRole"
        Resource = aws_iam_role.remediation.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "invoke_agentcore" {
  count = var.enable_agentcore ? 1 : 0
  name  = "invoke-agentcore"
  role  = aws_iam_role.incident_copilot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeAgentCoreRuntime"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:InvokeAgentRuntime"
        ]
        Resource = module.agentcore[0].agent_runtime_arn
      }
    ]
  })
}

resource "aws_iam_role" "remediation" {
  name = "${local.name_prefix}-remediation-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvestigationRoleOnly"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.incident_copilot.arn
        }
        Action = "sts:AssumeRole"
        Condition = merge(
          {
            ArnEquals = {
              "aws:PrincipalArn" = aws_iam_role.incident_copilot.arn
            }
            StringEquals = {
              "aws:SourceAccount" = local.account_id
            }
          },
          var.remediation_external_id != null ? {
            StringEquals = {
              "aws:SourceAccount" = local.account_id
              "sts:ExternalId"    = var.remediation_external_id
            }
          } : {}
        )
      }
    ]
  })
}

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
          "ecs:UpdateService",
          "ecs:DescribeServices"
        ]
        Resource = [
          "arn:aws:ecs:${local.region}:${local.account_id}:service/*/*",
          "arn:aws:ecs:${local.region}:${local.account_id}:cluster/*"
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

#checkov:skip=CKV_AWS_355:DescribeCluster is required to mint an EKS API token
resource "aws_iam_role_policy" "eks_remediation" {
  name = "eks-remediation"
  role = aws_iam_role.remediation.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EKSDescribeForKubeAuth"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:AccessKubernetesApi"
        ]
        Resource = length(var.eks_cluster_names) > 0 ? [
          for name in var.eks_cluster_names :
          "arn:aws:eks:${local.region}:${local.account_id}:cluster/${name}"
        ] : ["arn:aws:eks:${local.region}:${local.account_id}:cluster/*"]
      }
    ]
  })
}

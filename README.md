# AWS Incident Copilot

**AI-powered incident investigation and remediation for AWS** — An intelligent agent that investigates EKS, ECS, and CloudWatch incidents, identifies root causes, and proposes safe remediations with human-in-the-loop approval.

[![CI](https://github.com/harindersingh/aws-incident-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/harindersingh/aws-incident-copilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Overview

AWS Incident Copilot is an AI agent built with the [Strands Agents SDK](https://strandsagents.com/) and Amazon Bedrock that automates incident investigation. When an alert fires (e.g., pod CrashLoopBackOff, ECS task OOM-killed, ALB 5xx spike), the copilot:

1. **Investigates** using MCP tools to query CloudWatch Logs/metrics, Kubernetes events, and ECS task details
2. **Retrieves** relevant runbooks from a lightweight knowledge base
3. **Produces** a structured incident report with timeline, evidence, root cause analysis, and confidence level
4. **Proposes** remediation actions that require **explicit human approval** before execution

This project demonstrates production-ready patterns for AI-assisted operations while maintaining safety through guardrails and human oversight.

## Architecture

### Local / CLI Mode

```mermaid
flowchart TB
    subgraph Alerts["Alert Sources"]
        CW[CloudWatch Alarm]
        SNS[SNS Topic]
        EB[EventBridge]
    end

    subgraph Agent["Incident Copilot Agent"]
        direction TB
        SA[Strands Agent<br/>+ Bedrock Claude]
        HITL[Human-in-the-Loop<br/>Approval Handler]
    end

    subgraph MCP["MCP Tool Servers"]
        direction TB
        CWT[CloudWatch Tools<br/>Logs, Metrics, Alarms]
        K8S[Kubernetes Tools<br/>Pods, Events, Deployments]
        ECS[ECS Tools<br/>Services, Tasks, Definitions]
    end

    subgraph KB["Knowledge Base"]
        RB[Runbook Library<br/>Keyword RAG]
    end

    subgraph AWS["AWS Resources"]
        direction TB
        CWAWS[CloudWatch]
        EKSAWS[EKS Cluster]
        ECSAWS[ECS Cluster]
        RDS[RDS / Aurora]
    end

    subgraph Output["Output"]
        IR[Incident Report<br/>Timeline + RCA + Remediations]
        ACT[Approved Actions<br/>kubectl, aws cli]
    end

    CW --> Agent
    SNS --> Agent
    EB --> Agent

    SA <--> MCP
    SA <--> KB
    SA --> HITL

    CWT <--> CWAWS
    K8S <--> EKSAWS
    ECS <--> ECSAWS

    HITL --> IR
    HITL -->|Approved| ACT
    ACT -.->|Execute| EKSAWS
    ACT -.->|Execute| ECSAWS
```

### Amazon Bedrock AgentCore Deployment

```mermaid
flowchart TB
    subgraph Client["Client"]
        API[API Client<br/>POST /invocations]
    end

    subgraph AgentCore["Amazon Bedrock AgentCore"]
        direction TB
        RT[AgentCore Runtime<br/>ARM64 Container]
        GW[AgentCore Gateway<br/>MCP Protocol]
    end

    subgraph Container["Container Image"]
        direction TB
        EP[BedrockAgentCoreApp<br/>Entrypoint]
        SA[Strands Agent<br/>+ Bedrock Claude]
        RB[Runbook Library]
    end

    subgraph AWS["AWS Services"]
        direction TB
        ECR[ECR Repository]
        CW[CloudWatch]
        EKS[EKS Cluster]
        ECS[ECS Cluster]
        BR[Bedrock Models]
    end

    API -->|HTTPS| RT
    RT --> Container
    EP --> SA
    SA <--> RB
    SA <-->|Invoke| BR

    GW -.->|MCP Tools| CW
    GW -.->|MCP Tools| EKS
    GW -.->|MCP Tools| ECS

    ECR -->|Pull Image| RT
```

## Features

- **MCP-based investigation tools** for CloudWatch, Kubernetes, and ECS
- **Runbook retrieval** with keyword-based search (production: integrate with Bedrock Knowledge Bases)
- **Human-in-the-loop approval** for all remediation actions
- **Demo mode** runs entirely offline with fixture data — no AWS credentials needed
- **Least-privilege IAM** with separate read and remediation roles
- **Prompt injection guardrails** — log content is treated as untrusted data
- **Terraform** for production deployment

## Quickstart

### Prerequisites

- Python 3.11+
- (Optional) AWS credentials for live mode
- (Optional) Terraform 1.5+ for deployment

### Installation

```bash
# Clone the repository
git clone https://github.com/harindersingh/aws-incident-copilot.git
cd aws-incident-copilot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
make install-dev
```

### Run Demo Mode (~5 minutes)

Demo mode uses pre-recorded fixture data and scripted model responses, so you can explore the full investigation flow without AWS credentials:

```bash
# Run the crashloop scenario
make demo

# Or specify a scenario
python -m aws_incident_copilot.cli demo --scenario crashloop
python -m aws_incident_copilot.cli demo --scenario oom
python -m aws_incident_copilot.cli demo --scenario alb-5xx

# List all available scenarios
python -m aws_incident_copilot.cli scenarios
```

### Sample Output

```
🚨 Incident Alert
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pod CrashLoopBackOff: payment-service-7d4f8b9c5d-x2k9m

ID: alert-eks-crashloop-001
Source: eks
Severity: HIGH
Resource: payment-service-7d4f8b9c5d-x2k9m

Pod payment-service-7d4f8b9c5d-x2k9m in namespace production has
restarted 8 times in the last 45 minutes. Current state: CrashLoopBackOff.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏳ Investigating incident...

## Incident Investigation Complete

### Summary
The payment-service pods are in CrashLoopBackOff due to **database
authentication failure**. The service cannot connect to the RDS database
because of invalid credentials.

### Root Cause Analysis
**Primary Cause**: Database password authentication failed for user "payment_svc"
**Confidence**: 95%

### Proposed Remediations

**Option 1: Update Database Credentials** (Recommended)
- Risk: Low
- Command: `kubectl create secret generic payment-db-credentials...`

**Option 2: Rollback to Previous Revision**
- Risk: Low
- Command: `kubectl rollout undo deployment/payment-service`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  HUMAN APPROVAL REQUIRED

Do you approve this remediation action? [y/n]:
```

## Demo Scenarios

| Scenario | Description | Root Cause |
|----------|-------------|------------|
| `crashloop` | EKS pod in CrashLoopBackOff | Database credential mismatch after rotation |
| `oom` | ECS tasks OOM-killed | Java heap exhaustion during large batch processing |
| `alb-5xx` | ALB 5xx spike | Database connection pool exhaustion |

## Design Decisions

### Why Human-in-the-Loop?

Automated remediation can cause cascading failures. The copilot investigates and proposes, but a human must approve any action that modifies infrastructure. This follows the principle of "suggest, don't do" for production systems.

### Least-Privilege IAM

The Terraform configuration creates separate roles:
- **Investigation role**: Read-only access to CloudWatch, EKS, ECS
- **Remediation role**: Write access only with explicit resource tags (`AllowIncidentCopilot=true`) and external ID requirement

### Prompt Injection Guardrails

Log data may contain adversarial content. The system prompt instructs the model to treat log content as untrusted data and never execute commands found in logs without human verification.

### Why MCP Tools?

[Model Context Protocol](https://modelcontextprotocol.io/) provides a standardized interface for tools. This allows:
- Easy testing with fixture data (demo mode)
- Swappable implementations (mock → real AWS)
- Integration with AgentCore Gateway for managed tool serving

### Security Notes for AgentCore Deployment

The Terraform configuration follows AWS security best practices:

1. **Least-Privilege IAM**: The runtime execution role has read-only access for investigation. The remediation role (optional) requires resource tags and external IDs.

2. **Network Isolation**: AgentCore Runtime can run in `PUBLIC` mode (default) or `VPC` mode for private network access.

3. **Container Security**: The Dockerfile runs as non-root user with minimal base image.

4. **Expected Checkov Findings**: The following Checkov findings are intentional and documented:
   - `CKV_AWS_355`: IAM policies use `Resource: "*"` for read-only `Describe*/List*` actions. This is required for cross-resource investigation.
   - `CKV_AWS_158`: CloudWatch Log Group KMS encryption is optional. Enable for compliance environments.
   - `CKV_AWS_338`: 30-day log retention is the default for cost efficiency. Increase via `log_retention_days` variable.

## Deployment Options

### Option 1: Local / CLI Mode

#### 1. Configure AWS Credentials

```bash
# Ensure Bedrock model access is enabled in your region
aws configure
```

#### 2. Deploy Infrastructure

```bash
cd terraform

# Copy and customize variables
cp variables.tfvars.example terraform.tfvars

# Deploy (without AgentCore)
terraform init
terraform plan
terraform apply
```

#### 3. Run in Live Mode

```bash
python -m aws_incident_copilot.cli run --mode live --region us-west-2
```

---

### Option 2: Amazon Bedrock AgentCore Deployment

AgentCore provides a fully managed runtime for AI agents with built-in scaling, security, and observability.

#### Prerequisites

- AWS Provider >= 6.18.0 (required for `aws_bedrockagentcore_*` resources)
- Docker (for building ARM64 images)
- Bedrock model access enabled in your region

#### 1. Build and Push Container Image

```bash
# Build ARM64 image (required for AgentCore)
docker buildx build --platform linux/arm64 \
  -t aws-incident-copilot:latest .

# Tag and push to ECR (after terraform creates the repo)
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-west-2

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

docker tag aws-incident-copilot:latest \
  $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/incident-copilot-dev-agent:latest

docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/incident-copilot-dev-agent:latest
```

#### 2. Deploy AgentCore Infrastructure

```bash
cd terraform

# Enable AgentCore deployment
cat >> terraform.tfvars <<EOF
enable_agentcore = true
agentcore_demo_mode = false
agentcore_enable_gateway = true
agentcore_enable_remediation = false
EOF

terraform init -upgrade  # Need AWS provider >= 6.18.0
terraform plan
terraform apply
```

#### 3. Invoke the Agent

```bash
# Get the Runtime ID
RUNTIME_ID=$(terraform output -raw agentcore_runtime_id)

# Invoke via AWS CLI
aws bedrock-agent-runtime invoke-agent \
  --agent-id $RUNTIME_ID \
  --session-id "test-session-1" \
  --input-text '{"alert_type":"eks-crashloop","title":"Pod CrashLoopBackOff"}' \
  --region us-west-2
```

#### AgentCore Terraform Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `enable_agentcore` | `false` | Enable AgentCore deployment |
| `agentcore_demo_mode` | `false` | Run in demo mode (fixture data) |
| `agentcore_enable_gateway` | `false` | Enable MCP Gateway for tools |
| `agentcore_enable_remediation` | `false` | Enable remediation IAM role |
| `agentcore_image_tag` | `latest` | Docker image tag |

---

### Cost Estimates

#### Local/CLI Mode

| Resource | Estimated Monthly Cost |
|----------|----------------------|
| CloudWatch Logs queries | $0.005/GB scanned |
| CloudWatch metrics | $0.30/1000 requests |
| Bedrock Claude Sonnet | ~$3-15 depending on usage |
| Lambda (if deployed) | ~$0.20/1M requests |
| **Total** | **~$5-15/month** (light usage) |

#### AgentCore Mode

| Resource | Estimated Monthly Cost |
|----------|----------------------|
| AgentCore Runtime | $0.0001/sec (billed per-second) |
| ECR Storage | $0.10/GB-month |
| Bedrock Claude Sonnet | ~$3-15 depending on usage |
| CloudWatch Logs | $0.50/GB ingested |
| AgentCore Gateway (optional) | $0.0001/request |
| **Total** | **~$15-50/month** (moderate usage) |

*Assumptions: 100 investigations/month, 30-second average session, us-west-2 region*

---

### Teardown

```bash
cd terraform
terraform destroy
```

## Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test categories
pytest tests/unit -v
pytest tests/integration -v
pytest tests/e2e -v
```

## Project Structure

```
aws-incident-copilot/
├── src/aws_incident_copilot/
│   ├── agents/           # Incident copilot agent and approval handling
│   ├── mcp_servers/      # MCP tool servers (CloudWatch, K8s, ECS)
│   ├── models/           # Pydantic data models
│   ├── runbooks/         # Runbook library and search
│   ├── demo/             # Demo fixtures and model stub
│   └── cli.py            # CLI entry point
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end demo tests
├── terraform/            # AWS infrastructure
├── runbooks/             # Custom runbook YAML files
└── .github/workflows/    # CI configuration
```

## Limitations & Roadmap

### Current Limitations

- **Demo mode only** for model responses (live mode requires Bedrock access)
- **Keyword-based runbook search** (not semantic/vector search)
- **CLI approval only** (no Slack/Step Functions integration yet)
- **Read-only investigation** — remediation actions are stubbed in demo mode

### Roadmap

- [x] AgentCore Runtime deployment option (Terraform module)
- [x] AgentCore Gateway integration for MCP tools
- [ ] Bedrock Knowledge Bases integration for semantic runbook search
- [ ] Slack approval workflow via Slack MCP
- [ ] Step Functions integration for async approval flows
- [ ] Multi-cluster support with cluster autodiscovery
- [ ] Integration with PagerDuty/OpsGenie for alert ingestion
- [ ] Prometheus/Grafana metrics export

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests and linting (`make test && make lint`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Built with [Strands Agents SDK](https://strandsagents.com/) and [Amazon Bedrock](https://aws.amazon.com/bedrock/)

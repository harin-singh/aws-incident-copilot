"""Demo model provider that returns scripted responses.

The stub drives a fixed tool-call sequence so the demo is deterministic.
The final RCA is emitted only after the conversation contains the expected
tool results. If tools were rejected or returned no evidence, the stub
refuses to print a canned root cause.
"""

import json
from collections.abc import AsyncGenerator, AsyncIterable
from threading import Event
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Message, SystemContentBlock
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

T = TypeVar("T", bound=BaseModel)

UNGROUNDED_MARKER = "UNGROUNDED"

# Evidence that must appear in tool results (not the alert text) before RCA.
REQUIRED_EVIDENCE: dict[str, list[str]] = {
    "crashloop": ["CrashLoopBackOff", "password authentication failed"],
    "oom": ["137", "OutOfMemory"],
    "alb-5xx": ["Too many connections", "HTTPCode_Target_5XX"],
}

TOOL_FAILURE_MARKERS = (
    "tool not found",
    "unrecognized tool specification",
    "tool_name=",
)


def extract_tool_result_text(messages: list[Any] | None) -> str:
    """Flatten tool-result payloads from a Strands message list."""
    if not messages:
        return ""
    chunks: list[str] = []
    for message in messages:
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", None)
        )
        if not content:
            continue
        if isinstance(content, str):
            chunks.append(content)
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            result = block.get("toolResult")
            if result is None:
                continue
            status = str(result.get("status", ""))
            if status:
                chunks.append(status)
            for item in result.get("content") or []:
                if isinstance(item, dict):
                    if "text" in item:
                        chunks.append(str(item["text"]))
                    if "json" in item:
                        chunks.append(json.dumps(item["json"], default=str))
                    if "data" in item:
                        chunks.append(json.dumps(item["data"], default=str))
                else:
                    chunks.append(str(item))
    return "\n".join(chunks)


def evaluate_grounding(scenario: str, tool_result_text: str) -> tuple[bool, list[str]]:
    """Return (grounded, errors) for a scenario given flattened tool output."""
    errors: list[str] = []
    lowered = tool_result_text.lower()
    if not tool_result_text.strip():
        errors.append("no tool results were returned to the model")
    for marker in TOOL_FAILURE_MARKERS:
        if marker in lowered:
            errors.append(f"tool invocation failed: {marker}")
            break
    for needle in REQUIRED_EVIDENCE.get(scenario, []):
        if needle.lower() not in lowered:
            errors.append(f"missing expected evidence: {needle}")
    return (len(errors) == 0, errors)


class DemoModelProvider(Model):
    """A scripted model provider for demo mode.

    Tool-call turns are scripted. The closing RCA is emitted only when
    the preceding tool results contain the scenario's expected evidence.
    """

    def __init__(self, scenario: str = "crashloop"):
        """Initialize with a scenario name."""
        self.scenario = scenario
        self.call_count = 0
        self.tool_results_seen: str = ""
        self.grounded: bool | None = None
        self.grounding_errors: list[str] = []
        self._responses = SCENARIO_RESPONSES.get(scenario, SCENARIO_RESPONSES["crashloop"])

    def update_config(self, **model_config: Any) -> None:
        """Update model configuration."""
        pass

    def get_config(self) -> Any:
        """Get model configuration."""
        return {"model_id": "demo-model", "scenario": self.scenario}

    async def stream(
        self,
        messages: list[Message],
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: Any = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        invocation_state: dict[str, Any] | None = None,
        cancel_signal: Event | None = None,
        agent_metadata: Any = None,
        structured_output_model: type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        """Stream responses from the model."""
        self.tool_results_seen = extract_tool_result_text(messages)
        response = self._get_next_response()

        if response.get("tool_use"):
            for i, tool in enumerate(response["tool_use"]):
                yield {
                    "contentBlockStart": {
                        "contentBlockIndex": i,
                        "start": {
                            "toolUse": {
                                "toolUseId": f"demo-tool-{self.call_count}-{i}",
                                "name": tool["name"],
                            }
                        },
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "contentBlockIndex": i,
                        "delta": {"toolUse": {"input": json.dumps(tool["input"])}},
                    }
                }
                yield {"contentBlockStop": {"contentBlockIndex": i}}

        if response.get("text"):
            idx = len(response.get("tool_use", []))
            yield {
                "contentBlockStart": {
                    "contentBlockIndex": idx,
                    "start": {"text": ""},  # type: ignore[typeddict-unknown-key]
                }
            }
            yield {
                "contentBlockDelta": {
                    "contentBlockIndex": idx,
                    "delta": {"text": response["text"]},
                }
            }
            yield {"contentBlockStop": {"contentBlockIndex": idx}}

        yield {
            "messageStop": {
                "stopReason": response.get("stop_reason", "end_turn"),
            }
        }

    async def structured_output(
        self,
        output_model: type[T],
        prompt: list[Message],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        """Generate structured output."""
        yield {"type": "error", "message": "Structured output not supported in demo mode"}

    def _ungrounded_response(self, errors: list[str]) -> dict[str, Any]:
        """Build a refusal when tool output does not support an RCA."""
        missing = "\n".join(f"- {err}" for err in errors)
        return {
            "text": (
                f"## Investigation Failed ({UNGROUNDED_MARKER})\n\n"
                "The scripted demo model will not emit a root-cause analysis "
                "because the investigation tools did not return the expected evidence.\n\n"
                f"**Confidence**: 0%\n\n"
                f"**Problems**:\n{missing}\n\n"
                "Fix tool registration and re-run the demo. A canned RCA is not a substitute "
                "for actual tool output."
            ),
            "stop_reason": "end_turn",
        }

    def _is_final_rca(self, response: dict[str, Any]) -> bool:
        text = response.get("text") or ""
        return (
            response.get("stop_reason") == "end_turn"
            and "Incident Investigation Complete" in text
            and not response.get("tool_use")
        )

    def _get_next_response(self) -> dict[str, Any]:
        """Get the next scripted response, gating the RCA on tool evidence."""
        if self.call_count < len(self._responses):
            response = self._responses[self.call_count]
            self.call_count += 1
            if self._is_final_rca(response):
                self.grounded, self.grounding_errors = evaluate_grounding(
                    self.scenario, self.tool_results_seen
                )
                if not self.grounded:
                    return self._ungrounded_response(self.grounding_errors)
            return response

        if self.grounded is None:
            self.grounded, self.grounding_errors = evaluate_grounding(
                self.scenario, self.tool_results_seen
            )
            if not self.grounded:
                return self._ungrounded_response(self.grounding_errors)

        return {
            "text": "Investigation complete. Please review the incident report above.",
            "stop_reason": "end_turn",
        }


# Scripted responses for each scenario
SCENARIO_RESPONSES: dict[str, list[dict[str, Any]]] = {
    "crashloop": [
        {
            "text": "I'll investigate this CrashLoopBackOff alert. Let me start by examining the pod status and recent events.",
            "tool_use": [
                {
                    "name": "describe_pod",
                    "input": {
                        "name": "payment-service-7d4f8b9c5d-x2k9m",
                        "namespace": "production",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "The pod has restarted 8 times and is in CrashLoopBackOff. Let me check the Kubernetes events for more context.",
            "tool_use": [
                {
                    "name": "get_events",
                    "input": {
                        "namespace": "production",
                        "resource_name": "payment-service-7d4f8b9c5d-x2k9m",
                        "resource_kind": "Pod",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "I see repeated BackOff and Unhealthy events. Let me examine the container logs to identify the root cause.",
            "tool_use": [
                {
                    "name": "get_pod_logs",
                    "input": {
                        "name": "payment-service-7d4f8b9c5d-x2k9m",
                        "namespace": "production",
                        "previous": True,
                        "tail_lines": 50,
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "The logs show a clear pattern: database authentication is failing. Let me check the deployment status and recent changes.",
            "tool_use": [
                {
                    "name": "describe_deployment",
                    "input": {
                        "name": "payment-service",
                        "namespace": "production",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Let me also check CloudWatch for related alarms and logs.",
            "tool_use": [
                {
                    "name": "describe_alarms",
                    "input": {"state": "ALARM"},
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": """## Incident Investigation Complete

### Summary
The payment-service pods are in CrashLoopBackOff due to **database authentication failure**. The service cannot connect to the RDS database because of invalid credentials.

### Timeline
- **45 minutes ago**: New deployment (revision 15) rolled out
- **42 minutes ago**: First readiness probe failures observed
- **40 minutes ago**: Pods began entering CrashLoopBackOff
- **Now**: 8 restarts, 2/3 replicas unavailable

### Root Cause Analysis
**Primary Cause**: Database password authentication failed for user "payment_svc"

**Confidence**: 95%

**Evidence**:
1. Container logs show: `FATAL: password authentication failed for user "payment_svc"`
2. Service retries 3 times before fatal shutdown
3. Issue started with deployment revision 15
4. Previous revision (14) was stable

**Most Likely Explanation**: The database credentials were changed or the secret was not updated correctly during the recent deployment. This could be:
- A rotated database password that wasn't synced to Kubernetes secrets
- A misconfigured environment variable or secret reference
- An accidental change to the database user configuration

### Proposed Remediations

**Option 1: Verify and Update Database Credentials** (Recommended)
- Risk: Low
- Impact: Service will recover once correct credentials are deployed

```bash
# Check current secret value
kubectl get secret payment-db-credentials -n production -o jsonpath='{.data.password}' | base64 -d

# Verify against RDS credentials and update if needed
kubectl create secret generic payment-db-credentials \\
  --from-literal=password='<correct-password>' \\
  -n production --dry-run=client -o yaml | kubectl apply -f -

# Restart the deployment to pick up new secret
kubectl rollout restart deployment/payment-service -n production
```

**Option 2: Rollback to Previous Revision**
- Risk: Low
- Impact: Reverts any changes from revision 15, may lose desired changes

```bash
kubectl rollout undo deployment/payment-service -n production
```

### Requires Human Approval
Both remediation options require human approval before execution. Please confirm which action to take.""",
            "stop_reason": "end_turn",
        },
    ],
    "oom": [
        {
            "text": "I'll investigate this ECS task failure. Let me start by examining the service status and recent events.",
            "tool_use": [
                {
                    "name": "describe_service",
                    "input": {
                        "cluster": "production-cluster",
                        "service": "order-processor",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "The service shows task failures. Let me examine the stopped tasks to understand the failure pattern.",
            "tool_use": [
                {
                    "name": "describe_stopped_tasks",
                    "input": {
                        "cluster": "production-cluster",
                        "service": "order-processor",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Multiple tasks stopped with exit code 137 (OOM killed). Let me check the memory metrics and task definition.",
            "tool_use": [
                {
                    "name": "get_metrics",
                    "input": {
                        "namespace": "AWS/ECS",
                        "metric_name": "MemoryUtilization",
                        "dimensions": {
                            "ServiceName": "order-processor",
                            "ClusterName": "production-cluster",
                        },
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Memory utilization spiked to 99%+. Let me check the task definition for memory limits.",
            "tool_use": [
                {
                    "name": "describe_task_definition",
                    "input": {"task_definition": "order-processor:42"},
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Let me check the application logs for more context on what's consuming memory.",
            "tool_use": [
                {
                    "name": "query_logs",
                    "input": {
                        "log_group": "/ecs/order-processor",
                        "query": "fields @timestamp, @message | filter @message like /memory|heap|OutOfMemory/ | sort @timestamp desc | limit 20",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": """## Incident Investigation Complete

### Summary
The order-processor ECS tasks are being **OOM killed** due to insufficient memory allocation while processing large order batches.

### Timeline
- **30 minutes ago**: Memory utilization at normal levels (65%)
- **20 minutes ago**: Memory usage started climbing rapidly
- **10-15 minutes ago**: Multiple tasks OOM killed (exit code 137)
- **Now**: 3/5 tasks running, 2 pending restart

### Root Cause Analysis
**Primary Cause**: Java heap space exhaustion during large batch processing

**Confidence**: 92%

**Evidence**:
1. Exit code 137 = SIGKILL (OOM killed by kernel)
2. Memory utilization climbed from 65% to 99%+ before kills
3. Logs show: "java.lang.OutOfMemoryError: Java heap space"
4. Logs show: "Processing large batch: 50000 orders"
5. Task definition allocates only 1024MB for a Java service

**Analysis**: The service is configured with 1GB memory, but Java heap isn't properly constrained. When processing large batches, the JVM attempts to allocate more heap than available, triggering OOM kills. This is likely triggered by an unusually large order batch.

### Proposed Remediations

**Option 1: Increase Task Memory** (Immediate fix)
- Risk: Low (cost increase)
- Impact: Prevents OOM for larger workloads

Update task definition to allocate more memory:
```json
{
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [{
    "memory": 2048,
    "environment": [
      {"name": "JAVA_OPTS", "value": "-Xmx1536m -Xms512m"}
    ]
  }]
}
```

**Option 2: Add Batch Size Limits** (Architectural fix)
- Risk: Medium (requires code change)
- Impact: Prevents unbounded memory growth

Add environment variable to limit batch processing:
```
MAX_BATCH_SIZE=10000
```

**Option 3: Immediate Scale Up**
- Risk: Low
- Impact: Distribute load across more tasks

```bash
aws ecs update-service --cluster production-cluster \\
  --service order-processor --desired-count 8
```

### Requires Human Approval
All remediation options require human approval. Option 1 (increase memory) is recommended for immediate relief.""",
            "stop_reason": "end_turn",
        },
    ],
    "alb-5xx": [
        {
            "text": "I'll investigate this 5xx spike. Let me start by examining the ALB metrics and error patterns.",
            "tool_use": [
                {
                    "name": "get_metrics",
                    "input": {
                        "namespace": "AWS/ApplicationELB",
                        "metric_name": "HTTPCode_Target_5XX_Count",
                        "dimensions": {"LoadBalancer": "app/api-alb/1234567890"},
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Significant 5xx spike detected. Let me check target response times to understand if this is latency-related.",
            "tool_use": [
                {
                    "name": "get_metrics",
                    "input": {
                        "namespace": "AWS/ApplicationELB",
                        "metric_name": "TargetResponseTime",
                        "dimensions": {"LoadBalancer": "app/api-alb/1234567890"},
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Response times spiked significantly. Let me check the application logs for error details.",
            "tool_use": [
                {
                    "name": "query_logs",
                    "input": {
                        "log_group": "/ecs/api-service",
                        "query": "fields @timestamp, @message | filter @message like /ERROR|connection|timeout/ | sort @timestamp desc | limit 30",
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Database connection issues detected. Let me check RDS connection metrics.",
            "tool_use": [
                {
                    "name": "get_metrics",
                    "input": {
                        "namespace": "AWS/RDS",
                        "metric_name": "DatabaseConnections",
                        "dimensions": {"DBInstanceIdentifier": "api-db-primary"},
                    },
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": "Let me check all related CloudWatch alarms.",
            "tool_use": [
                {
                    "name": "describe_alarms",
                    "input": {"state": "ALARM"},
                }
            ],
            "stop_reason": "tool_use",
        },
        {
            "text": """## Incident Investigation Complete

### Summary
The API service is returning 5xx errors due to **database connection pool exhaustion**. The RDS instance hit its maximum connection limit (200), causing new requests to timeout waiting for connections.

### Timeline
- **30 minutes ago**: Normal operation, ~45 database connections
- **25 minutes ago**: Connection count started climbing
- **20 minutes ago**: 5xx errors began appearing (45 errors/5min)
- **15 minutes ago**: Connections hit max limit (200), errors peaked (312/5min → 587/5min)
- **Now**: Errors decreasing as connections are recycled, but still elevated

### Root Cause Analysis
**Primary Cause**: Database connection pool exhaustion

**Confidence**: 88%

**Evidence**:
1. RDS connections hit max_connections limit (200)
2. Logs show: "Too many connections" and "connection pool exhausted"
3. Application timeout errors waiting for DB connections
4. Response time correlated with connection saturation
5. Three alarms triggered: 5xx high, response time high, RDS connections high

**Analysis**: Connection leak or connection pool misconfiguration. Possible causes:
- Unclosed connections from a recent code deployment
- Sudden traffic spike exhausting pool
- Long-running queries holding connections
- Connection pool size misconfigured for current task count

### Proposed Remediations

**Option 1: Increase RDS max_connections** (Quick mitigation)
- Risk: Low (may need instance upgrade)
- Impact: Allows more concurrent connections

```sql
-- Check current setting
SHOW VARIABLES LIKE 'max_connections';

-- Increase if instance has capacity
-- Note: May require parameter group change and reboot
```

**Option 2: Restart ECS Tasks** (Reset connection pools)
- Risk: Medium (brief service disruption)
- Impact: Clears potentially leaked connections

```bash
aws ecs update-service --cluster production-cluster \\
  --service api-service --force-new-deployment
```

**Option 3: Scale Down and Back Up** (Gradual reset)
- Risk: Low
- Impact: Gracefully recycles connections

```bash
# Scale down to 5 tasks
aws ecs update-service --cluster production-cluster \\
  --service api-service --desired-count 5

# Wait 2 minutes, then scale back up
aws ecs update-service --cluster production-cluster \\
  --service api-service --desired-count 10
```

### Requires Human Approval
All remediation options require human approval. Option 3 is recommended as lowest risk.""",
            "stop_reason": "end_turn",
        },
    ],
}

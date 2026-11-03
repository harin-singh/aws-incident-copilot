"""Demo scenarios for incident investigation.

Each scenario represents a realistic incident that can be investigated
using the demo mode.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aws_incident_copilot.models.incident import Alert, AlertSeverity, AlertSource


@dataclass
class DemoScenario:
    """A demo incident scenario."""

    id: str
    name: str
    description: str
    alert: Alert
    expected_root_cause: str
    expected_remediations: list[str]


SCENARIOS: dict[str, DemoScenario] = {
    "crashloop": DemoScenario(
        id="crashloop",
        name="EKS CrashLoopBackOff",
        description=(
            "A payment service pod is stuck in CrashLoopBackOff due to "
            "database authentication failure after a recent deployment."
        ),
        alert=Alert(
            id="alert-eks-crashloop-001",
            source=AlertSource.EKS,
            severity=AlertSeverity.HIGH,
            title="Pod CrashLoopBackOff: payment-service-7d4f8b9c5d-x2k9m",
            description=(
                "Pod payment-service-7d4f8b9c5d-x2k9m in namespace production "
                "has restarted 8 times in the last 45 minutes. Current state: "
                "CrashLoopBackOff. Readiness probe failing."
            ),
            timestamp=datetime.now(UTC),
            resource_id="payment-service-7d4f8b9c5d-x2k9m",
            region="us-west-2",
            namespace="production",
            cluster="production-eks",
            metadata={
                "restart_count": 8,
                "last_state": "CrashLoopBackOff",
                "container": "payment-service",
            },
        ),
        expected_root_cause="Database authentication failure - password mismatch",
        expected_remediations=[
            "Update database credentials secret",
            "Rollback to previous deployment",
        ],
    ),
    "oom": DemoScenario(
        id="oom",
        name="ECS OOM Kill",
        description=(
            "An order processing service is being OOM-killed while processing "
            "large batches, causing service instability."
        ),
        alert=Alert(
            id="alert-ecs-oom-001",
            source=AlertSource.ECS,
            severity=AlertSeverity.CRITICAL,
            title="ECS Task OOM: order-processor tasks killed",
            description=(
                "Multiple order-processor tasks in production-cluster have been "
                "terminated with exit code 137 (OOM killed). 3/5 tasks running, "
                "service degraded."
            ),
            timestamp=datetime.now(UTC),
            resource_id="arn:aws:ecs:us-west-2:123456789:service/production-cluster/order-processor",
            region="us-west-2",
            service="order-processor",
            metadata={
                "cluster": "production-cluster",
                "exit_code": 137,
                "stopped_tasks": 3,
                "running_tasks": 3,
            },
        ),
        expected_root_cause="Java heap exhaustion during large batch processing",
        expected_remediations=[
            "Increase task memory allocation",
            "Add batch size limits",
            "Scale up task count",
        ],
    ),
    "alb-5xx": DemoScenario(
        id="alb-5xx",
        name="ALB 5xx Spike",
        description=(
            "API service behind ALB is returning 5xx errors due to database "
            "connection pool exhaustion."
        ),
        alert=Alert(
            id="alert-alb-5xx-001",
            source=AlertSource.ALB,
            severity=AlertSeverity.CRITICAL,
            title="ALB 5xx Spike: api-alb target errors",
            description=(
                "Application Load Balancer api-alb is reporting elevated 5xx "
                "errors from target group api-tg. Error rate: 587 errors in last "
                "5 minutes. Response times elevated to 8.9s average."
            ),
            timestamp=datetime.now(UTC),
            resource_id="arn:aws:elasticloadbalancing:us-west-2:123456789:loadbalancer/app/api-alb/1234567890",
            region="us-west-2",
            metadata={
                "target_group": "api-tg",
                "error_count_5min": 587,
                "avg_response_time": 8.9,
                "healthy_hosts": 10,
            },
        ),
        expected_root_cause="Database connection pool exhaustion",
        expected_remediations=[
            "Increase RDS max_connections",
            "Restart ECS tasks to reset pools",
            "Scale down and back up gradually",
        ],
    ),
}


def load_scenario(scenario_id: str) -> DemoScenario:
    """Load a demo scenario by ID.

    Args:
        scenario_id: The scenario identifier.

    Returns:
        The demo scenario.

    Raises:
        ValueError: If the scenario is not found.
    """
    if scenario_id not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Unknown scenario '{scenario_id}'. Available: {available}")
    return SCENARIOS[scenario_id]


def list_scenarios() -> list[dict[str, Any]]:
    """List all available scenarios.

    Returns:
        List of scenario summaries.
    """
    results = []
    for s in SCENARIOS.values():
        severity = s.alert.severity
        source = s.alert.source
        severity_val = severity.value if hasattr(severity, "value") else str(severity)
        source_val = source.value if hasattr(source, "value") else str(source)
        results.append(
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "severity": severity_val,
                "source": source_val,
            }
        )
    return results

"""Demo fixture data provider for offline testing.

This module provides realistic fixture data for all MCP tools,
enabling the demo mode to run without AWS credentials.
"""

from datetime import UTC, datetime, timedelta
from typing import Any


class DemoDataProvider:
    """Provides fixture data for demo mode."""

    def __init__(self, scenario: str = "crashloop"):
        """Initialize with a scenario name."""
        self.scenario = scenario
        self._load_scenario_data()

    def _load_scenario_data(self) -> None:
        """Load scenario-specific data."""
        self.scenario_data = SCENARIOS.get(self.scenario, SCENARIOS["crashloop"])

    def get_cloudwatch_logs(
        self,
        log_group: str,
        query: str | None = None,
        filter_pattern: str | None = None,
    ) -> dict[str, Any]:
        """Get CloudWatch logs fixture data."""
        return self.scenario_data.get("cloudwatch_logs", DEFAULT_CLOUDWATCH_LOGS)

    def get_cloudwatch_metrics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str],
    ) -> dict[str, Any]:
        """Get CloudWatch metrics fixture data."""
        metrics_key = f"{namespace}/{metric_name}"
        return self.scenario_data.get("cloudwatch_metrics", {}).get(metrics_key, DEFAULT_METRICS)

    def get_cloudwatch_alarms(
        self,
        alarm_name: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """Get CloudWatch alarms fixture data."""
        return self.scenario_data.get("cloudwatch_alarms", DEFAULT_ALARMS)

    def get_log_events(
        self,
        log_group: str,
        log_stream: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get log events fixture data."""
        return self.scenario_data.get("log_events", DEFAULT_LOG_EVENTS)

    def list_log_streams(
        self,
        log_group: str,
        prefix: str | None = None,
    ) -> dict[str, Any]:
        """List log streams fixture data."""
        return self.scenario_data.get("log_streams", DEFAULT_LOG_STREAMS)

    def get_pod_description(
        self,
        name: str,
        namespace: str = "default",
    ) -> dict[str, Any]:
        """Get pod description fixture data."""
        return self.scenario_data.get("pod_description", DEFAULT_POD_DESCRIPTION)

    def get_kubernetes_events(
        self,
        namespace: str = "default",
        resource_name: str | None = None,
        resource_kind: str | None = None,
    ) -> dict[str, Any]:
        """Get Kubernetes events fixture data."""
        return self.scenario_data.get("kubernetes_events", DEFAULT_K8S_EVENTS)

    def list_pods(
        self,
        namespace: str = "default",
        label_selector: str | None = None,
    ) -> dict[str, Any]:
        """List pods fixture data."""
        return self.scenario_data.get("pods_list", DEFAULT_PODS_LIST)

    def get_deployment_description(
        self,
        name: str,
        namespace: str = "default",
    ) -> dict[str, Any]:
        """Get deployment description fixture data."""
        return self.scenario_data.get("deployment_description", DEFAULT_DEPLOYMENT)

    def list_replicasets(
        self,
        namespace: str = "default",
        deployment_name: str | None = None,
    ) -> dict[str, Any]:
        """List ReplicaSets fixture data."""
        return self.scenario_data.get("replicasets", DEFAULT_REPLICASETS)

    def get_pod_logs(
        self,
        name: str,
        namespace: str = "default",
        container: str | None = None,
        previous: bool = False,
    ) -> dict[str, Any]:
        """Get pod logs fixture data."""
        logs_key = "pod_logs_previous" if previous else "pod_logs"
        return self.scenario_data.get(logs_key, DEFAULT_POD_LOGS)

    def get_node_description(self, name: str) -> dict[str, Any]:
        """Get node description fixture data."""
        return self.scenario_data.get("node_description", DEFAULT_NODE)

    def get_ecs_service(
        self,
        cluster: str,
        service: str,
    ) -> dict[str, Any]:
        """Get ECS service fixture data."""
        return self.scenario_data.get("ecs_service", DEFAULT_ECS_SERVICE)

    def list_ecs_tasks(
        self,
        cluster: str,
        service: str | None = None,
        status: str = "RUNNING",
    ) -> dict[str, Any]:
        """List ECS tasks fixture data."""
        return self.scenario_data.get("ecs_tasks", DEFAULT_ECS_TASKS)

    def get_stopped_tasks(
        self,
        cluster: str,
        service: str | None = None,
    ) -> dict[str, Any]:
        """Get stopped tasks fixture data."""
        return self.scenario_data.get("stopped_tasks", DEFAULT_STOPPED_TASKS)

    def get_task_definition(
        self,
        task_definition: str,
    ) -> dict[str, Any]:
        """Get task definition fixture data."""
        return self.scenario_data.get("task_definition", DEFAULT_TASK_DEF)

    def get_ecs_cluster(self, cluster: str) -> dict[str, Any]:
        """Get ECS cluster fixture data."""
        return self.scenario_data.get("ecs_cluster", DEFAULT_ECS_CLUSTER)


def _now() -> datetime:
    return datetime.now(UTC)


def _ago(minutes: int) -> str:
    return (_now() - timedelta(minutes=minutes)).isoformat()


# Default fixture data
DEFAULT_CLOUDWATCH_LOGS: dict[str, Any] = {
    "status": "Complete",
    "results": [],
    "statistics": {"recordsMatched": 0, "recordsScanned": 0},
}

DEFAULT_METRICS: dict[str, Any] = {
    "namespace": "AWS/ECS",
    "metric_name": "CPUUtilization",
    "datapoints": [],
}

DEFAULT_ALARMS: dict[str, Any] = {"alarms": []}

DEFAULT_LOG_EVENTS: dict[str, Any] = {"events": []}

DEFAULT_LOG_STREAMS: dict[str, Any] = {"log_streams": []}

DEFAULT_POD_DESCRIPTION: dict[str, Any] = {
    "name": "unknown",
    "namespace": "default",
    "phase": "Unknown",
    "node": None,
    "created": _ago(60),
    "labels": {},
    "container_statuses": [],
    "conditions": [],
    "resource_requests": {},
    "resource_limits": {},
}

DEFAULT_K8S_EVENTS: dict[str, Any] = {"events": []}

DEFAULT_PODS_LIST: dict[str, Any] = {"pods": []}

DEFAULT_DEPLOYMENT: dict[str, Any] = {
    "name": "unknown",
    "namespace": "default",
    "replicas": {"desired": 0, "ready": 0, "available": 0, "updated": 0},
    "strategy": "RollingUpdate",
    "selector": {},
    "conditions": [],
    "created": _ago(60),
    "generation": 1,
    "observed_generation": 1,
}

DEFAULT_REPLICASETS: dict[str, Any] = {"replicasets": []}

DEFAULT_POD_LOGS: dict[str, Any] = {
    "pod": "unknown",
    "namespace": "default",
    "container": "default",
    "previous": False,
    "logs": "",
}

DEFAULT_NODE: dict[str, Any] = {
    "name": "unknown",
    "labels": {},
    "conditions": [],
    "capacity": {},
    "allocatable": {},
    "info": {},
}

DEFAULT_ECS_SERVICE: dict[str, Any] = {
    "service_name": "unknown",
    "cluster": "unknown",
    "status": "ACTIVE",
    "desired_count": 0,
    "running_count": 0,
    "pending_count": 0,
    "launch_type": "FARGATE",
    "task_definition": "unknown:1",
    "deployments": [],
    "events": [],
    "created_at": _ago(1440),
}

DEFAULT_ECS_TASKS: dict[str, Any] = {"tasks": []}

DEFAULT_STOPPED_TASKS: dict[str, Any] = {"stopped_tasks": []}

DEFAULT_TASK_DEF: dict[str, Any] = {
    "family": "unknown",
    "revision": 1,
    "status": "ACTIVE",
    "cpu": "256",
    "memory": "512",
    "network_mode": "awsvpc",
    "requires_compatibilities": ["FARGATE"],
    "containers": [],
    "registered_at": _ago(1440),
}

DEFAULT_ECS_CLUSTER: dict[str, Any] = {
    "cluster_name": "unknown",
    "status": "ACTIVE",
    "registered_container_instances": 0,
    "running_tasks": 0,
    "pending_tasks": 0,
    "active_services": 0,
    "statistics": {},
    "capacity_providers": [],
}


# Scenario-specific data
SCENARIOS: dict[str, dict[str, Any]] = {
    # Scenario 1: EKS CrashLoopBackOff
    "crashloop": {
        "pod_description": {
            "name": "payment-service-7d4f8b9c5d-x2k9m",
            "namespace": "production",
            "phase": "Running",
            "node": "ip-10-0-1-45.us-west-2.compute.internal",
            "created": _ago(45),
            "labels": {
                "app": "payment-service",
                "version": "v2.3.1",
                "team": "payments",
            },
            "container_statuses": [
                {
                    "name": "payment-service",
                    "ready": False,
                    "restart_count": 8,
                    "image": "123456789.dkr.ecr.us-west-2.amazonaws.com/payment-service:v2.3.1",
                    "state": "Waiting",
                    "reason": "CrashLoopBackOff",
                    "message": "back-off 5m0s restarting failed container",
                    "last_termination": {
                        "reason": "Error",
                        "exit_code": 1,
                        "finished_at": _ago(2),
                    },
                }
            ],
            "conditions": [
                {
                    "type": "Initialized",
                    "status": "True",
                    "reason": None,
                    "message": None,
                    "last_transition": _ago(45),
                },
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "ContainersNotReady",
                    "message": "containers with unready status: [payment-service]",
                    "last_transition": _ago(2),
                },
                {
                    "type": "ContainersReady",
                    "status": "False",
                    "reason": "ContainersNotReady",
                    "message": "containers with unready status: [payment-service]",
                    "last_transition": _ago(2),
                },
            ],
            "resource_requests": {"payment-service": {"cpu": "500m", "memory": "512Mi"}},
            "resource_limits": {"payment-service": {"cpu": "1000m", "memory": "1Gi"}},
        },
        "kubernetes_events": {
            "events": [
                {
                    "type": "Warning",
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container",
                    "count": 8,
                    "first_seen": _ago(40),
                    "last_seen": _ago(2),
                    "source": "kubelet",
                    "involved_object": {
                        "kind": "Pod",
                        "name": "payment-service-7d4f8b9c5d-x2k9m",
                    },
                },
                {
                    "type": "Warning",
                    "reason": "Unhealthy",
                    "message": "Readiness probe failed: HTTP probe failed with statuscode: 503",
                    "count": 15,
                    "first_seen": _ago(42),
                    "last_seen": _ago(3),
                    "source": "kubelet",
                    "involved_object": {
                        "kind": "Pod",
                        "name": "payment-service-7d4f8b9c5d-x2k9m",
                    },
                },
                {
                    "type": "Normal",
                    "reason": "Pulled",
                    "message": "Container image already present on machine",
                    "count": 9,
                    "first_seen": _ago(45),
                    "last_seen": _ago(2),
                    "source": "kubelet",
                    "involved_object": {
                        "kind": "Pod",
                        "name": "payment-service-7d4f8b9c5d-x2k9m",
                    },
                },
            ]
        },
        "pod_logs": {
            "pod": "payment-service-7d4f8b9c5d-x2k9m",
            "namespace": "production",
            "container": "payment-service",
            "previous": False,
            "logs": """2026-11-02T03:12:45.123Z INFO  Starting payment-service v2.3.1
2026-11-02T03:12:45.234Z INFO  Loading configuration from environment
2026-11-02T03:12:45.345Z INFO  Connecting to database: payments-db.cluster-abc123.us-west-2.rds.amazonaws.com
2026-11-02T03:12:46.456Z ERROR Database connection failed: FATAL: password authentication failed for user "payment_svc"
2026-11-02T03:12:46.567Z ERROR Retrying database connection (1/3)...
2026-11-02T03:12:47.678Z ERROR Database connection failed: FATAL: password authentication failed for user "payment_svc"
2026-11-02T03:12:47.789Z ERROR Retrying database connection (2/3)...
2026-11-02T03:12:48.890Z ERROR Database connection failed: FATAL: password authentication failed for user "payment_svc"
2026-11-02T03:12:48.901Z ERROR Retrying database connection (3/3)...
2026-11-02T03:12:49.012Z FATAL Unable to connect to database after 3 retries. Shutting down.
2026-11-02T03:12:49.023Z INFO  Shutdown complete""",
        },
        "pod_logs_previous": {
            "pod": "payment-service-7d4f8b9c5d-x2k9m",
            "namespace": "production",
            "container": "payment-service",
            "previous": True,
            "logs": """2026-11-02T03:07:32.123Z INFO  Starting payment-service v2.3.1
2026-11-02T03:07:32.234Z INFO  Loading configuration from environment
2026-11-02T03:07:32.345Z INFO  Connecting to database: payments-db.cluster-abc123.us-west-2.rds.amazonaws.com
2026-11-02T03:07:33.456Z ERROR Database connection failed: FATAL: password authentication failed for user "payment_svc"
2026-11-02T03:07:33.567Z ERROR Retrying database connection (1/3)...
2026-11-02T03:07:34.678Z ERROR Database connection failed: FATAL: password authentication failed for user "payment_svc"
2026-11-02T03:07:34.789Z ERROR Retrying database connection (2/3)...
2026-11-02T03:07:35.890Z ERROR Database connection failed: FATAL: password authentication failed for user "payment_svc"
2026-11-02T03:07:35.901Z ERROR Retrying database connection (3/3)...
2026-11-02T03:07:36.012Z FATAL Unable to connect to database after 3 retries. Shutting down.""",
        },
        "deployment_description": {
            "name": "payment-service",
            "namespace": "production",
            "replicas": {"desired": 3, "ready": 2, "available": 2, "updated": 3},
            "strategy": "RollingUpdate",
            "selector": {"app": "payment-service"},
            "conditions": [
                {
                    "type": "Progressing",
                    "status": "True",
                    "reason": "NewReplicaSetAvailable",
                    "message": "ReplicaSet 'payment-service-7d4f8b9c5d' has successfully progressed.",
                    "last_update": _ago(45),
                },
                {
                    "type": "Available",
                    "status": "False",
                    "reason": "MinimumReplicasUnavailable",
                    "message": "Deployment does not have minimum availability.",
                    "last_update": _ago(40),
                },
            ],
            "created": _ago(10080),
            "generation": 15,
            "observed_generation": 15,
        },
        "replicasets": {
            "replicasets": [
                {
                    "name": "payment-service-7d4f8b9c5d",
                    "replicas": {"desired": 3, "ready": 2, "available": 2},
                    "created": _ago(45),
                    "revision": "15",
                },
                {
                    "name": "payment-service-6c3e7a8b4c",
                    "replicas": {"desired": 0, "ready": 0, "available": 0},
                    "created": _ago(1440),
                    "revision": "14",
                },
            ]
        },
        "cloudwatch_logs": {
            "status": "Complete",
            "results": [
                [
                    {"field": "@timestamp", "value": _ago(2)},
                    {
                        "field": "@message",
                        "value": 'FATAL: password authentication failed for user "payment_svc"',
                    },
                    {"field": "@logStream", "value": "payment-service-7d4f8b9c5d-x2k9m"},
                ],
                [
                    {"field": "@timestamp", "value": _ago(5)},
                    {
                        "field": "@message",
                        "value": 'FATAL: password authentication failed for user "payment_svc"',
                    },
                    {"field": "@logStream", "value": "payment-service-7d4f8b9c5d-x2k9m"},
                ],
                [
                    {"field": "@timestamp", "value": _ago(8)},
                    {
                        "field": "@message",
                        "value": 'FATAL: password authentication failed for user "payment_svc"',
                    },
                    {"field": "@logStream", "value": "payment-service-7d4f8b9c5d-x2k9m"},
                ],
            ],
            "statistics": {"recordsMatched": 8, "recordsScanned": 1250},
        },
        "cloudwatch_alarms": {
            "alarms": [
                {
                    "name": "payment-service-pod-restarts",
                    "state": "ALARM",
                    "reason": "Threshold Crossed: 1 datapoint (8.0) was greater than or equal to the threshold (3.0).",
                    "metric_name": "pod_restart_count",
                    "namespace": "ContainerInsights",
                    "threshold": 3.0,
                    "comparison": "GreaterThanOrEqualToThreshold",
                    "evaluation_periods": 1,
                    "updated": _ago(5),
                }
            ]
        },
    },
    # Scenario 2: ECS OOM Kill
    "oom": {
        "ecs_service": {
            "service_name": "order-processor",
            "cluster": "production-cluster",
            "status": "ACTIVE",
            "desired_count": 5,
            "running_count": 3,
            "pending_count": 2,
            "launch_type": "FARGATE",
            "task_definition": "order-processor:42",
            "deployments": [
                {
                    "id": "ecs-svc/1234567890",
                    "status": "PRIMARY",
                    "task_definition": "order-processor:42",
                    "desired_count": 5,
                    "running_count": 3,
                    "pending_count": 2,
                    "rollout_state": "IN_PROGRESS",
                    "created_at": _ago(30),
                }
            ],
            "events": [
                {
                    "timestamp": _ago(2),
                    "message": "(service order-processor) has begun draining connections on 2 tasks.",
                },
                {
                    "timestamp": _ago(3),
                    "message": "(service order-processor) stopped 2 tasks: task abc123 (container stopped due to memory limit), task def456 (container stopped due to memory limit)",
                },
                {
                    "timestamp": _ago(5),
                    "message": "(service order-processor) has started 2 tasks: task ghi789, task jkl012.",
                },
                {
                    "timestamp": _ago(10),
                    "message": "(service order-processor) stopped 1 task: task mno345 (container stopped due to memory limit)",
                },
            ],
            "created_at": _ago(43200),
        },
        "stopped_tasks": {
            "stopped_tasks": [
                {
                    "task_id": "abc123def456",
                    "stopped_at": _ago(3),
                    "stopped_reason": "Essential container in task exited",
                    "stop_code": "EssentialContainerExited",
                    "containers": [
                        {
                            "name": "order-processor",
                            "exit_code": 137,
                            "reason": "OutOfMemoryError: Container killed due to memory usage",
                            "likely_oom": True,
                        }
                    ],
                },
                {
                    "task_id": "def456ghi789",
                    "stopped_at": _ago(3),
                    "stopped_reason": "Essential container in task exited",
                    "stop_code": "EssentialContainerExited",
                    "containers": [
                        {
                            "name": "order-processor",
                            "exit_code": 137,
                            "reason": "OutOfMemoryError: Container killed due to memory usage",
                            "likely_oom": True,
                        }
                    ],
                },
                {
                    "task_id": "mno345pqr678",
                    "stopped_at": _ago(10),
                    "stopped_reason": "Essential container in task exited",
                    "stop_code": "EssentialContainerExited",
                    "containers": [
                        {
                            "name": "order-processor",
                            "exit_code": 137,
                            "reason": "OutOfMemoryError: Container killed due to memory usage",
                            "likely_oom": True,
                        }
                    ],
                },
            ]
        },
        "task_definition": {
            "family": "order-processor",
            "revision": 42,
            "status": "ACTIVE",
            "cpu": "512",
            "memory": "1024",
            "network_mode": "awsvpc",
            "requires_compatibilities": ["FARGATE"],
            "containers": [
                {
                    "name": "order-processor",
                    "image": "123456789.dkr.ecr.us-west-2.amazonaws.com/order-processor:v3.1.0",
                    "cpu": 512,
                    "memory": 1024,
                    "memory_reservation": 512,
                    "essential": True,
                    "health_check": True,
                    "log_driver": "awslogs",
                }
            ],
            "registered_at": _ago(1440),
        },
        "cloudwatch_metrics": {
            "AWS/ECS/MemoryUtilization": {
                "namespace": "AWS/ECS",
                "metric_name": "MemoryUtilization",
                "datapoints": [
                    {"timestamp": _ago(30), "value": 65.2, "unit": "Percent"},
                    {"timestamp": _ago(25), "value": 72.8, "unit": "Percent"},
                    {"timestamp": _ago(20), "value": 81.5, "unit": "Percent"},
                    {"timestamp": _ago(15), "value": 89.3, "unit": "Percent"},
                    {"timestamp": _ago(10), "value": 95.7, "unit": "Percent"},
                    {"timestamp": _ago(5), "value": 99.2, "unit": "Percent"},
                    {"timestamp": _ago(2), "value": 99.8, "unit": "Percent"},
                ],
            }
        },
        "cloudwatch_logs": {
            "status": "Complete",
            "results": [
                [
                    {"field": "@timestamp", "value": _ago(3)},
                    {"field": "@message", "value": "java.lang.OutOfMemoryError: Java heap space"},
                    {"field": "@logStream", "value": "order-processor/order-processor/abc123"},
                ],
                [
                    {"field": "@timestamp", "value": _ago(4)},
                    {"field": "@message", "value": "WARN  Memory usage critical: 98% of heap used"},
                    {"field": "@logStream", "value": "order-processor/order-processor/abc123"},
                ],
                [
                    {"field": "@timestamp", "value": _ago(5)},
                    {"field": "@message", "value": "Processing large batch: 50000 orders"},
                    {"field": "@logStream", "value": "order-processor/order-processor/abc123"},
                ],
            ],
            "statistics": {"recordsMatched": 15, "recordsScanned": 2500},
        },
        "cloudwatch_alarms": {
            "alarms": [
                {
                    "name": "order-processor-memory-high",
                    "state": "ALARM",
                    "reason": "Threshold Crossed: 3 datapoints were greater than or equal to the threshold (90.0).",
                    "metric_name": "MemoryUtilization",
                    "namespace": "AWS/ECS",
                    "threshold": 90.0,
                    "comparison": "GreaterThanOrEqualToThreshold",
                    "evaluation_periods": 3,
                    "updated": _ago(5),
                },
                {
                    "name": "order-processor-task-failures",
                    "state": "ALARM",
                    "reason": "Threshold Crossed: 1 datapoint (3.0) was greater than or equal to the threshold (2.0).",
                    "metric_name": "ServiceTaskFailures",
                    "namespace": "AWS/ECS",
                    "threshold": 2.0,
                    "comparison": "GreaterThanOrEqualToThreshold",
                    "evaluation_periods": 1,
                    "updated": _ago(3),
                },
            ]
        },
    },
    # Scenario 3: ALB 5xx Spike
    "alb-5xx": {
        "cloudwatch_metrics": {
            "AWS/ApplicationELB/HTTPCode_Target_5XX_Count": {
                "namespace": "AWS/ApplicationELB",
                "metric_name": "HTTPCode_Target_5XX_Count",
                "datapoints": [
                    {"timestamp": _ago(30), "value": 2, "unit": "Count"},
                    {"timestamp": _ago(25), "value": 5, "unit": "Count"},
                    {"timestamp": _ago(20), "value": 45, "unit": "Count"},
                    {"timestamp": _ago(15), "value": 312, "unit": "Count"},
                    {"timestamp": _ago(10), "value": 587, "unit": "Count"},
                    {"timestamp": _ago(5), "value": 423, "unit": "Count"},
                    {"timestamp": _ago(2), "value": 198, "unit": "Count"},
                ],
            },
            "AWS/ApplicationELB/TargetResponseTime": {
                "namespace": "AWS/ApplicationELB",
                "metric_name": "TargetResponseTime",
                "datapoints": [
                    {"timestamp": _ago(30), "value": 0.125, "unit": "Seconds"},
                    {"timestamp": _ago(25), "value": 0.342, "unit": "Seconds"},
                    {"timestamp": _ago(20), "value": 1.234, "unit": "Seconds"},
                    {"timestamp": _ago(15), "value": 4.567, "unit": "Seconds"},
                    {"timestamp": _ago(10), "value": 8.901, "unit": "Seconds"},
                    {"timestamp": _ago(5), "value": 5.432, "unit": "Seconds"},
                    {"timestamp": _ago(2), "value": 2.345, "unit": "Seconds"},
                ],
            },
            "AWS/RDS/DatabaseConnections": {
                "namespace": "AWS/RDS",
                "metric_name": "DatabaseConnections",
                "datapoints": [
                    {"timestamp": _ago(30), "value": 45, "unit": "Count"},
                    {"timestamp": _ago(25), "value": 78, "unit": "Count"},
                    {"timestamp": _ago(20), "value": 145, "unit": "Count"},
                    {"timestamp": _ago(15), "value": 198, "unit": "Count"},
                    {"timestamp": _ago(10), "value": 200, "unit": "Count"},
                    {"timestamp": _ago(5), "value": 200, "unit": "Count"},
                    {"timestamp": _ago(2), "value": 185, "unit": "Count"},
                ],
            },
        },
        "cloudwatch_logs": {
            "status": "Complete",
            "results": [
                [
                    {"field": "@timestamp", "value": _ago(10)},
                    {
                        "field": "@message",
                        "value": "ERROR SQLSTATE[HY000] [1040] Too many connections",
                    },
                    {"field": "@logStream", "value": "api-service/api/task123"},
                ],
                [
                    {"field": "@timestamp", "value": _ago(11)},
                    {
                        "field": "@message",
                        "value": "ERROR Database connection pool exhausted, waiting for connection",
                    },
                    {"field": "@logStream", "value": "api-service/api/task456"},
                ],
                [
                    {"field": "@timestamp", "value": _ago(12)},
                    {
                        "field": "@message",
                        "value": "ERROR Request timeout after 30000ms waiting for database connection",
                    },
                    {"field": "@logStream", "value": "api-service/api/task789"},
                ],
                [
                    {"field": "@timestamp", "value": _ago(15)},
                    {"field": "@message", "value": "WARN  Connection pool size: 200/200 (max)"},
                    {"field": "@logStream", "value": "api-service/api/task123"},
                ],
            ],
            "statistics": {"recordsMatched": 847, "recordsScanned": 15000},
        },
        "cloudwatch_alarms": {
            "alarms": [
                {
                    "name": "api-alb-5xx-high",
                    "state": "ALARM",
                    "reason": "Threshold Crossed: 5 datapoints were greater than or equal to the threshold (100.0).",
                    "metric_name": "HTTPCode_Target_5XX_Count",
                    "namespace": "AWS/ApplicationELB",
                    "threshold": 100.0,
                    "comparison": "GreaterThanOrEqualToThreshold",
                    "evaluation_periods": 2,
                    "updated": _ago(15),
                },
                {
                    "name": "api-response-time-high",
                    "state": "ALARM",
                    "reason": "Threshold Crossed: 3 datapoints were greater than or equal to the threshold (2.0).",
                    "metric_name": "TargetResponseTime",
                    "namespace": "AWS/ApplicationELB",
                    "threshold": 2.0,
                    "comparison": "GreaterThanOrEqualToThreshold",
                    "evaluation_periods": 3,
                    "updated": _ago(10),
                },
                {
                    "name": "rds-connections-high",
                    "state": "ALARM",
                    "reason": "Threshold Crossed: 4 datapoints were greater than or equal to the threshold (180.0).",
                    "metric_name": "DatabaseConnections",
                    "namespace": "AWS/RDS",
                    "threshold": 180.0,
                    "comparison": "GreaterThanOrEqualToThreshold",
                    "evaluation_periods": 2,
                    "updated": _ago(12),
                },
            ]
        },
        "ecs_service": {
            "service_name": "api-service",
            "cluster": "production-cluster",
            "status": "ACTIVE",
            "desired_count": 10,
            "running_count": 10,
            "pending_count": 0,
            "launch_type": "FARGATE",
            "task_definition": "api-service:28",
            "deployments": [
                {
                    "id": "ecs-svc/9876543210",
                    "status": "PRIMARY",
                    "task_definition": "api-service:28",
                    "desired_count": 10,
                    "running_count": 10,
                    "pending_count": 0,
                    "rollout_state": "COMPLETED",
                    "created_at": _ago(4320),
                }
            ],
            "events": [
                {
                    "timestamp": _ago(5),
                    "message": "(service api-service) registered 10 targets in target-group api-tg",
                },
            ],
            "created_at": _ago(43200),
        },
    },
}

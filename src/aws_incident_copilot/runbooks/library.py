"""Runbook library with simple keyword-based retrieval.

This module provides a lightweight runbook retrieval system using
keyword matching and TF-IDF-like scoring. For production use,
consider integrating with Amazon Bedrock Knowledge Bases.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Runbook:
    """A runbook for incident response."""

    id: str
    title: str
    description: str
    symptoms: list[str]
    keywords: list[str]
    steps: list[str]
    related_services: list[str] = field(default_factory=list)
    severity: str = "medium"
    estimated_time: str = "15 minutes"
    requires_approval: bool = True


class RunbookLibrary:
    """A simple runbook library with keyword-based retrieval."""

    def __init__(self, runbooks_dir: Path | str | None = None):
        """Initialize the library.

        Args:
            runbooks_dir: Directory containing YAML runbook files.
                If None, uses the default runbooks directory.
        """
        self.runbooks: dict[str, Runbook] = {}
        self._keyword_index: dict[str, set[str]] = {}

        if runbooks_dir:
            self.load_from_directory(Path(runbooks_dir))
        else:
            self._load_default_runbooks()

    def _load_default_runbooks(self) -> None:
        """Load the built-in runbooks."""
        for rb_data in DEFAULT_RUNBOOKS:
            runbook = Runbook(**rb_data)
            self.add_runbook(runbook)

    def load_from_directory(self, directory: Path) -> None:
        """Load runbooks from YAML files in a directory.

        Args:
            directory: Path to directory containing YAML runbook files.
        """
        if not directory.exists():
            return

        for yaml_file in directory.glob("*.yaml"):
            try:
                with yaml_file.open() as f:
                    data = yaml.safe_load(f)
                    if data:
                        runbook = Runbook(**data)
                        self.add_runbook(runbook)
            except Exception as e:
                print(f"Warning: Failed to load runbook {yaml_file}: {e}")

    def add_runbook(self, runbook: Runbook) -> None:
        """Add a runbook to the library.

        Args:
            runbook: The runbook to add.
        """
        self.runbooks[runbook.id] = runbook
        self._index_runbook(runbook)

    def _index_runbook(self, runbook: Runbook) -> None:
        """Index a runbook for keyword search.

        Args:
            runbook: The runbook to index.
        """
        all_text = " ".join(
            [
                runbook.title,
                runbook.description,
                " ".join(runbook.symptoms),
                " ".join(runbook.keywords),
                " ".join(runbook.related_services),
            ]
        ).lower()

        tokens = set(re.findall(r"\w+", all_text))

        for token in tokens:
            if token not in self._keyword_index:
                self._keyword_index[token] = set()
            self._keyword_index[token].add(runbook.id)

    def search(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.1,
    ) -> list[tuple[Runbook, float]]:
        """Search for relevant runbooks.

        Args:
            query: The search query.
            limit: Maximum number of results.
            min_score: Minimum relevance score (0-1).

        Returns:
            List of (runbook, score) tuples, sorted by relevance.
        """
        query_tokens = set(re.findall(r"\w+", query.lower()))

        if not query_tokens:
            return []

        scores: dict[str, float] = {}

        for token in query_tokens:
            matching_ids = self._keyword_index.get(token, set())
            for rb_id in matching_ids:
                scores[rb_id] = scores.get(rb_id, 0) + 1

        max_possible = len(query_tokens)
        results = []

        for rb_id, match_count in scores.items():
            score = match_count / max_possible
            if score >= min_score:
                results.append((self.runbooks[rb_id], score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_by_id(self, runbook_id: str) -> Runbook | None:
        """Get a runbook by ID.

        Args:
            runbook_id: The runbook identifier.

        Returns:
            The runbook or None if not found.
        """
        return self.runbooks.get(runbook_id)

    def get_by_service(self, service: str) -> list[Runbook]:
        """Get runbooks for a specific service.

        Args:
            service: The service name.

        Returns:
            List of relevant runbooks.
        """
        service_lower = service.lower()
        return [
            rb
            for rb in self.runbooks.values()
            if service_lower in [s.lower() for s in rb.related_services]
        ]


def search_runbooks(
    query: str,
    library: RunbookLibrary | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search runbooks and return formatted results.

    Args:
        query: The search query (symptoms, error messages, etc.).
        library: The runbook library (uses default if None).
        limit: Maximum number of results.

    Returns:
        List of matching runbooks with relevance scores.
    """
    if library is None:
        library = RunbookLibrary()

    results = library.search(query, limit=limit)

    return [
        {
            "id": rb.id,
            "title": rb.title,
            "description": rb.description,
            "symptoms": rb.symptoms,
            "steps": rb.steps,
            "relevance_score": score,
            "requires_approval": rb.requires_approval,
            "estimated_time": rb.estimated_time,
        }
        for rb, score in results
    ]


DEFAULT_RUNBOOKS: list[dict[str, Any]] = [
    {
        "id": "rb-eks-crashloop",
        "title": "EKS Pod CrashLoopBackOff Troubleshooting",
        "description": "Steps to diagnose and resolve Kubernetes pods stuck in CrashLoopBackOff state.",
        "symptoms": [
            "Pod status shows CrashLoopBackOff",
            "Container restarts repeatedly",
            "Readiness or liveness probes failing",
            "Application fails to start",
        ],
        "keywords": [
            "crashloopbackoff",
            "crash",
            "loop",
            "restart",
            "pod",
            "kubernetes",
            "eks",
            "container",
            "backoff",
            "probe",
            "readiness",
            "liveness",
        ],
        "steps": [
            "Check pod status: kubectl describe pod <pod-name> -n <namespace>",
            "Review container logs: kubectl logs <pod-name> -n <namespace> --previous",
            "Check for resource constraints (CPU/memory limits)",
            "Verify environment variables and secrets are correctly mounted",
            "Check if dependent services (databases, APIs) are available",
            "Review recent deployment changes or image updates",
            "If probe-related: verify probe endpoints return healthy responses",
            "Consider rollback if issue started after recent deployment",
        ],
        "related_services": ["eks", "kubernetes", "deployment"],
        "severity": "high",
        "estimated_time": "15-30 minutes",
        "requires_approval": True,
    },
    {
        "id": "rb-eks-oom",
        "title": "EKS Pod OOMKilled Troubleshooting",
        "description": "Steps to diagnose and resolve pods being killed due to out-of-memory conditions.",
        "symptoms": [
            "Pod terminated with OOMKilled reason",
            "Exit code 137",
            "Container memory usage at limit",
            "Sudden pod restarts under load",
        ],
        "keywords": [
            "oom",
            "oomkilled",
            "memory",
            "exit code 137",
            "killed",
            "outofmemory",
            "heap",
            "java",
            "container",
            "limit",
            "pod",
            "eks",
            "kubernetes",
        ],
        "steps": [
            "Check pod events: kubectl describe pod <pod-name> -n <namespace>",
            "Review memory metrics in CloudWatch Container Insights",
            "Analyze container memory limits vs. actual usage",
            "Check for memory leaks in application logs",
            "Review JVM heap settings if Java application",
            "Consider increasing memory limits in deployment",
            "Implement memory profiling for long-term fix",
        ],
        "related_services": ["eks", "kubernetes", "cloudwatch"],
        "severity": "high",
        "estimated_time": "20-45 minutes",
        "requires_approval": True,
    },
    {
        "id": "rb-ecs-oom",
        "title": "ECS Task OOMKilled Troubleshooting",
        "description": "Steps to diagnose and resolve ECS tasks terminated due to memory limits.",
        "symptoms": [
            "Task stopped with exit code 137",
            "Essential container exited",
            "Memory utilization at 100%",
            "OutOfMemoryError in logs",
        ],
        "keywords": [
            "ecs",
            "fargate",
            "oom",
            "memory",
            "exit code 137",
            "killed",
            "task",
            "container",
            "outofmemory",
            "heap",
            "essential",
        ],
        "steps": [
            "Check stopped task details: aws ecs describe-tasks",
            "Review CloudWatch metrics for memory utilization",
            "Analyze task definition memory settings",
            "Check application logs for memory-related errors",
            "For Java: verify JVM heap settings match container limits",
            "Consider increasing task memory in task definition",
            "Implement batch size limits if processing large datasets",
        ],
        "related_services": ["ecs", "fargate", "cloudwatch"],
        "severity": "high",
        "estimated_time": "20-45 minutes",
        "requires_approval": True,
    },
    {
        "id": "rb-alb-5xx",
        "title": "ALB 5xx Errors Troubleshooting",
        "description": "Steps to diagnose and resolve elevated 5xx errors from Application Load Balancer targets.",
        "symptoms": [
            "HTTPCode_Target_5XX_Count elevated",
            "Increased response times",
            "Intermittent 502/503/504 errors",
            "Target health check failures",
        ],
        "keywords": [
            "alb",
            "5xx",
            "502",
            "503",
            "504",
            "error",
            "target",
            "loadbalancer",
            "response time",
            "timeout",
            "health check",
            "elb",
            "application",
        ],
        "steps": [
            "Check target group health in EC2 console or CLI",
            "Review CloudWatch ALB metrics: 5xx count, response time, healthy hosts",
            "Check application logs for error patterns",
            "Verify target security groups allow health check traffic",
            "Check backend resource constraints (CPU, memory, connections)",
            "Review recent deployments or configuration changes",
            "Consider scaling up targets if load-related",
        ],
        "related_services": ["alb", "ecs", "ec2", "cloudwatch"],
        "severity": "critical",
        "estimated_time": "15-30 minutes",
        "requires_approval": True,
    },
    {
        "id": "rb-db-connections",
        "title": "Database Connection Pool Exhaustion",
        "description": "Steps to diagnose and resolve database connection pool exhaustion issues.",
        "symptoms": [
            "Too many connections error",
            "Connection pool exhausted",
            "Request timeouts waiting for connections",
            "Elevated database connection count",
        ],
        "keywords": [
            "database",
            "connection",
            "pool",
            "exhausted",
            "rds",
            "mysql",
            "postgres",
            "too many connections",
            "timeout",
            "max_connections",
        ],
        "steps": [
            "Check RDS connection metrics in CloudWatch",
            "Review application connection pool settings",
            "Look for connection leaks in application code",
            "Check for long-running queries holding connections",
            "Consider increasing max_connections (may need larger instance)",
            "Review and tune connection pool size per task/pod",
            "Implement connection timeout and validation settings",
        ],
        "related_services": ["rds", "aurora", "database"],
        "severity": "high",
        "estimated_time": "20-40 minutes",
        "requires_approval": True,
    },
    {
        "id": "rb-secret-rotation",
        "title": "Secret/Credential Rotation Failure",
        "description": "Steps to diagnose and resolve authentication failures after credential changes.",
        "symptoms": [
            "Authentication failed errors",
            "Password authentication failed",
            "Invalid credentials after rotation",
            "Service unable to connect after secret update",
        ],
        "keywords": [
            "secret",
            "credential",
            "password",
            "authentication",
            "failed",
            "rotation",
            "secrets manager",
            "ssm",
            "environment variable",
        ],
        "steps": [
            "Verify the current secret value in Secrets Manager or SSM",
            "Check if application has the latest secret version",
            "For EKS: verify Kubernetes secret is synced with source",
            "For ECS: check task definition references correct secret ARN",
            "Restart pods/tasks to pick up new secret values",
            "Verify IAM permissions to access secrets",
            "Check secret rotation lambda logs if automated rotation",
        ],
        "related_services": ["secrets-manager", "ssm", "eks", "ecs", "iam"],
        "severity": "high",
        "estimated_time": "15-30 minutes",
        "requires_approval": True,
    },
    {
        "id": "rb-image-pull",
        "title": "Container Image Pull Failure",
        "description": "Steps to diagnose and resolve container image pull failures.",
        "symptoms": [
            "ImagePullBackOff",
            "ErrImagePull",
            "Failed to pull image",
            "Repository not found or access denied",
        ],
        "keywords": [
            "image",
            "pull",
            "ecr",
            "docker",
            "registry",
            "imagepullbackoff",
            "errimagepull",
            "repository",
            "access denied",
            "not found",
        ],
        "steps": [
            "Verify image exists in ECR: aws ecr describe-images",
            "Check IAM permissions for ECR access",
            "Verify node/task has internet access for public images",
            "For EKS: check imagePullSecrets configuration",
            "Verify ECR repository policy allows access",
            "Check if image tag exists and hasn't been deleted",
            "Review VPC endpoints if using private ECR access",
        ],
        "related_services": ["ecr", "eks", "ecs", "iam"],
        "severity": "medium",
        "estimated_time": "10-20 minutes",
        "requires_approval": False,
    },
]

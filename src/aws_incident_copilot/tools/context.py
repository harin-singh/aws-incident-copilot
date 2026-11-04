"""Shared context for investigation tools.

Callers inject demo fixtures or live AWS/Kubernetes clients so the same
tool implementations run in demo mode, unit tests, and live CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aws_incident_copilot.demo.fixtures import DemoDataProvider


@dataclass
class InvestigationContext:
    """Runtime context for CloudWatch, Kubernetes, and ECS tools."""

    demo_mode: bool = True
    demo_provider: DemoDataProvider | None = None
    region: str = "us-west-2"
    kubeconfig_path: str | None = None
    boto3_session: Any = None
    logs_client: Any = None
    cloudwatch_client: Any = None
    ecs_client: Any = None
    k8s_core: Any = None
    k8s_apps: Any = None

    def provider(self) -> DemoDataProvider:
        """Return the demo fixture provider, creating a default if needed."""
        if self.demo_provider is None:
            self.demo_provider = DemoDataProvider()
        return self.demo_provider

    def client(self, service: str) -> Any:
        """Return an injectable or newly created boto3 client."""
        if service == "logs" and self.logs_client is not None:
            return self.logs_client
        if service == "cloudwatch" and self.cloudwatch_client is not None:
            return self.cloudwatch_client
        if service == "ecs" and self.ecs_client is not None:
            return self.ecs_client

        session = self.boto3_session
        if session is None:
            import boto3

            session = boto3
        return session.client(service, region_name=self.region)

    def kubernetes_apis(self) -> tuple[Any, Any]:
        """Return (CoreV1Api, AppsV1Api), loading kubeconfig when not injected."""
        if self.k8s_core is not None and self.k8s_apps is not None:
            return self.k8s_core, self.k8s_apps

        from kubernetes import client, config

        if self.kubeconfig_path:
            config.load_kube_config(config_file=self.kubeconfig_path)
        else:
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()

        self.k8s_core = client.CoreV1Api()
        self.k8s_apps = client.AppsV1Api()
        return self.k8s_core, self.k8s_apps

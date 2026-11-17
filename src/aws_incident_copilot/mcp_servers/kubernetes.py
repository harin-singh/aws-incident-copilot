"""Kubernetes MCP server — thin wrapper over shared investigation impls."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from aws_incident_copilot.demo.fixtures import DemoDataProvider  # noqa: TC001
from aws_incident_copilot.tools.context import InvestigationContext
from aws_incident_copilot.tools.kubernetes import (
    describe_deployment_impl,
    describe_node_impl,
    describe_pod_impl,
    get_events_impl,
    get_pod_logs_impl,
    list_pods_impl,
    list_replicasets_impl,
)


def create_kubernetes_server(
    demo_mode: bool = True,
    demo_provider: DemoDataProvider | None = None,
    kubeconfig_path: str | None = None,
    ctx: InvestigationContext | None = None,
) -> MCPServer:
    """Create a Kubernetes MCP server using the shared tool implementations."""
    server = MCPServer(
        name="kubernetes-tools",
        title="Kubernetes Investigation Tools",
        description="Tools for investigating Kubernetes pods, events, and deployments in EKS",
        version="1.0.0",
    )
    context = ctx or InvestigationContext(
        demo_mode=demo_mode,
        demo_provider=demo_provider,
        kubeconfig_path=kubeconfig_path,
    )

    @server.tool(
        description="Get detailed information about a pod, including status, containers, "
        "conditions, and recent events. Essential for investigating pod failures."
    )
    def describe_pod(
        name: str,
        namespace: str = "default",
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """Get detailed pod information."""
        return describe_pod_impl(context, name, namespace, cluster)

    @server.tool(
        description="Get Kubernetes events for a resource or namespace. Events show "
        "scheduling failures, OOM kills, image pull errors, and other issues."
    )
    def get_events(
        namespace: str = "default",
        resource_name: str | None = None,
        resource_kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get Kubernetes events."""
        return get_events_impl(context, namespace, resource_name, resource_kind, limit)

    @server.tool(
        description="List pods in a namespace with optional label selector. Use this to "
        "find pods matching specific criteria or to see overall namespace health."
    )
    def list_pods(
        namespace: str = "default",
        label_selector: str | None = None,
        field_selector: str | None = None,
    ) -> dict[str, Any]:
        """List pods in a namespace."""
        return list_pods_impl(context, namespace, label_selector, field_selector)

    @server.tool(
        description="Get deployment details including replica status, strategy, and "
        "conditions. Use this to check deployment health and recent rollouts."
    )
    def describe_deployment(
        name: str,
        namespace: str = "default",
    ) -> dict[str, Any]:
        """Get deployment details."""
        return describe_deployment_impl(context, name, namespace)

    @server.tool(
        description="Get recent ReplicaSet history for a deployment. Useful for tracking "
        "rollout history and identifying when issues started."
    )
    def list_replicasets(
        namespace: str = "default",
        deployment_name: str | None = None,
    ) -> dict[str, Any]:
        """List ReplicaSets, optionally filtered by deployment."""
        return list_replicasets_impl(context, namespace, deployment_name)

    @server.tool(
        description="Get container logs from a pod. Essential for debugging application "
        "errors and crashes. Can get logs from previous container instance after restarts."
    )
    def get_pod_logs(
        name: str,
        namespace: str = "default",
        container: str | None = None,
        previous: bool = False,
        tail_lines: int = 100,
    ) -> dict[str, Any]:
        """Get logs from a pod container."""
        return get_pod_logs_impl(context, name, namespace, container, previous, tail_lines)

    @server.tool(
        description="Get node information and conditions. Use this to check if node "
        "issues (memory pressure, disk pressure) are causing pod problems."
    )
    def describe_node(name: str) -> dict[str, Any]:
        """Get node details."""
        return describe_node_impl(context, name)

    return server

"""ECS MCP server — thin wrapper over shared investigation impls."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from aws_incident_copilot.demo.fixtures import DemoDataProvider  # noqa: TC001
from aws_incident_copilot.tools.context import InvestigationContext
from aws_incident_copilot.tools.ecs import (
    describe_cluster_impl,
    describe_service_impl,
    describe_stopped_tasks_impl,
    describe_task_definition_impl,
    list_tasks_impl,
)


def create_ecs_server(
    demo_mode: bool = True,
    demo_provider: DemoDataProvider | None = None,
    ctx: InvestigationContext | None = None,
) -> MCPServer:
    """Create an ECS MCP server using the shared tool implementations."""
    server = MCPServer(
        name="ecs-tools",
        title="ECS Investigation Tools",
        description="Tools for investigating ECS services, tasks, and containers",
        version="1.0.0",
    )
    context = ctx or InvestigationContext(demo_mode=demo_mode, demo_provider=demo_provider)

    @server.tool(
        description="Describe an ECS service including deployment status, task counts, "
        "and recent events. Use this to understand service health."
    )
    def describe_service(cluster: str, service: str) -> dict[str, Any]:
        """Describe an ECS service."""
        return describe_service_impl(context, cluster, service)

    @server.tool(
        description="List and describe ECS tasks in a service. Shows task status, "
        "container health, and stopped reasons."
    )
    def list_tasks(
        cluster: str,
        service: str | None = None,
        status: str = "RUNNING",
    ) -> dict[str, Any]:
        """List ECS tasks."""
        return list_tasks_impl(context, cluster, service, status)

    @server.tool(
        description="Get stopped task details with exit codes and stop reasons. "
        "Essential for debugging OOM kills and task failures."
    )
    def describe_stopped_tasks(
        cluster: str,
        service: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get details of recently stopped tasks."""
        return describe_stopped_tasks_impl(context, cluster, service, limit)

    @server.tool(
        description="Get task definition details including container definitions, "
        "resource limits, and environment variables."
    )
    def describe_task_definition(task_definition: str) -> dict[str, Any]:
        """Get task definition details."""
        return describe_task_definition_impl(context, task_definition)

    @server.tool(
        description="Describe an ECS cluster including capacity provider status "
        "and registered container instances."
    )
    def describe_cluster(cluster: str) -> dict[str, Any]:
        """Get ECS cluster details."""
        return describe_cluster_impl(context, cluster)

    return server

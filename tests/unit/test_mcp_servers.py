"""Tests for MCP server tools via public APIs (no private _tool_manager)."""

import asyncio

import pytest

from aws_incident_copilot.mcp_servers import (
    create_cloudwatch_server,
    create_ecs_server,
    create_kubernetes_server,
)
from aws_incident_copilot.tools.cloudwatch import describe_alarms_impl, query_logs_impl
from aws_incident_copilot.tools.context import InvestigationContext
from aws_incident_copilot.tools.ecs import describe_service_impl, describe_stopped_tasks_impl
from aws_incident_copilot.tools.kubernetes import (
    describe_pod_impl,
    get_events_impl,
    get_pod_logs_impl,
)


def _tool_names(server) -> list[str]:
    tools = asyncio.run(server.list_tools())
    return [t.name for t in tools]


class TestCloudWatchServer:
    """Tests for CloudWatch MCP server."""

    @pytest.fixture
    def server(self, demo_provider_crashloop):
        return create_cloudwatch_server(demo_mode=True, demo_provider=demo_provider_crashloop)

    def test_server_creation(self, server):
        assert server.name == "cloudwatch-tools"
        assert server.version == "1.0.0"

    def test_server_has_tools(self, server):
        tool_names = _tool_names(server)
        assert "query_logs" in tool_names
        assert "get_metrics" in tool_names
        assert "describe_alarms" in tool_names
        assert "get_log_events" in tool_names
        assert "list_log_streams" in tool_names

    def test_query_logs_tool(self, demo_provider_crashloop):
        ctx = InvestigationContext(demo_mode=True, demo_provider=demo_provider_crashloop)
        result = query_logs_impl(
            ctx, log_group="/eks/production", query="fields @timestamp, @message"
        )
        assert "status" in result
        assert "results" in result

    def test_describe_alarms_tool(self, demo_provider_crashloop):
        ctx = InvestigationContext(demo_mode=True, demo_provider=demo_provider_crashloop)
        result = describe_alarms_impl(ctx, state="ALARM")
        assert "alarms" in result

    def test_mcp_call_tool(self, server):
        result = asyncio.run(server.call_tool("describe_alarms", {"state": "ALARM"}))
        assert result is not None
        assert asyncio.run(server.call_tool("query_logs", {"log_group": "/eks/production"}))
        assert asyncio.run(
            server.call_tool(
                "get_metrics", {"namespace": "AWS/ECS", "metric_name": "CPUUtilization"}
            )
        )
        assert asyncio.run(
            server.call_tool("get_log_events", {"log_group": "/eks/production", "log_stream": "a"})
        )
        assert asyncio.run(server.call_tool("list_log_streams", {"log_group": "/eks/production"}))


class TestKubernetesServer:
    """Tests for Kubernetes MCP server."""

    @pytest.fixture
    def server(self, demo_provider_crashloop):
        return create_kubernetes_server(demo_mode=True, demo_provider=demo_provider_crashloop)

    def test_server_creation(self, server):
        assert server.name == "kubernetes-tools"
        assert server.version == "1.0.0"

    def test_server_has_tools(self, server):
        tool_names = _tool_names(server)
        assert "describe_pod" in tool_names
        assert "get_events" in tool_names
        assert "list_pods" in tool_names
        assert "describe_deployment" in tool_names
        assert "get_pod_logs" in tool_names
        assert "describe_node" in tool_names

    def test_describe_pod_tool(self, demo_provider_crashloop):
        ctx = InvestigationContext(demo_mode=True, demo_provider=demo_provider_crashloop)
        result = describe_pod_impl(
            ctx,
            name="payment-service-7d4f8b9c5d-x2k9m",
            namespace="production",
        )
        assert "name" in result
        assert "container_statuses" in result

    def test_get_events_tool(self, demo_provider_crashloop):
        ctx = InvestigationContext(demo_mode=True, demo_provider=demo_provider_crashloop)
        result = get_events_impl(
            ctx,
            namespace="production",
            resource_name="payment-service-7d4f8b9c5d-x2k9m",
        )
        assert "events" in result

    def test_get_pod_logs_tool(self, demo_provider_crashloop):
        ctx = InvestigationContext(demo_mode=True, demo_provider=demo_provider_crashloop)
        result = get_pod_logs_impl(
            ctx,
            name="payment-service-7d4f8b9c5d-x2k9m",
            namespace="production",
            previous=True,
        )
        assert "logs" in result

    def test_mcp_call_tool(self, server):
        result = asyncio.run(
            server.call_tool(
                "describe_pod",
                {"name": "payment-service-7d4f8b9c5d-x2k9m", "namespace": "production"},
            )
        )
        assert result is not None
        assert asyncio.run(
            server.call_tool(
                "get_events",
                {"namespace": "production", "resource_name": "payment-service-7d4f8b9c5d-x2k9m"},
            )
        )
        assert asyncio.run(server.call_tool("list_pods", {"namespace": "production"}))
        assert asyncio.run(
            server.call_tool(
                "describe_deployment",
                {"name": "payment-service", "namespace": "production"},
            )
        )
        assert asyncio.run(server.call_tool("list_replicasets", {"namespace": "production"}))
        assert asyncio.run(
            server.call_tool(
                "get_pod_logs",
                {"name": "payment-service-7d4f8b9c5d-x2k9m", "namespace": "production"},
            )
        )
        assert asyncio.run(
            server.call_tool(
                "describe_node",
                {"name": "ip-10-0-1-45.us-west-2.compute.internal"},
            )
        )


class TestECSServer:
    """Tests for ECS MCP server."""

    @pytest.fixture
    def server(self, demo_provider_oom):
        return create_ecs_server(demo_mode=True, demo_provider=demo_provider_oom)

    def test_server_creation(self, server):
        assert server.name == "ecs-tools"
        assert server.version == "1.0.0"

    def test_server_has_tools(self, server):
        tool_names = _tool_names(server)
        assert "describe_service" in tool_names
        assert "list_tasks" in tool_names
        assert "describe_stopped_tasks" in tool_names
        assert "describe_task_definition" in tool_names
        assert "describe_cluster" in tool_names

    def test_describe_service_tool(self, demo_provider_oom):
        ctx = InvestigationContext(demo_mode=True, demo_provider=demo_provider_oom)
        result = describe_service_impl(ctx, cluster="production-cluster", service="order-processor")
        assert result["service_name"] == "order-processor"

    def test_describe_stopped_tasks_tool(self, demo_provider_oom):
        ctx = InvestigationContext(demo_mode=True, demo_provider=demo_provider_oom)
        result = describe_stopped_tasks_impl(
            ctx,
            cluster="production-cluster",
            service="order-processor",
        )
        assert result["stopped_tasks"][0]["containers"][0]["exit_code"] == 137

    def test_mcp_call_tool(self, server):
        result = asyncio.run(
            server.call_tool(
                "describe_service",
                {"cluster": "production-cluster", "service": "order-processor"},
            )
        )
        assert result is not None
        assert asyncio.run(
            server.call_tool(
                "list_tasks", {"cluster": "production-cluster", "service": "order-processor"}
            )
        )
        assert asyncio.run(
            server.call_tool(
                "describe_stopped_tasks",
                {"cluster": "production-cluster", "service": "order-processor"},
            )
        )
        assert asyncio.run(
            server.call_tool("describe_task_definition", {"task_definition": "order-processor:42"})
        )
        assert asyncio.run(server.call_tool("describe_cluster", {"cluster": "production-cluster"}))

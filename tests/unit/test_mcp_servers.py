"""Tests for MCP server tools."""

import pytest

from aws_incident_copilot.mcp_servers import (
    create_cloudwatch_server,
    create_ecs_server,
    create_kubernetes_server,
)


class TestCloudWatchServer:
    """Tests for CloudWatch MCP server."""

    @pytest.fixture
    def server(self, demo_provider_crashloop):
        """Create CloudWatch server in demo mode."""
        return create_cloudwatch_server(
            demo_mode=True,
            demo_provider=demo_provider_crashloop,
        )

    def test_server_creation(self, server):
        """Test server is created successfully."""
        assert server.name == "cloudwatch-tools"
        assert server.version == "1.0.0"

    def test_server_has_tools(self, server):
        """Test server has expected tools."""
        tool_names = list(server._tool_manager._tools.keys())

        assert "query_logs" in tool_names
        assert "get_metrics" in tool_names
        assert "describe_alarms" in tool_names
        assert "get_log_events" in tool_names
        assert "list_log_streams" in tool_names

    def test_query_logs_tool(self, server):
        """Test query_logs tool returns data."""
        tool = server._tool_manager._tools["query_logs"]
        result = tool.fn(
            log_group="/eks/production",
            query="fields @timestamp, @message",
        )

        assert "status" in result
        assert "results" in result

    def test_describe_alarms_tool(self, server):
        """Test describe_alarms tool returns data."""
        tool = server._tool_manager._tools["describe_alarms"]
        result = tool.fn(state="ALARM")

        assert "alarms" in result


class TestKubernetesServer:
    """Tests for Kubernetes MCP server."""

    @pytest.fixture
    def server(self, demo_provider_crashloop):
        """Create Kubernetes server in demo mode."""
        return create_kubernetes_server(
            demo_mode=True,
            demo_provider=demo_provider_crashloop,
        )

    def test_server_creation(self, server):
        """Test server is created successfully."""
        assert server.name == "kubernetes-tools"
        assert server.version == "1.0.0"

    def test_server_has_tools(self, server):
        """Test server has expected tools."""
        tool_names = list(server._tool_manager._tools.keys())

        assert "describe_pod" in tool_names
        assert "get_events" in tool_names
        assert "list_pods" in tool_names
        assert "describe_deployment" in tool_names
        assert "get_pod_logs" in tool_names
        assert "describe_node" in tool_names

    def test_describe_pod_tool(self, server):
        """Test describe_pod tool returns data."""
        tool = server._tool_manager._tools["describe_pod"]
        result = tool.fn(
            name="payment-service-7d4f8b9c5d-x2k9m",
            namespace="production",
        )

        assert "name" in result
        assert "container_statuses" in result

    def test_get_events_tool(self, server):
        """Test get_events tool returns data."""
        tool = server._tool_manager._tools["get_events"]
        result = tool.fn(
            namespace="production",
            resource_name="payment-service-7d4f8b9c5d-x2k9m",
        )

        assert "events" in result

    def test_get_pod_logs_tool(self, server):
        """Test get_pod_logs tool returns data."""
        tool = server._tool_manager._tools["get_pod_logs"]
        result = tool.fn(
            name="payment-service-7d4f8b9c5d-x2k9m",
            namespace="production",
            previous=True,
        )

        assert "logs" in result


class TestECSServer:
    """Tests for ECS MCP server."""

    @pytest.fixture
    def server(self, demo_provider_oom):
        """Create ECS server in demo mode."""
        return create_ecs_server(
            demo_mode=True,
            demo_provider=demo_provider_oom,
        )

    def test_server_creation(self, server):
        """Test server is created successfully."""
        assert server.name == "ecs-tools"
        assert server.version == "1.0.0"

    def test_server_has_tools(self, server):
        """Test server has expected tools."""
        tool_names = list(server._tool_manager._tools.keys())

        assert "describe_service" in tool_names
        assert "list_tasks" in tool_names
        assert "describe_stopped_tasks" in tool_names
        assert "describe_task_definition" in tool_names
        assert "describe_cluster" in tool_names

    def test_describe_service_tool(self, server):
        """Test describe_service tool returns data."""
        tool = server._tool_manager._tools["describe_service"]
        result = tool.fn(
            cluster="production-cluster",
            service="order-processor",
        )

        assert "service_name" in result
        assert result["service_name"] == "order-processor"

    def test_describe_stopped_tasks_tool(self, server):
        """Test describe_stopped_tasks tool returns data."""
        tool = server._tool_manager._tools["describe_stopped_tasks"]
        result = tool.fn(
            cluster="production-cluster",
            service="order-processor",
        )

        assert "stopped_tasks" in result
        assert len(result["stopped_tasks"]) > 0
        assert result["stopped_tasks"][0]["containers"][0]["exit_code"] == 137

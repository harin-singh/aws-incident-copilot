"""CloudWatch MCP server — thin wrapper over shared investigation impls."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from aws_incident_copilot.demo.fixtures import DemoDataProvider  # noqa: TC001
from aws_incident_copilot.tools.cloudwatch import (
    describe_alarms_impl,
    get_log_events_impl,
    get_metrics_impl,
    list_log_streams_impl,
    query_logs_impl,
)
from aws_incident_copilot.tools.context import InvestigationContext


def create_cloudwatch_server(
    demo_mode: bool = True,
    demo_provider: DemoDataProvider | None = None,
    ctx: InvestigationContext | None = None,
) -> MCPServer:
    """Create a CloudWatch MCP server using the shared tool implementations."""
    server = MCPServer(
        name="cloudwatch-tools",
        title="CloudWatch Investigation Tools",
        description="Tools for querying CloudWatch Logs and Metrics during incident investigation",
        version="1.0.0",
    )
    context = ctx or InvestigationContext(demo_mode=demo_mode, demo_provider=demo_provider)

    @server.tool(
        description="Query CloudWatch Logs using Logs Insights. Use this to search for errors, "
        "exceptions, and relevant log entries during an incident window."
    )
    def query_logs(
        log_group: str,
        query: str = "fields @timestamp, @message | sort @timestamp desc | limit 100",
        start_time: str | None = None,
        end_time: str | None = None,
        filter_pattern: str | None = None,
    ) -> dict[str, Any]:
        """Query CloudWatch Logs using Logs Insights."""
        return query_logs_impl(context, log_group, query, start_time, end_time, filter_pattern)

    @server.tool(
        description="Get CloudWatch metric data points. Use this to analyze CPU, memory, "
        "network, or custom metrics during an incident."
    )
    def get_metrics(
        namespace: str,
        metric_name: str,
        dimensions: dict[str, str] | None = None,
        statistic: str = "Average",
        period: int = 300,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Get CloudWatch metric data."""
        return get_metrics_impl(
            context, namespace, metric_name, dimensions, statistic, period, start_time, end_time
        )

    @server.tool(
        description="List and describe CloudWatch alarms. Use this to check alarm states "
        "and thresholds related to an incident."
    )
    def describe_alarms(
        alarm_name: str | None = None,
        state: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Describe CloudWatch alarms."""
        return describe_alarms_impl(context, alarm_name, state, namespace)

    @server.tool(
        description="Get recent log events from a log stream. Useful for getting raw "
        "log entries without running a Logs Insights query."
    )
    def get_log_events(
        log_group: str,
        log_stream: str,
        limit: int = 50,
        start_time: str | None = None,
    ) -> dict[str, Any]:
        """Get log events from a specific log stream."""
        return get_log_events_impl(context, log_group, log_stream, limit, start_time)

    @server.tool(
        description="List log streams in a log group. Use this to find the relevant "
        "log streams for a specific time window or pattern."
    )
    def list_log_streams(
        log_group: str,
        prefix: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List log streams in a log group."""
        return list_log_streams_impl(context, log_group, prefix, limit)

    return server

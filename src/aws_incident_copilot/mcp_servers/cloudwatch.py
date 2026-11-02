"""CloudWatch MCP Server for logs and metrics investigation.

This MCP server provides tools for querying CloudWatch Logs and Metrics
to investigate AWS incidents. In demo mode, it returns fixture data.
In live mode, it queries actual AWS CloudWatch APIs.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from aws_incident_copilot.demo.fixtures import DemoDataProvider


class LogQueryParams(BaseModel):
    """Parameters for CloudWatch Logs queries."""

    log_group: str = Field(description="CloudWatch Log Group name or ARN")
    query: str = Field(
        default="fields @timestamp, @message | sort @timestamp desc | limit 100",
        description="CloudWatch Logs Insights query",
    )
    start_time: str | None = Field(
        default=None, description="Start time (ISO format). Defaults to 1 hour ago."
    )
    end_time: str | None = Field(
        default=None, description="End time (ISO format). Defaults to now."
    )
    filter_pattern: str | None = Field(default=None, description="Filter pattern for log events")


class MetricQueryParams(BaseModel):
    """Parameters for CloudWatch Metrics queries."""

    namespace: str = Field(description="CloudWatch metric namespace (e.g., AWS/ECS)")
    metric_name: str = Field(description="Metric name (e.g., CPUUtilization)")
    dimensions: dict[str, str] = Field(default_factory=dict, description="Metric dimensions")
    statistic: str = Field(default="Average", description="Statistic type")
    period: int = Field(default=300, description="Period in seconds")
    start_time: str | None = Field(default=None, description="Start time (ISO format)")
    end_time: str | None = Field(default=None, description="End time (ISO format)")


class AlarmQueryParams(BaseModel):
    """Parameters for CloudWatch Alarms queries."""

    alarm_name: str | None = Field(default=None, description="Specific alarm name")
    state: str | None = Field(
        default=None, description="Filter by state (OK, ALARM, INSUFFICIENT_DATA)"
    )
    namespace: str | None = Field(default=None, description="Filter by metric namespace")


def create_cloudwatch_server(
    demo_mode: bool = True,
    demo_provider: DemoDataProvider | None = None,
) -> MCPServer:
    """Create a CloudWatch MCP server.

    Args:
        demo_mode: If True, return fixture data instead of querying AWS.
        demo_provider: Provider for demo fixture data.

    Returns:
        Configured MCPServer instance.
    """
    server = MCPServer(
        name="cloudwatch-tools",
        title="CloudWatch Investigation Tools",
        description="Tools for querying CloudWatch Logs and Metrics during incident investigation",
        version="1.0.0",
    )

    provider = demo_provider or DemoDataProvider()

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
        if demo_mode:
            return provider.get_cloudwatch_logs(
                log_group=log_group,
                query=query,
                filter_pattern=filter_pattern,
            )

        # Live mode implementation
        import boto3

        client = boto3.client("logs")

        now = datetime.now(UTC)
        start = (
            datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if start_time
            else now - timedelta(hours=1)
        )
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00")) if end_time else now

        response = client.start_query(
            logGroupName=log_group,
            startTime=int(start.timestamp()),
            endTime=int(end.timestamp()),
            queryString=query,
        )

        query_id = response["queryId"]

        # Poll for results
        import time

        while True:
            result = client.get_query_results(queryId=query_id)
            if result["status"] in ("Complete", "Failed", "Cancelled"):
                break
            time.sleep(0.5)

        return {
            "status": result["status"],
            "results": result.get("results", []),
            "statistics": result.get("statistics", {}),
        }

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
        if demo_mode:
            return provider.get_cloudwatch_metrics(
                namespace=namespace,
                metric_name=metric_name,
                dimensions=dimensions or {},
            )

        # Live mode implementation
        import boto3

        client = boto3.client("cloudwatch")

        now = datetime.now(UTC)
        start = (
            datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if start_time
            else now - timedelta(hours=1)
        )
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00")) if end_time else now

        dim_list = [{"Name": k, "Value": v} for k, v in (dimensions or {}).items()]

        response = client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dim_list,
            StartTime=start,
            EndTime=end,
            Period=period,
            Statistics=[statistic],
        )

        datapoints = [
            {
                "timestamp": dp["Timestamp"].isoformat(),
                "value": dp.get(statistic),
                "unit": dp.get("Unit"),
            }
            for dp in sorted(response.get("Datapoints", []), key=lambda x: x["Timestamp"])
        ]

        return {
            "namespace": namespace,
            "metric_name": metric_name,
            "datapoints": datapoints,
        }

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
        if demo_mode:
            return provider.get_cloudwatch_alarms(
                alarm_name=alarm_name,
                state=state,
            )

        # Live mode implementation
        import boto3

        client = boto3.client("cloudwatch")

        params: dict[str, Any] = {}
        if alarm_name:
            params["AlarmNames"] = [alarm_name]
        if state:
            params["StateValue"] = state

        response = client.describe_alarms(**params)

        alarms = []
        for alarm in response.get("MetricAlarms", []):
            if namespace and alarm.get("Namespace") != namespace:
                continue
            alarms.append(
                {
                    "name": alarm["AlarmName"],
                    "state": alarm["StateValue"],
                    "reason": alarm.get("StateReason", ""),
                    "metric_name": alarm.get("MetricName"),
                    "namespace": alarm.get("Namespace"),
                    "threshold": alarm.get("Threshold"),
                    "comparison": alarm.get("ComparisonOperator"),
                    "evaluation_periods": alarm.get("EvaluationPeriods"),
                    "updated": alarm.get("StateUpdatedTimestamp", "").isoformat()
                    if alarm.get("StateUpdatedTimestamp")
                    else None,
                }
            )

        return {"alarms": alarms}

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
        if demo_mode:
            return provider.get_log_events(
                log_group=log_group,
                log_stream=log_stream,
                limit=limit,
            )

        # Live mode implementation
        import boto3

        client = boto3.client("logs")

        params: dict[str, Any] = {
            "logGroupName": log_group,
            "logStreamName": log_stream,
            "limit": limit,
            "startFromHead": False,
        }

        if start_time:
            params["startTime"] = int(
                datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp() * 1000
            )

        response = client.get_log_events(**params)

        events = [
            {
                "timestamp": datetime.fromtimestamp(e["timestamp"] / 1000, tz=UTC).isoformat(),
                "message": e["message"],
            }
            for e in response.get("events", [])
        ]

        return {"events": events}

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
        if demo_mode:
            return provider.list_log_streams(
                log_group=log_group,
                prefix=prefix,
            )

        # Live mode implementation
        import boto3

        client = boto3.client("logs")

        params: dict[str, Any] = {
            "logGroupName": log_group,
            "orderBy": "LastEventTime",
            "descending": True,
            "limit": limit,
        }

        if prefix:
            params["logStreamNamePrefix"] = prefix

        response = client.describe_log_streams(**params)

        streams = [
            {
                "name": s["logStreamName"],
                "last_event": datetime.fromtimestamp(
                    s.get("lastEventTimestamp", 0) / 1000, tz=UTC
                ).isoformat()
                if s.get("lastEventTimestamp")
                else None,
                "stored_bytes": s.get("storedBytes", 0),
            }
            for s in response.get("logStreams", [])
        ]

        return {"log_streams": streams}

    return server

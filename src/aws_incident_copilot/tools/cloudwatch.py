"""CloudWatch investigation tools (Strands @tool wrappers + shared impl)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from strands import tool

from aws_incident_copilot.tools._time import default_window, parse_iso
from aws_incident_copilot.tools.context import InvestigationContext  # noqa: TC001


def query_logs_impl(
    ctx: InvestigationContext,
    log_group: str,
    query: str = "fields @timestamp, @message | sort @timestamp desc | limit 100",
    start_time: str | None = None,
    end_time: str | None = None,
    filter_pattern: str | None = None,
) -> dict[str, Any]:
    """Query CloudWatch Logs using Logs Insights."""
    if ctx.demo_mode:
        return ctx.provider().get_cloudwatch_logs(
            log_group=log_group,
            query=query,
            filter_pattern=filter_pattern,
        )

    client = ctx.client("logs")
    start, end = default_window(start_time, end_time)

    response = client.start_query(
        logGroupName=log_group,
        startTime=int(start.timestamp()),
        endTime=int(end.timestamp()),
        queryString=query,
    )
    query_id = response["queryId"]

    result: dict[str, Any] = {"status": "Running"}
    for _ in range(40):
        result = client.get_query_results(queryId=query_id)
        if result["status"] in ("Complete", "Failed", "Cancelled"):
            break
        time.sleep(0.25)

    return {
        "status": result["status"],
        "results": result.get("results", []),
        "statistics": result.get("statistics", {}),
    }


def get_metrics_impl(
    ctx: InvestigationContext,
    namespace: str,
    metric_name: str,
    dimensions: dict[str, str] | None = None,
    statistic: str = "Average",
    period: int = 300,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Get CloudWatch metric data."""
    if ctx.demo_mode:
        return ctx.provider().get_cloudwatch_metrics(
            namespace=namespace,
            metric_name=metric_name,
            dimensions=dimensions or {},
        )

    client = ctx.client("cloudwatch")
    start, end = default_window(start_time, end_time)
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


def describe_alarms_impl(
    ctx: InvestigationContext,
    alarm_name: str | None = None,
    state: str | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """Describe CloudWatch alarms."""
    if ctx.demo_mode:
        return ctx.provider().get_cloudwatch_alarms(alarm_name=alarm_name, state=state)

    client = ctx.client("cloudwatch")
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
        updated = alarm.get("StateUpdatedTimestamp")
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
                "updated": updated.isoformat() if updated else None,
            }
        )

    return {"alarms": alarms}


def get_log_events_impl(
    ctx: InvestigationContext,
    log_group: str,
    log_stream: str,
    limit: int = 50,
    start_time: str | None = None,
) -> dict[str, Any]:
    """Get log events from a specific log stream."""
    if ctx.demo_mode:
        return ctx.provider().get_log_events(
            log_group=log_group,
            log_stream=log_stream,
            limit=limit,
        )

    client = ctx.client("logs")
    params: dict[str, Any] = {
        "logGroupName": log_group,
        "logStreamName": log_stream,
        "limit": limit,
        "startFromHead": False,
    }
    if start_time:
        params["startTime"] = int(parse_iso(start_time).timestamp() * 1000)

    response = client.get_log_events(**params)
    events = [
        {
            "timestamp": datetime.fromtimestamp(e["timestamp"] / 1000, tz=UTC).isoformat(),
            "message": e["message"],
        }
        for e in response.get("events", [])
    ]
    return {"events": events}


def list_log_streams_impl(
    ctx: InvestigationContext,
    log_group: str,
    prefix: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """List log streams in a log group."""
    if ctx.demo_mode:
        return ctx.provider().list_log_streams(log_group=log_group, prefix=prefix)

    client = ctx.client("logs")
    params: dict[str, Any] = {
        "logGroupName": log_group,
        "orderBy": "LastEventTime",
        "descending": True,
        "limit": limit,
    }
    if prefix:
        params["logStreamNamePrefix"] = prefix

    response = client.describe_log_streams(**params)
    streams = []
    for stream in response.get("logStreams", []):
        last_event = stream.get("lastEventTimestamp")
        streams.append(
            {
                "name": stream["logStreamName"],
                "last_event": (
                    datetime.fromtimestamp(last_event / 1000, tz=UTC).isoformat()
                    if last_event
                    else None
                ),
                "stored_bytes": stream.get("storedBytes", 0),
            }
        )
    return {"log_streams": streams}


def create_cloudwatch_tools(ctx: InvestigationContext) -> list[Any]:
    """Create Strands-decorated CloudWatch investigation tools."""

    @tool(
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
        return query_logs_impl(ctx, log_group, query, start_time, end_time, filter_pattern)

    @tool(
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
            ctx, namespace, metric_name, dimensions, statistic, period, start_time, end_time
        )

    @tool(
        description="List and describe CloudWatch alarms. Use this to check alarm states "
        "and thresholds related to an incident."
    )
    def describe_alarms(
        alarm_name: str | None = None,
        state: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Describe CloudWatch alarms."""
        return describe_alarms_impl(ctx, alarm_name, state, namespace)

    @tool(
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
        return get_log_events_impl(ctx, log_group, log_stream, limit, start_time)

    @tool(
        description="List log streams in a log group. Use this to find the relevant "
        "log streams for a specific time window or pattern."
    )
    def list_log_streams(
        log_group: str,
        prefix: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List log streams in a log group."""
        return list_log_streams_impl(ctx, log_group, prefix, limit)

    return [query_logs, get_metrics, describe_alarms, get_log_events, list_log_streams]

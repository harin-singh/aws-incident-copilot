"""Live-path tests for investigation tools using moto and a fake k8s API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import boto3
import pytest
from moto import mock_aws

from aws_incident_copilot.tools.cloudwatch import (
    describe_alarms_impl,
    get_log_events_impl,
    get_metrics_impl,
    list_log_streams_impl,
    query_logs_impl,
)
from aws_incident_copilot.tools.context import InvestigationContext
from aws_incident_copilot.tools.ecs import (
    describe_cluster_impl,
    describe_service_impl,
    describe_stopped_tasks_impl,
    describe_task_definition_impl,
    list_tasks_impl,
)
from aws_incident_copilot.tools.kubernetes import (
    describe_deployment_impl,
    describe_node_impl,
    describe_pod_impl,
    get_events_impl,
    get_pod_logs_impl,
    list_pods_impl,
    list_replicasets_impl,
)
from tests.fakes.aws import create_fargate_service
from tests.fakes.k8s import FakeAppsV1Api, FakeCoreV1Api


@pytest.fixture
def aws_region() -> str:
    return "us-west-2"


@mock_aws
def test_cloudwatch_alarms_and_metrics_live(aws_region: str) -> None:
    cw = boto3.client("cloudwatch", region_name=aws_region)
    cw.put_metric_data(
        Namespace="AWS/ECS",
        MetricData=[
            {
                "MetricName": "CPUUtilization",
                "Timestamp": datetime.now(UTC) - timedelta(minutes=5),
                "Value": 90.0,
                "Unit": "Percent",
                "Dimensions": [{"Name": "ServiceName", "Value": "api"}],
            }
        ],
    )
    cw.put_metric_alarm(
        AlarmName="api-cpu-high",
        ComparisonOperator="GreaterThanThreshold",
        EvaluationPeriods=1,
        MetricName="CPUUtilization",
        Namespace="AWS/ECS",
        Period=60,
        Statistic="Average",
        Threshold=80.0,
        ActionsEnabled=False,
    )
    # Force ALARM so describe_alarms(state=ALARM) is non-empty.
    cw.set_alarm_state(
        AlarmName="api-cpu-high",
        StateValue="ALARM",
        StateReason="test",
    )

    ctx = InvestigationContext(demo_mode=False, cloudwatch_client=cw, region=aws_region)
    alarms = describe_alarms_impl(ctx, state="ALARM")
    assert any(a["name"] == "api-cpu-high" for a in alarms["alarms"])

    metrics = get_metrics_impl(
        ctx,
        namespace="AWS/ECS",
        metric_name="CPUUtilization",
        dimensions={"ServiceName": "api"},
        period=60,
    )
    assert metrics["metric_name"] == "CPUUtilization"
    assert len(metrics["datapoints"]) >= 1


@mock_aws
def test_cloudwatch_logs_live(aws_region: str) -> None:
    logs = boto3.client("logs", region_name=aws_region)
    logs.create_log_group(logGroupName="/ecs/api")
    logs.create_log_stream(logGroupName="/ecs/api", logStreamName="task/1")
    ts = int(datetime.now(UTC).timestamp() * 1000)
    logs.put_log_events(
        logGroupName="/ecs/api",
        logStreamName="task/1",
        logEvents=[{"timestamp": ts, "message": "ERROR Too many connections"}],
    )

    ctx = InvestigationContext(demo_mode=False, logs_client=logs, region=aws_region)
    streams = list_log_streams_impl(ctx, log_group="/ecs/api")
    assert streams["log_streams"][0]["name"] == "task/1"

    events = get_log_events_impl(ctx, log_group="/ecs/api", log_stream="task/1")
    assert "Too many connections" in events["events"][0]["message"]

    query = query_logs_impl(
        ctx,
        log_group="/ecs/api",
        query="fields @timestamp, @message",
    )
    assert query["status"] in {"Complete", "Failed", "Cancelled", "Running"}


@mock_aws
def test_ecs_live_tools(aws_region: str) -> None:
    ecs = create_fargate_service(aws_region)
    ctx = InvestigationContext(demo_mode=False, ecs_client=ecs, region=aws_region)
    cluster = describe_cluster_impl(ctx, "prod")
    assert cluster["cluster_name"] == "prod"

    service = describe_service_impl(ctx, "prod", "api")
    assert service["service_name"] == "api"

    td = describe_task_definition_impl(ctx, "api")
    assert td["family"] == "api"

    running = list_tasks_impl(ctx, "prod", "api", status="RUNNING")
    assert "tasks" in running

    stopped = describe_stopped_tasks_impl(ctx, "prod", "api")
    assert stopped["stopped_tasks"] == []


@mock_aws
def test_investigation_context_uses_injected_and_live_clients(aws_region: str) -> None:
    cw = boto3.client("cloudwatch", region_name=aws_region)
    ctx = InvestigationContext(demo_mode=False, cloudwatch_client=cw, region=aws_region)
    assert ctx.client("cloudwatch") is cw
    logs = ctx.client("logs")
    assert logs.meta.service_model.service_name == "logs"
    assert ctx.provider().scenario == "crashloop"


def test_kubernetes_live_tools_with_fake_api() -> None:
    core = FakeCoreV1Api()
    apps = FakeAppsV1Api()
    core.add_pod("web-1", "production", restart_count=3, previous_logs="FATAL boom")
    core.add_event("web-1", "production", "BackOff", "Back-off restarting")
    core.add_node("ip-10-0-1-1")
    apps.add_deployment("web", "production")

    ctx = InvestigationContext(demo_mode=False, k8s_core=core, k8s_apps=apps)
    pod = describe_pod_impl(ctx, "web-1", "production")
    assert pod["name"] == "web-1"
    assert pod["container_statuses"][0]["restart_count"] == 3

    events = get_events_impl(ctx, namespace="production", resource_name="web-1")
    assert events["events"][0]["reason"] == "BackOff"

    pods = list_pods_impl(ctx, namespace="production")
    assert pods["pods"][0]["name"] == "web-1"

    logs = get_pod_logs_impl(ctx, "web-1", "production", previous=True)
    assert "FATAL boom" in logs["logs"]

    dep = describe_deployment_impl(ctx, "web", "production")
    assert dep["name"] == "web"

    rs = list_replicasets_impl(ctx, namespace="production", deployment_name="web")
    assert len(rs["replicasets"]) == 2

    node = describe_node_impl(ctx, "ip-10-0-1-1")
    assert node["name"] == "ip-10-0-1-1"

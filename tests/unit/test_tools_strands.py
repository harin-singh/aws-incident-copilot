"""Tests that investigation tools register as Strands AgentTool instances."""

from strands.types.tools import AgentTool

from aws_incident_copilot.demo.fixtures import DemoDataProvider
from aws_incident_copilot.tools import InvestigationContext, collect_investigation_tools


def test_collect_investigation_tools_are_strands_tools() -> None:
    ctx = InvestigationContext(demo_mode=True, demo_provider=DemoDataProvider("crashloop"))
    tools = collect_investigation_tools(ctx)
    assert len(tools) == 17
    assert all(isinstance(t, AgentTool) for t in tools)
    names = {t.tool_name for t in tools}
    assert {
        "describe_pod",
        "get_pod_logs",
        "describe_service",
        "query_logs",
        "describe_alarms",
        "get_metrics",
    } <= names


def test_strands_tools_call_demo_backend() -> None:
    ctx = InvestigationContext(demo_mode=True, demo_provider=DemoDataProvider("crashloop"))
    tools = {t.tool_name: t for t in collect_investigation_tools(ctx)}
    result = tools["describe_pod"](
        name="payment-service-7d4f8b9c5d-x2k9m",
        namespace="production",
    )
    # DecoratedFunctionTool may wrap the dict; accept either form.
    payload = result if isinstance(result, dict) else getattr(result, "content", result)
    text = str(payload)
    assert "CrashLoopBackOff" in text or "payment-service" in text

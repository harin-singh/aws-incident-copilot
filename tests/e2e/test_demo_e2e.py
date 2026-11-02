"""End-to-end tests for demo mode."""

import pytest

from aws_incident_copilot.agents import ApprovalHandler, IncidentCopilot
from aws_incident_copilot.demo.fixtures import DemoDataProvider
from aws_incident_copilot.demo.model_stub import DemoModelProvider
from aws_incident_copilot.demo.scenarios import load_scenario
from aws_incident_copilot.mcp_servers import (
    create_cloudwatch_server,
    create_ecs_server,
    create_kubernetes_server,
)


class TestDemoModeE2E:
    """End-to-end tests for demo mode scenarios."""

    @pytest.fixture
    def setup_crashloop(self):
        """Set up crashloop scenario components."""
        scenario = load_scenario("crashloop")
        provider = DemoDataProvider(scenario="crashloop")

        return {
            "scenario": scenario,
            "provider": provider,
            "cw_server": create_cloudwatch_server(demo_mode=True, demo_provider=provider),
            "k8s_server": create_kubernetes_server(demo_mode=True, demo_provider=provider),
            "ecs_server": create_ecs_server(demo_mode=True, demo_provider=provider),
        }

    @pytest.fixture
    def setup_oom(self):
        """Set up OOM scenario components."""
        scenario = load_scenario("oom")
        provider = DemoDataProvider(scenario="oom")

        return {
            "scenario": scenario,
            "provider": provider,
            "cw_server": create_cloudwatch_server(demo_mode=True, demo_provider=provider),
            "k8s_server": create_kubernetes_server(demo_mode=True, demo_provider=provider),
            "ecs_server": create_ecs_server(demo_mode=True, demo_provider=provider),
        }

    def test_crashloop_scenario_runs(self, setup_crashloop):
        """Test that crashloop scenario runs without errors."""
        scenario = setup_crashloop["scenario"]

        copilot = IncidentCopilot(
            demo_mode=True,
            scenario="crashloop",
            approval_handler=ApprovalHandler(auto_approve=True),
            verbose=False,
        )

        tools = self._collect_tools(
            [
                setup_crashloop["cw_server"],
                setup_crashloop["k8s_server"],
                setup_crashloop["ecs_server"],
            ]
        )

        report = copilot.investigate(
            alert=scenario.alert,
            mcp_tools=tools,
        )

        assert report is not None
        assert report.status == "complete"
        assert report.investigation_end is not None
        assert report.summary is not None

    def test_oom_scenario_runs(self, setup_oom):
        """Test that OOM scenario runs without errors."""
        scenario = setup_oom["scenario"]

        copilot = IncidentCopilot(
            demo_mode=True,
            scenario="oom",
            approval_handler=ApprovalHandler(auto_approve=True),
            verbose=False,
        )

        tools = self._collect_tools(
            [
                setup_oom["cw_server"],
                setup_oom["k8s_server"],
                setup_oom["ecs_server"],
            ]
        )

        report = copilot.investigate(
            alert=scenario.alert,
            mcp_tools=tools,
        )

        assert report is not None
        assert report.status == "complete"

    async def test_model_stub_produces_responses(self):
        """Test that the model stub produces scripted responses."""
        model = DemoModelProvider(scenario="crashloop")

        responses = []
        async for event in model.stream(
            messages=[],
            tool_specs=[],
        ):
            responses.append(event)

        assert len(responses) > 0

        has_content = any("contentBlockStart" in r or "contentBlockDelta" in r for r in responses)
        assert has_content

        has_stop = any("messageStop" in r for r in responses)
        assert has_stop

    async def test_model_stub_uses_tools(self):
        """Test that the model stub requests tool use."""
        model = DemoModelProvider(scenario="crashloop")

        responses = []
        async for event in model.stream(
            messages=[],
            tool_specs=[],
        ):
            responses.append(event)

        tool_uses = [
            r
            for r in responses
            if "contentBlockStart" in r
            and "toolUse" in r.get("contentBlockStart", {}).get("start", {})
        ]

        assert len(tool_uses) > 0

    def test_all_scenarios_produce_output(self):
        """Test that all scenarios produce output."""
        for scenario_id in ["crashloop", "oom", "alb-5xx"]:
            scenario = load_scenario(scenario_id)
            provider = DemoDataProvider(scenario=scenario_id)

            copilot = IncidentCopilot(
                demo_mode=True,
                scenario=scenario_id,
                approval_handler=ApprovalHandler(auto_approve=True),
                verbose=False,
            )

            servers = [
                create_cloudwatch_server(demo_mode=True, demo_provider=provider),
                create_kubernetes_server(demo_mode=True, demo_provider=provider),
                create_ecs_server(demo_mode=True, demo_provider=provider),
            ]

            tools = self._collect_tools(servers)

            report = copilot.investigate(
                alert=scenario.alert,
                mcp_tools=tools,
            )

            assert report.status == "complete", f"Scenario {scenario_id} did not complete"

    def _collect_tools(self, servers):
        """Collect tools from MCP servers."""
        tools = []
        for server in servers:
            for tool_name in server._tool_manager._tools:
                tool_func = server._tool_manager._tools[tool_name]
                tools.append(tool_func.fn)
        return tools


class TestApprovalGatingE2E:
    """End-to-end tests for approval gating."""

    def test_remediation_blocked_without_approval(self):
        """Test that remediation is blocked when approval is denied."""
        from aws_incident_copilot.agents.approval import (
            ApprovalDecision,
            create_remediation_tools,
        )

        handler = ApprovalHandler(
            mode="callback",
            approval_callback=lambda a, d: ApprovalDecision.DENIED,
        )

        tools = create_remediation_tools(handler)
        restart_tool = tools[0]

        result = restart_tool(name="test-deploy", namespace="production")

        assert result["status"] == "not_executed"
        assert "denied" in result["reason"].lower()

    def test_remediation_allowed_with_approval(self):
        """Test that remediation proceeds with approval."""
        from aws_incident_copilot.agents.approval import create_remediation_tools

        handler = ApprovalHandler(auto_approve=True)

        tools = create_remediation_tools(handler)
        restart_tool = tools[0]

        result = restart_tool(name="test-deploy", namespace="production")

        assert result["status"] == "executed"
        assert result["approval"]["decision"] == "approved"

    def test_approval_history_tracked(self):
        """Test that approval decisions are tracked."""
        from aws_incident_copilot.agents.approval import create_remediation_tools

        handler = ApprovalHandler(auto_approve=True)
        tools = create_remediation_tools(handler)

        tools[0](name="deploy-1", namespace="prod")
        tools[1](name="deploy-2", namespace="prod")
        tools[2](cluster="cluster", service="svc", desired_count=5)

        history = handler.get_history()

        assert len(history) == 3
        assert all(h["decision"] == "approved" for h in history)

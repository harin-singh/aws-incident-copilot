"""End-to-end tests for demo mode."""

import subprocess
import sys

import pytest
from click.testing import CliRunner

from aws_incident_copilot.agents import ApprovalHandler, IncidentCopilot
from aws_incident_copilot.cli import main
from aws_incident_copilot.demo.model_stub import UNGROUNDED_MARKER, DemoModelProvider
from aws_incident_copilot.demo.scenarios import load_scenario


class TestDemoModeE2E:
    """End-to-end tests for demo mode scenarios."""

    def test_crashloop_scenario_runs(self):
        scenario = load_scenario("crashloop")
        copilot = IncidentCopilot(
            demo_mode=True,
            scenario="crashloop",
            approval_handler=ApprovalHandler(auto_approve=True),
            verbose=False,
        )
        report = copilot.investigate(alert=scenario.alert)
        assert report.status == "complete"
        assert report.summary is not None
        assert UNGROUNDED_MARKER not in report.summary
        assert "password authentication failed" in report.summary.lower()
        assert isinstance(copilot.model, DemoModelProvider)
        assert copilot.model.grounded is True

    def test_oom_scenario_runs(self):
        scenario = load_scenario("oom")
        copilot = IncidentCopilot(
            demo_mode=True,
            scenario="oom",
            approval_handler=ApprovalHandler(auto_approve=True),
            verbose=False,
        )
        report = copilot.investigate(alert=scenario.alert)
        assert report.status == "complete"
        assert UNGROUNDED_MARKER not in (report.summary or "")
        assert isinstance(copilot.model, DemoModelProvider)
        assert copilot.model.grounded is True

    async def test_model_stub_produces_responses(self):
        model = DemoModelProvider(scenario="crashloop")
        responses = [event async for event in model.stream(messages=[], tool_specs=[])]
        assert responses
        assert any("contentBlockStart" in r or "contentBlockDelta" in r for r in responses)
        assert any("messageStop" in r for r in responses)

    async def test_model_stub_uses_tools(self):
        model = DemoModelProvider(scenario="crashloop")
        responses = [event async for event in model.stream(messages=[], tool_specs=[])]
        tool_uses = [
            r
            for r in responses
            if "contentBlockStart" in r
            and "toolUse" in r.get("contentBlockStart", {}).get("start", {})
        ]
        assert tool_uses

    def test_all_scenarios_produce_grounded_output(self):
        for scenario_id in ["crashloop", "oom", "alb-5xx"]:
            scenario = load_scenario(scenario_id)
            copilot = IncidentCopilot(
                demo_mode=True,
                scenario=scenario_id,
                approval_handler=ApprovalHandler(auto_approve=True),
                verbose=False,
            )
            report = copilot.investigate(alert=scenario.alert)
            assert report.status == "complete", f"Scenario {scenario_id} did not complete"
            assert UNGROUNDED_MARKER not in (report.summary or ""), scenario_id
            assert "tool not found" not in (report.summary or "").lower()


class TestApprovalGatingE2E:
    """End-to-end tests for approval gating."""

    def test_remediation_blocked_without_approval(self):
        from aws_incident_copilot.agents.approval import (
            ApprovalDecision,
            create_remediation_tools,
        )

        handler = ApprovalHandler(
            mode="callback",
            approval_callback=lambda a, d: ApprovalDecision.DENIED,
        )
        tools = create_remediation_tools(handler)
        result = tools[0](name="test-deploy", namespace="production")
        assert result["status"] == "not_executed"
        assert "denied" in result["reason"].lower()

    def test_remediation_allowed_with_approval(self):
        from aws_incident_copilot.agents.approval import create_remediation_tools

        handler = ApprovalHandler(auto_approve=True)
        tools = create_remediation_tools(handler)
        result = tools[0](name="test-deploy", namespace="production")
        assert result["status"] == "simulated"
        assert result["backend"] == "demo"
        assert result["approval"]["decision"] == "approved"

    def test_approval_history_tracked(self):
        from aws_incident_copilot.agents.approval import create_remediation_tools

        handler = ApprovalHandler(auto_approve=True)
        tools = create_remediation_tools(handler)
        tools[0](name="deploy-1", namespace="prod")
        tools[1](name="deploy-2", namespace="prod")
        tools[2](cluster="cluster", service="svc", desired_count=5)
        history = handler.get_history()
        assert len(history) == 3
        assert all(h["decision"] == "approved" for h in history)


class TestCliDemoScenarios:
    """Run the real CLI for every scenario and fail on theater."""

    @pytest.mark.parametrize("scenario", ["crashloop", "oom", "alb-5xx"])
    def test_cli_demo_scenario(self, scenario: str) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["demo", "--scenario", scenario, "--auto-approve"])
        assert result.exit_code == 0, result.output
        combined = result.output.lower()
        assert "tool not found" not in combined
        assert "unrecognized tool" not in combined
        assert UNGROUNDED_MARKER.lower() not in combined
        assert "demo complete" in combined

    @pytest.mark.parametrize("scenario", ["crashloop", "oom", "alb-5xx"])
    def test_cli_module_subprocess(self, scenario: str) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "aws_incident_copilot.cli",
                "demo",
                "--scenario",
                scenario,
                "--auto-approve",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        output = f"{proc.stdout}\n{proc.stderr}"
        assert proc.returncode == 0, output
        lowered = output.lower()
        assert "tool not found" not in lowered
        assert "unrecognized tool" not in lowered
        assert UNGROUNDED_MARKER.lower() not in lowered
        assert "traceback" not in lowered

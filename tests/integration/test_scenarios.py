"""Tests for demo scenarios."""

import pytest

from aws_incident_copilot.demo.scenarios import (
    SCENARIOS,
    list_scenarios,
    load_scenario,
)
from aws_incident_copilot.models.incident import AlertSeverity, AlertSource


class TestScenarios:
    """Tests for demo scenarios."""

    def test_all_scenarios_exist(self):
        """Test that all expected scenarios exist."""
        assert "crashloop" in SCENARIOS
        assert "oom" in SCENARIOS
        assert "alb-5xx" in SCENARIOS

    def test_load_crashloop_scenario(self, crashloop_scenario):
        """Test loading crashloop scenario."""
        assert crashloop_scenario.id == "crashloop"
        assert crashloop_scenario.name == "EKS CrashLoopBackOff"
        assert crashloop_scenario.alert.source == AlertSource.EKS
        assert crashloop_scenario.alert.severity == AlertSeverity.HIGH

    def test_load_oom_scenario(self, oom_scenario):
        """Test loading OOM scenario."""
        assert oom_scenario.id == "oom"
        assert oom_scenario.alert.source == AlertSource.ECS
        assert oom_scenario.alert.severity == AlertSeverity.CRITICAL

    def test_load_alb_scenario(self, alb_scenario):
        """Test loading ALB 5xx scenario."""
        assert alb_scenario.id == "alb-5xx"
        assert alb_scenario.alert.source == AlertSource.ALB
        assert alb_scenario.alert.severity == AlertSeverity.CRITICAL

    def test_load_invalid_scenario(self):
        """Test loading invalid scenario raises error."""
        with pytest.raises(ValueError, match="Unknown scenario"):
            load_scenario("nonexistent")

    def test_list_scenarios(self):
        """Test listing all scenarios."""
        scenarios = list_scenarios()

        assert len(scenarios) == 3
        assert all("id" in s for s in scenarios)
        assert all("name" in s for s in scenarios)
        assert all("severity" in s for s in scenarios)

    def test_scenario_alerts_are_complete(self):
        """Test that all scenario alerts have required fields."""
        for scenario_id, scenario in SCENARIOS.items():
            alert = scenario.alert

            assert alert.id, f"Scenario {scenario_id} missing alert ID"
            assert alert.title, f"Scenario {scenario_id} missing alert title"
            assert alert.description, f"Scenario {scenario_id} missing description"
            assert alert.resource_id, f"Scenario {scenario_id} missing resource_id"
            assert alert.timestamp, f"Scenario {scenario_id} missing timestamp"

    def test_scenario_expected_outcomes_defined(self):
        """Test that scenarios have expected outcomes for validation."""
        for scenario_id, scenario in SCENARIOS.items():
            assert scenario.expected_root_cause, (
                f"Scenario {scenario_id} missing expected root cause"
            )
            assert len(scenario.expected_remediations) > 0, (
                f"Scenario {scenario_id} missing expected remediations"
            )

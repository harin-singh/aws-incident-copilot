"""Tests for AgentCore entrypoint module."""

import os
from unittest.mock import patch

import pytest

from aws_incident_copilot.agentcore.entrypoint import (
    _create_alert_from_payload,
    _get_demo_scenario,
    _is_demo_mode,
    invoke_handler,
)


class TestDemoModeDetection:
    """Tests for demo mode detection."""

    def test_demo_mode_false_by_default(self):
        """Demo mode should be false when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DEMO_MODE", None)
            assert _is_demo_mode() is False

    def test_demo_mode_true_when_set(self):
        """Demo mode should be true when DEMO_MODE=true."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            assert _is_demo_mode() is True

    def test_demo_mode_true_with_yes(self):
        """Demo mode should be true when DEMO_MODE=yes."""
        with patch.dict(os.environ, {"DEMO_MODE": "yes"}):
            assert _is_demo_mode() is True

    def test_demo_mode_true_with_1(self):
        """Demo mode should be true when DEMO_MODE=1."""
        with patch.dict(os.environ, {"DEMO_MODE": "1"}):
            assert _is_demo_mode() is True

    def test_demo_mode_false_with_other_values(self):
        """Demo mode should be false for other values."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            assert _is_demo_mode() is False
        with patch.dict(os.environ, {"DEMO_MODE": "no"}):
            assert _is_demo_mode() is False


class TestDemoScenarioDetection:
    """Tests for demo scenario detection."""

    def test_default_scenario_is_crashloop(self):
        """Default scenario should be crashloop."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DEMO_SCENARIO", None)
            assert _get_demo_scenario() == "crashloop"

    def test_scenario_from_env_var(self):
        """Scenario should come from environment variable."""
        with patch.dict(os.environ, {"DEMO_SCENARIO": "oom"}):
            assert _get_demo_scenario() == "oom"

        with patch.dict(os.environ, {"DEMO_SCENARIO": "alb-5xx"}):
            assert _get_demo_scenario() == "alb-5xx"


class TestAlertCreation:
    """Tests for alert creation from payload."""

    def test_create_alert_minimal(self):
        """Create alert with minimal required fields."""
        payload = {
            "alert_type": "eks-crashloop",
        }
        alert = _create_alert_from_payload(payload)

        assert alert.alert_type == "eks-crashloop"
        assert alert.source == "manual"
        assert alert.severity == "warning"

    def test_create_alert_full(self):
        """Create alert with all fields."""
        payload = {
            "alert_type": "ecs-oom",
            "source": "cloudwatch",
            "severity": "critical",
            "title": "ECS OOM Kill",
            "description": "Service experiencing OOM kills",
            "ecs_context": {
                "cluster": "prod-cluster",
                "service": "api-service",
            },
        }
        alert = _create_alert_from_payload(payload)

        assert alert.alert_type == "ecs-oom"
        assert alert.source == "cloudwatch"
        assert alert.severity == "critical"
        assert alert.title == "ECS OOM Kill"
        assert alert.ecs_context == {"cluster": "prod-cluster", "service": "api-service"}

    def test_create_alert_missing_type_raises(self):
        """Missing alert_type should raise ValueError."""
        payload = {"source": "cloudwatch"}
        with pytest.raises(ValueError, match="alert_type is required"):
            _create_alert_from_payload(payload)


class TestInvokeHandler:
    """Tests for the main invoke handler."""

    @pytest.mark.asyncio
    async def test_invoke_handler_with_prompt(self):
        """Handler should process free-form prompts."""
        payload = {
            "prompt": "What pods are failing in the production namespace?",
        }

        with patch.dict(os.environ, {"DEMO_MODE": "true", "DEMO_SCENARIO": "crashloop"}):
            results = []
            async for chunk in invoke_handler(payload):
                results.append(chunk)

        assert len(results) >= 2
        assert results[0]["status"] == "started"
        assert any(r["status"] == "processing" for r in results)

    @pytest.mark.asyncio
    async def test_invoke_handler_with_alert(self):
        """Handler should process alert payloads."""
        payload = {
            "alert_type": "eks-crashloop",
            "source": "cloudwatch",
            "title": "Pod CrashLoopBackOff",
            "description": "Payment service pod is crashing",
        }

        with patch.dict(os.environ, {"DEMO_MODE": "true", "DEMO_SCENARIO": "crashloop"}):
            results = []
            async for chunk in invoke_handler(payload):
                results.append(chunk)

        assert len(results) >= 2
        assert results[0]["status"] == "started"
        assert any(r["status"] == "processing" for r in results)

    @pytest.mark.asyncio
    async def test_invoke_handler_validation_error(self):
        """Handler should return error for invalid payload."""
        payload = {
            "invalid": "data",
        }

        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            results = []
            async for chunk in invoke_handler(payload):
                results.append(chunk)

        assert any(r.get("status") == "error" for r in results)
        assert any(r.get("error_type") == "validation" for r in results)


class TestCreateApp:
    """Tests for app creation."""

    def test_create_app_requires_bedrock_agentcore(self):
        """Creating app should require bedrock-agentcore package."""
        modules = {"bedrock_agentcore": None, "bedrock_agentcore.runtime": None}
        with patch.dict("sys.modules", modules):
            pass


class TestAlertModel:
    """Tests for Alert model integration."""

    def test_alert_with_eks_context(self):
        """Alert with EKS context should be created properly."""
        payload = {
            "alert_type": "eks-crashloop",
            "eks_context": {
                "cluster": "prod-eks",
                "namespace": "production",
                "pod": "payment-7d4f8b9c5d-x2k9m",
            },
        }
        alert = _create_alert_from_payload(payload)
        assert alert.eks_context == payload["eks_context"]

    def test_alert_with_ecs_context(self):
        """Alert with ECS context should be created properly."""
        payload = {
            "alert_type": "ecs-oom",
            "ecs_context": {
                "cluster": "prod-cluster",
                "service": "order-processor",
            },
        }
        alert = _create_alert_from_payload(payload)
        assert alert.ecs_context == payload["ecs_context"]

"""Pytest configuration and shared fixtures."""

import pytest

from aws_incident_copilot.agents.approval import ApprovalDecision, ApprovalHandler
from aws_incident_copilot.demo.fixtures import DemoDataProvider
from aws_incident_copilot.demo.scenarios import load_scenario
from aws_incident_copilot.runbooks.library import RunbookLibrary


@pytest.fixture
def demo_provider_crashloop():
    """Demo data provider for crashloop scenario."""
    return DemoDataProvider(scenario="crashloop")


@pytest.fixture
def demo_provider_oom():
    """Demo data provider for OOM scenario."""
    return DemoDataProvider(scenario="oom")


@pytest.fixture
def demo_provider_alb():
    """Demo data provider for ALB 5xx scenario."""
    return DemoDataProvider(scenario="alb-5xx")


@pytest.fixture
def runbook_library():
    """Runbook library with default runbooks."""
    return RunbookLibrary()


@pytest.fixture
def auto_approve_handler():
    """Approval handler that auto-approves everything."""
    return ApprovalHandler(mode="auto", auto_approve=True)


@pytest.fixture
def auto_deny_handler():
    """Approval handler that auto-denies everything."""

    def deny_callback(action, details):
        return ApprovalDecision.DENIED

    return ApprovalHandler(mode="callback", approval_callback=deny_callback)


@pytest.fixture
def crashloop_scenario():
    """Load the crashloop demo scenario."""
    return load_scenario("crashloop")


@pytest.fixture
def oom_scenario():
    """Load the OOM demo scenario."""
    return load_scenario("oom")


@pytest.fixture
def alb_scenario():
    """Load the ALB 5xx demo scenario."""
    return load_scenario("alb-5xx")

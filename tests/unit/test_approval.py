"""Tests for human-in-the-loop approval handling."""

from datetime import UTC

import pytest

from aws_incident_copilot.agents.approval import (
    ApprovalDecision,
    RemediationApproval,
    create_remediation_tools,
)


class TestApprovalHandler:
    """Tests for the ApprovalHandler class."""

    def test_auto_approve_mode(self, auto_approve_handler):
        """Test auto-approve mode."""
        approval = auto_approve_handler.request_approval(
            action="Restart deployment",
            details={"command": "kubectl rollout restart"},
            risk_level="high",
        )

        assert approval.decision == ApprovalDecision.APPROVED
        assert approval.reason == "Auto-approved"

    def test_callback_deny_mode(self, auto_deny_handler):
        """Test callback mode with deny."""
        approval = auto_deny_handler.request_approval(
            action="Dangerous action",
            details={"command": "rm -rf /"},
            risk_level="high",
        )

        assert approval.decision == ApprovalDecision.DENIED

    def test_approval_history(self, auto_approve_handler):
        """Test approval history tracking."""
        handler = auto_approve_handler

        handler.request_approval(
            action="Action 1",
            details={},
        )
        handler.request_approval(
            action="Action 2",
            details={},
        )

        history = handler.get_history()
        assert len(history) == 2
        assert history[0]["action"] == "Action 1"
        assert history[1]["action"] == "Action 2"

    def test_approval_to_dict(self):
        """Test RemediationApproval serialization."""
        from datetime import datetime

        approval = RemediationApproval(
            action="Test action",
            decision=ApprovalDecision.APPROVED,
            approver="test-user",
            timestamp=datetime.now(UTC),
            reason="Test reason",
        )

        data = approval.to_dict()
        assert data["action"] == "Test action"
        assert data["decision"] == "approved"
        assert data["approver"] == "test-user"
        assert "timestamp" in data


class TestRemediationTools:
    """Tests for remediation tools with approval."""

    @pytest.fixture
    def tools(self, auto_approve_handler):
        """Create remediation tools with auto-approve handler."""
        return create_remediation_tools(auto_approve_handler)

    @pytest.fixture
    def deny_tools(self, auto_deny_handler):
        """Create remediation tools with auto-deny handler."""
        return create_remediation_tools(auto_deny_handler)

    def test_restart_deployment_approved(self, tools):
        """Test restart deployment with approval."""
        restart_deployment = tools[0]

        result = restart_deployment(
            name="test-deployment",
            namespace="production",
        )

        assert result["status"] == "executed"
        assert "Restarted deployment" in result["action"]
        assert result["approval"]["decision"] == "approved"

    def test_restart_deployment_denied(self, deny_tools):
        """Test restart deployment with denial."""
        restart_deployment = deny_tools[0]

        result = restart_deployment(
            name="test-deployment",
            namespace="production",
        )

        assert result["status"] == "not_executed"
        assert "denied" in result["reason"].lower()

    def test_rollback_deployment_approved(self, tools):
        """Test rollback deployment with approval."""
        rollback_deployment = tools[1]

        result = rollback_deployment(
            name="test-deployment",
            namespace="production",
            revision=5,
        )

        assert result["status"] == "executed"
        assert "Rolled back" in result["action"]

    def test_scale_ecs_service_approved(self, tools):
        """Test ECS service scaling with approval."""
        scale_ecs_service = tools[2]

        result = scale_ecs_service(
            cluster="prod-cluster",
            service="api-service",
            desired_count=10,
        )

        assert result["status"] == "executed"
        assert "Scaled" in result["action"]

    def test_force_ecs_deployment_approved(self, tools):
        """Test force ECS deployment with approval."""
        force_ecs_deployment = tools[3]

        result = force_ecs_deployment(
            cluster="prod-cluster",
            service="api-service",
        )

        assert result["status"] == "executed"
        assert "Forced new deployment" in result["action"]

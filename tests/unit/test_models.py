"""Tests for incident data models."""

from datetime import UTC, datetime

import pytest

from aws_incident_copilot.models.incident import (
    Alert,
    AlertSeverity,
    AlertSource,
    IncidentReport,
    ProposedRemediation,
    RemediationRisk,
    RootCauseAnalysis,
)


class TestAlert:
    """Tests for the Alert model."""

    def test_create_alert_minimal(self):
        """Test creating an alert with minimal fields."""
        alert = Alert(
            id="test-001",
            source=AlertSource.EKS,
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
            timestamp=datetime.now(UTC),
            resource_id="test-resource",
        )

        assert alert.id == "test-001"
        assert alert.source == AlertSource.EKS
        assert alert.severity == AlertSeverity.HIGH
        assert alert.region == "us-west-2"

    def test_create_alert_with_eks_context(self):
        """Test creating an alert with EKS context."""
        alert = Alert(
            id="eks-001",
            source=AlertSource.EKS,
            severity=AlertSeverity.CRITICAL,
            title="Pod CrashLoopBackOff",
            description="Pod is in CrashLoopBackOff",
            timestamp=datetime.now(UTC),
            resource_id="payment-service-pod",
            namespace="production",
            cluster="prod-eks",
            metadata={"restart_count": 5},
        )

        assert alert.namespace == "production"
        assert alert.cluster == "prod-eks"
        assert alert.metadata["restart_count"] == 5

    def test_alert_severity_levels(self):
        """Test all severity levels."""
        for severity in AlertSeverity:
            alert = Alert(
                id="test",
                source=AlertSource.CLOUDWATCH,
                severity=severity,
                title="Test",
                description="Test",
                timestamp=datetime.now(UTC),
                resource_id="test",
            )
            assert alert.severity == severity


class TestRootCauseAnalysis:
    """Tests for the RootCauseAnalysis model."""

    def test_create_root_cause_analysis(self):
        """Test creating a root cause analysis."""
        rca = RootCauseAnalysis(
            primary_cause="Database authentication failure",
            confidence=0.95,
            supporting_evidence=[
                "Logs show authentication errors",
                "Recent credential rotation",
            ],
            alternative_causes=[
                "Network connectivity issues",
            ],
            reasoning="Multiple consecutive auth failures indicate credential mismatch",
        )

        assert rca.confidence == 0.95
        assert len(rca.supporting_evidence) == 2
        assert len(rca.alternative_causes) == 1

    def test_confidence_bounds(self):
        """Test confidence value bounds."""
        with pytest.raises(ValueError):
            RootCauseAnalysis(
                primary_cause="Test",
                confidence=1.5,
                supporting_evidence=[],
                reasoning="Test",
            )

        with pytest.raises(ValueError):
            RootCauseAnalysis(
                primary_cause="Test",
                confidence=-0.1,
                supporting_evidence=[],
                reasoning="Test",
            )


class TestProposedRemediation:
    """Tests for the ProposedRemediation model."""

    def test_create_remediation(self):
        """Test creating a remediation proposal."""
        remediation = ProposedRemediation(
            action="Restart deployment",
            command="kubectl rollout restart deployment/app",
            risk_level=RemediationRisk.MEDIUM,
            reversible=True,
            estimated_impact="Pods will restart, brief service interruption",
            rollback_steps=["kubectl rollout undo deployment/app"],
        )

        assert remediation.requires_approval is True
        assert remediation.reversible is True
        assert len(remediation.rollback_steps) == 1


class TestIncidentReport:
    """Tests for the IncidentReport model."""

    @pytest.fixture
    def sample_alert(self):
        """Create a sample alert for testing."""
        return Alert(
            id="test-001",
            source=AlertSource.EKS,
            severity=AlertSeverity.HIGH,
            title="Test Alert",
            description="Test description",
            timestamp=datetime.now(UTC),
            resource_id="test-resource",
        )

    def test_create_empty_report(self, sample_alert):
        """Test creating an empty incident report."""
        report = IncidentReport(
            alert=sample_alert,
            investigation_start=datetime.now(UTC),
        )

        assert report.status == "investigating"
        assert len(report.evidence) == 0
        assert len(report.timeline) == 0
        assert report.root_cause is None

    def test_report_to_markdown(self, sample_alert):
        """Test markdown report generation."""
        report = IncidentReport(
            alert=sample_alert,
            investigation_start=datetime.now(UTC),
            summary="Test incident summary",
            root_cause=RootCauseAnalysis(
                primary_cause="Test cause",
                confidence=0.9,
                supporting_evidence=["Evidence 1"],
                reasoning="Test reasoning",
            ),
            proposed_remediations=[
                ProposedRemediation(
                    action="Test action",
                    risk_level=RemediationRisk.LOW,
                    reversible=True,
                    estimated_impact="Test impact",
                )
            ],
        )

        markdown = report.to_markdown()

        assert "# Incident Report: Test Alert" in markdown
        assert "Test incident summary" in markdown
        assert "Test cause" in markdown
        assert "90%" in markdown
        assert "Test action" in markdown

"""Data models for incidents and reports."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertSource(StrEnum):
    """Alert source types."""

    CLOUDWATCH = "cloudwatch"
    EKS = "eks"
    ECS = "ecs"
    ALB = "alb"
    CUSTOM = "custom"


class Alert(BaseModel):
    """Represents an incoming alert that triggers investigation."""

    id: str = Field(description="Unique alert identifier")
    source: AlertSource = Field(description="Source of the alert")
    severity: AlertSeverity = Field(description="Alert severity level")
    title: str = Field(description="Short alert title")
    description: str = Field(description="Detailed alert description")
    timestamp: datetime = Field(description="When the alert was triggered")
    resource_id: str = Field(description="AWS resource identifier (ARN or name)")
    region: str = Field(default="us-west-2", description="AWS region")
    namespace: str | None = Field(default=None, description="Kubernetes namespace if applicable")
    cluster: str | None = Field(default=None, description="EKS cluster name if applicable")
    service: str | None = Field(default=None, description="ECS service name if applicable")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional alert metadata")


class Evidence(BaseModel):
    """A piece of evidence collected during investigation."""

    source: str = Field(description="Where this evidence came from")
    timestamp: datetime = Field(description="When this evidence was collected")
    summary: str = Field(description="Brief summary of the evidence")
    raw_data: dict[str, Any] = Field(description="Raw evidence data")
    relevance: str = Field(description="Why this evidence is relevant to the incident")


class IncidentTimeline(BaseModel):
    """A single event in the incident timeline."""

    timestamp: datetime = Field(description="When this event occurred")
    event: str = Field(description="Description of what happened")
    source: str = Field(description="Source of this timeline event")


class RootCauseAnalysis(BaseModel):
    """Root cause analysis results."""

    primary_cause: str = Field(description="The most likely root cause")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level (0-1)")
    supporting_evidence: list[str] = Field(description="Evidence supporting this conclusion")
    alternative_causes: list[str] = Field(
        default_factory=list, description="Other possible causes considered"
    )
    reasoning: str = Field(description="Explanation of the analysis reasoning")


class RemediationRisk(StrEnum):
    """Risk level for a proposed remediation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProposedRemediation(BaseModel):
    """A proposed remediation action."""

    action: str = Field(description="Description of the remediation action")
    command: str | None = Field(default=None, description="Exact command to execute if applicable")
    risk_level: RemediationRisk = Field(description="Risk level of this action")
    reversible: bool = Field(description="Whether this action can be easily reversed")
    estimated_impact: str = Field(description="Expected impact of this action")
    requires_approval: bool = Field(default=True, description="Whether this needs human approval")
    rollback_steps: list[str] = Field(
        default_factory=list, description="Steps to rollback if needed"
    )


class IncidentReport(BaseModel):
    """Complete incident investigation report."""

    alert: Alert = Field(description="The original alert that triggered this investigation")
    investigation_start: datetime = Field(description="When investigation started")
    investigation_end: datetime | None = Field(
        default=None, description="When investigation completed"
    )
    timeline: list[IncidentTimeline] = Field(
        default_factory=list, description="Chronological timeline of events"
    )
    evidence: list[Evidence] = Field(
        default_factory=list, description="Evidence collected during investigation"
    )
    root_cause: RootCauseAnalysis | None = Field(
        default=None, description="Root cause analysis results"
    )
    proposed_remediations: list[ProposedRemediation] = Field(
        default_factory=list, description="Proposed remediation actions"
    )
    runbooks_consulted: list[str] = Field(
        default_factory=list, description="Runbooks that were consulted"
    )
    status: str = Field(default="investigating", description="Current status of the incident")
    summary: str | None = Field(default=None, description="Executive summary of the incident")

    def to_markdown(self) -> str:
        """Generate a markdown report."""
        lines = [
            f"# Incident Report: {self.alert.title}",
            "",
            "## Summary",
            self.summary or "_Investigation in progress_",
            "",
            "## Alert Details",
            f"- **ID:** {self.alert.id}",
            f"- **Source:** {self.alert.source.value}",
            f"- **Severity:** {self.alert.severity.value}",
            f"- **Resource:** {self.alert.resource_id}",
            f"- **Triggered:** {self.alert.timestamp.isoformat()}",
            "",
            "## Timeline",
        ]

        for event in sorted(self.timeline, key=lambda x: x.timestamp):
            lines.append(
                f"- **{event.timestamp.strftime('%H:%M:%S')}** [{event.source}] {event.event}"
            )

        lines.extend(["", "## Evidence Collected"])
        for i, evidence in enumerate(self.evidence, 1):
            lines.extend(
                [
                    f"### Evidence {i}: {evidence.source}",
                    f"_{evidence.summary}_",
                    f"**Relevance:** {evidence.relevance}",
                    "",
                ]
            )

        if self.root_cause:
            lines.extend(
                [
                    "## Root Cause Analysis",
                    f"**Primary Cause:** {self.root_cause.primary_cause}",
                    f"**Confidence:** {self.root_cause.confidence:.0%}",
                    "",
                    "**Reasoning:**",
                    self.root_cause.reasoning,
                    "",
                    "**Supporting Evidence:**",
                ]
            )
            for ev in self.root_cause.supporting_evidence:
                lines.append(f"- {ev}")

            if self.root_cause.alternative_causes:
                lines.extend(["", "**Alternative Causes Considered:**"])
                for cause in self.root_cause.alternative_causes:
                    lines.append(f"- {cause}")

        if self.proposed_remediations:
            lines.extend(["", "## Proposed Remediations"])
            for i, rem in enumerate(self.proposed_remediations, 1):
                lines.extend(
                    [
                        f"### Option {i}: {rem.action}",
                        f"- **Risk Level:** {rem.risk_level.value}",
                        f"- **Reversible:** {'Yes' if rem.reversible else 'No'}",
                        f"- **Impact:** {rem.estimated_impact}",
                        f"- **Requires Approval:** {'Yes' if rem.requires_approval else 'No'}",
                    ]
                )
                if rem.command:
                    lines.extend(["", "**Command:**", "```", rem.command, "```"])
                if rem.rollback_steps:
                    lines.extend(["", "**Rollback Steps:**"])
                    for step in rem.rollback_steps:
                        lines.append(f"1. {step}")
                lines.append("")

        if self.runbooks_consulted:
            lines.extend(["## Runbooks Consulted"])
            for rb in self.runbooks_consulted:
                lines.append(f"- {rb}")

        return "\n".join(lines)

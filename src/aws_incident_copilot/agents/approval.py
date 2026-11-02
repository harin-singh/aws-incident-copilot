"""Human-in-the-loop approval handling for remediation actions.

This module provides the approval mechanism for remediation actions,
ensuring that destructive or risky operations require explicit human
confirmation before execution.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table


class ApprovalDecision(Enum):
    """Possible approval decisions."""

    APPROVED = "approved"
    DENIED = "denied"
    MODIFIED = "modified"
    DEFERRED = "deferred"


@dataclass
class RemediationApproval:
    """Record of a remediation approval decision."""

    action: str
    decision: ApprovalDecision
    approver: str
    timestamp: datetime
    reason: str | None = None
    modifications: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action": self.action,
            "decision": self.decision.value,
            "approver": self.approver,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "modifications": self.modifications,
        }


class ApprovalHandler:
    """Handles human approval for remediation actions.

    This class provides both CLI-based approval for demo mode and
    an extensible interface for integration with external approval
    systems (Slack, Step Functions, etc.).
    """

    def __init__(
        self,
        mode: str = "cli",
        approver_id: str = "demo-user",
        auto_approve: bool = False,
        approval_callback: Callable[[str, dict[str, Any]], ApprovalDecision] | None = None,
    ):
        """Initialize the approval handler.

        Args:
            mode: Approval mode ("cli", "auto", or "callback").
            approver_id: Identifier for the approver.
            auto_approve: If True, automatically approve all actions (for testing).
            approval_callback: Custom callback for approval decisions.
        """
        self.mode = mode
        self.approver_id = approver_id
        self.auto_approve = auto_approve
        self.approval_callback = approval_callback
        self.approval_history: list[RemediationApproval] = []
        self.console = Console()

    def request_approval(
        self,
        action: str,
        details: dict[str, Any],
        risk_level: str = "medium",
        reversible: bool = True,
    ) -> RemediationApproval:
        """Request approval for a remediation action.

        Args:
            action: Description of the action to be taken.
            details: Details about the action (command, impact, etc.).
            risk_level: Risk level (low, medium, high).
            reversible: Whether the action can be easily reversed.

        Returns:
            The approval decision record.
        """
        if self.auto_approve:
            return self._create_approval(action, ApprovalDecision.APPROVED, "Auto-approved")

        if self.mode == "cli":
            return self._cli_approval(action, details, risk_level, reversible)
        elif self.mode == "callback" and self.approval_callback:
            decision = self.approval_callback(action, details)
            return self._create_approval(action, decision)
        else:
            return self._create_approval(action, ApprovalDecision.DEFERRED, "No approval handler")

    def _cli_approval(
        self,
        action: str,
        details: dict[str, Any],
        risk_level: str,
        reversible: bool,
    ) -> RemediationApproval:
        """Handle CLI-based approval."""
        self.console.print()

        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(risk_level, "white")

        table = Table(title="Remediation Action Approval Required", show_header=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Action", action)
        table.add_row("Risk Level", f"[{risk_color}]{risk_level.upper()}[/{risk_color}]")
        table.add_row("Reversible", "Yes" if reversible else "[red]No[/red]")

        if details.get("command"):
            table.add_row("Command", f"[dim]{details['command']}[/dim]")

        if details.get("impact"):
            table.add_row("Expected Impact", details["impact"])

        if details.get("rollback_steps"):
            rollback = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(details["rollback_steps"]))
            table.add_row("Rollback Steps", rollback)

        self.console.print(Panel(table, border_style=risk_color))

        self.console.print()
        self.console.print("[bold yellow]⚠️  HUMAN APPROVAL REQUIRED[/bold yellow]")
        self.console.print()
        self.console.print("This action will modify your AWS environment.")
        self.console.print("Review the details above carefully before approving.")
        self.console.print()

        try:
            approved = Confirm.ask(
                "[bold]Do you approve this remediation action?[/bold]",
                default=False,
            )

            if approved:
                self.console.print("[green]✓ Action approved[/green]")
                return self._create_approval(action, ApprovalDecision.APPROVED)
            else:
                reason = self.console.input("[dim]Reason for denial (optional): [/dim]")
                self.console.print("[red]✗ Action denied[/red]")
                return self._create_approval(
                    action,
                    ApprovalDecision.DENIED,
                    reason or "User denied",
                )
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Action deferred[/yellow]")
            return self._create_approval(action, ApprovalDecision.DEFERRED, "User interrupted")

    def _create_approval(
        self,
        action: str,
        decision: ApprovalDecision,
        reason: str | None = None,
    ) -> RemediationApproval:
        """Create and record an approval decision."""
        approval = RemediationApproval(
            action=action,
            decision=decision,
            approver=self.approver_id,
            timestamp=datetime.now(UTC),
            reason=reason,
        )
        self.approval_history.append(approval)
        return approval

    def get_history(self) -> list[dict[str, Any]]:
        """Get the approval history.

        Returns:
            List of approval records.
        """
        return [a.to_dict() for a in self.approval_history]


def create_remediation_tools(approval_handler: ApprovalHandler) -> list[Callable[..., Any]]:
    """Create remediation tools that require approval.

    These tools demonstrate the pattern for implementing remediation
    actions with human-in-the-loop approval.

    Args:
        approval_handler: The approval handler to use.

    Returns:
        List of tool functions.
    """
    from strands import tool

    @tool(description="Restart a Kubernetes deployment. Requires human approval.")
    def restart_deployment(
        name: str,
        namespace: str = "default",
    ) -> dict[str, Any]:
        """Restart a Kubernetes deployment."""
        approval = approval_handler.request_approval(
            action=f"Restart deployment {name} in namespace {namespace}",
            details={
                "command": f"kubectl rollout restart deployment/{name} -n {namespace}",
                "impact": "Pods will be terminated and recreated with the same configuration",
                "rollback_steps": [
                    "Deployment will recreate pods automatically",
                    f"If issues persist: kubectl rollout undo deployment/{name} -n {namespace}",
                ],
            },
            risk_level="medium",
            reversible=True,
        )

        if approval.decision != ApprovalDecision.APPROVED:
            return {
                "status": "not_executed",
                "reason": f"Action {approval.decision.value}: {approval.reason}",
            }

        return {
            "status": "executed",
            "action": f"Restarted deployment {name}",
            "approval": approval.to_dict(),
        }

    @tool(
        description="Rollback a Kubernetes deployment to previous revision. "
        "Requires human approval."
    )
    def rollback_deployment(
        name: str,
        namespace: str = "default",
        revision: int | None = None,
    ) -> dict[str, Any]:
        """Rollback a Kubernetes deployment."""
        revision_str = f" to revision {revision}" if revision else " to previous revision"

        approval = approval_handler.request_approval(
            action=f"Rollback deployment {name}{revision_str} in namespace {namespace}",
            details={
                "command": f"kubectl rollout undo deployment/{name} -n {namespace}"
                + (f" --to-revision={revision}" if revision else ""),
                "impact": "Deployment will revert to previous container image and configuration",
                "rollback_steps": [
                    "Re-deploy the newer version when ready",
                    f"kubectl rollout history deployment/{name} -n {namespace}",
                ],
            },
            risk_level="medium",
            reversible=True,
        )

        if approval.decision != ApprovalDecision.APPROVED:
            return {
                "status": "not_executed",
                "reason": f"Action {approval.decision.value}: {approval.reason}",
            }

        return {
            "status": "executed",
            "action": f"Rolled back deployment {name}",
            "approval": approval.to_dict(),
        }

    @tool(description="Update ECS service desired count. Requires human approval.")
    def scale_ecs_service(
        cluster: str,
        service: str,
        desired_count: int,
    ) -> dict[str, Any]:
        """Scale an ECS service."""
        approval = approval_handler.request_approval(
            action=f"Scale ECS service {service} to {desired_count} tasks",
            details={
                "command": (
                    f"aws ecs update-service --cluster {cluster} "
                    f"--service {service} --desired-count {desired_count}"
                ),
                "impact": f"Service will scale to {desired_count} running tasks",
                "rollback_steps": [
                    "Scale back to previous count using the same command",
                ],
            },
            risk_level="low",
            reversible=True,
        )

        if approval.decision != ApprovalDecision.APPROVED:
            return {
                "status": "not_executed",
                "reason": f"Action {approval.decision.value}: {approval.reason}",
            }

        return {
            "status": "executed",
            "action": f"Scaled {service} to {desired_count} tasks",
            "approval": approval.to_dict(),
        }

    @tool(description="Force new ECS deployment. Requires human approval.")
    def force_ecs_deployment(
        cluster: str,
        service: str,
    ) -> dict[str, Any]:
        """Force a new ECS deployment to restart all tasks."""
        approval = approval_handler.request_approval(
            action=f"Force new deployment for ECS service {service}",
            details={
                "command": (
                    f"aws ecs update-service --cluster {cluster} "
                    f"--service {service} --force-new-deployment"
                ),
                "impact": (
                    "All tasks will be replaced with new tasks using the same task definition"
                ),
                "rollback_steps": [
                    "New tasks will start automatically",
                    "If issues persist, roll back task definition or investigate further",
                ],
            },
            risk_level="medium",
            reversible=True,
        )

        if approval.decision != ApprovalDecision.APPROVED:
            return {
                "status": "not_executed",
                "reason": f"Action {approval.decision.value}: {approval.reason}",
            }

        return {
            "status": "executed",
            "action": f"Forced new deployment for {service}",
            "approval": approval.to_dict(),
        }

    return [restart_deployment, rollback_deployment, scale_ecs_service, force_ecs_deployment]

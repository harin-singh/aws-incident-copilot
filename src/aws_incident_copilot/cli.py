"""CLI interface for AWS Incident Copilot.

This module provides the command-line interface for running the
incident copilot in both demo and live modes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aws_incident_copilot import __version__
from aws_incident_copilot.agents import ApprovalHandler, IncidentCopilot
from aws_incident_copilot.demo.model_stub import UNGROUNDED_MARKER, DemoModelProvider
from aws_incident_copilot.demo.scenarios import list_scenarios, load_scenario
from aws_incident_copilot.models.incident import Alert

if TYPE_CHECKING:
    from aws_incident_copilot.models.incident import IncidentReport

console = Console()


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """AWS Incident Copilot - AI-powered incident investigation for AWS.

    Investigates EKS/ECS incidents using MCP-compatible tools and proposes
    fixes with human-in-the-loop approval.
    """
    pass


@main.command()
@click.option(
    "--scenario",
    "-s",
    type=click.Choice(["crashloop", "oom", "alb-5xx"]),
    default="crashloop",
    help="Demo scenario to run",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Auto-approve remediation actions (for testing)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress verbose output",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="If a remediation is approved, validate it without mutating state",
)
def demo(scenario: str, auto_approve: bool, quiet: bool, dry_run: bool) -> None:
    """Run a demo incident investigation.

    Uses fixture data and a scripted model. The model only emits an RCA
    after investigation tools return the expected evidence.

    Available scenarios:
    - crashloop: EKS pod in CrashLoopBackOff due to DB auth failure
    - oom: ECS tasks OOM-killed during large batch processing
    - alb-5xx: ALB 5xx spike from database connection exhaustion
    """
    verbose = not quiet

    if verbose:
        _print_banner()
        console.print(f"[bold]Running demo scenario:[/bold] {scenario}")
        console.print()

    try:
        scenario_data = load_scenario(scenario)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    approval_handler = ApprovalHandler(
        mode="cli",
        auto_approve=auto_approve,
    )

    copilot = IncidentCopilot(
        demo_mode=True,
        scenario=scenario,
        approval_handler=approval_handler,
        verbose=verbose,
        dry_run=dry_run,
    )

    report = copilot.investigate(alert=scenario_data.alert)

    if verbose:
        _print_report(report)

    summary = report.summary or ""
    if UNGROUNDED_MARKER in summary:
        console.print(
            "[red]Demo failed:[/red] the model refused to emit an RCA because "
            "investigation tools did not return expected evidence."
        )
        sys.exit(2)

    if isinstance(copilot.model, DemoModelProvider) and copilot.model.grounded is False:
        console.print("[red]Demo failed:[/red] investigation was not grounded in tool output.")
        sys.exit(2)

    if verbose:
        console.print()
        console.print("[bold green]Demo complete![/bold green]")
        console.print()
        console.print(
            "[dim]This run used fixture data. Investigation tools were invoked "
            "against the demo backend; remediations are simulated after approval.[/dim]"
        )


@main.command()
def scenarios() -> None:
    """List available demo scenarios."""
    _print_banner()

    table = Table(title="Available Demo Scenarios")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Severity", style="yellow")
    table.add_column("Source")
    table.add_column("Description")

    for s in list_scenarios():
        severity_style = {
            "critical": "red",
            "high": "yellow",
            "medium": "blue",
        }.get(s["severity"], "white")

        table.add_row(
            s["id"],
            s["name"],
            f"[{severity_style}]{s['severity'].upper()}[/{severity_style}]",
            s["source"].upper(),
            s["description"][:60] + "..." if len(s["description"]) > 60 else s["description"],
        )

    console.print(table)
    console.print()
    console.print("[dim]Run a scenario with: incident-copilot demo --scenario <id>[/dim]")


@main.command()
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["demo", "live"]),
    default="demo",
    help="Run mode (demo uses fixtures, live queries AWS)",
)
@click.option(
    "--region",
    "-r",
    default="us-west-2",
    help="AWS region for live mode",
)
@click.option(
    "--cluster",
    "-c",
    help="EKS/ECS cluster name",
)
@click.option(
    "--namespace",
    "-n",
    default="default",
    help="Kubernetes namespace",
)
@click.option(
    "--alert-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON file containing an Alert payload (required for live mode)",
)
@click.option(
    "--kubeconfig",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Kubeconfig path for live Kubernetes investigation/remediation",
)
@click.option(
    "--remediation-role-arn",
    help="IAM role to assume before executing remediations",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate remediations without applying them",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Auto-approve remediation actions (for testing)",
)
def run(
    mode: str,
    region: str,
    cluster: str | None,
    namespace: str,
    alert_file: Path | None,
    kubeconfig: Path | None,
    remediation_role_arn: str | None,
    dry_run: bool,
    auto_approve: bool,
) -> None:
    """Run the incident copilot.

    Demo mode uses fixture data. Live mode requires AWS credentials (and a
    kubeconfig for EKS) plus ``--alert-file``.
    """
    _print_banner()

    if mode == "demo":
        console.print(
            "[dim]Starting in demo mode. Prefer: incident-copilot demo --scenario <name>[/dim]"
        )
        ctx = click.get_current_context()
        ctx.invoke(
            demo, scenario="crashloop", auto_approve=auto_approve, quiet=False, dry_run=dry_run
        )
        return

    if alert_file is None:
        console.print(
            "[red]Live mode requires --alert-file pointing at an Alert JSON document.[/red]"
        )
        sys.exit(1)

    try:
        payload = json.loads(alert_file.read_text())
        alert = Alert.model_validate(payload)
    except Exception as exc:
        console.print(f"[red]Failed to load alert file:[/red] {exc}")
        sys.exit(1)

    if cluster and not alert.cluster:
        alert.cluster = cluster
    if namespace and not alert.namespace:
        alert.namespace = namespace
    if region:
        alert.region = region

    copilot = IncidentCopilot(
        demo_mode=False,
        approval_handler=ApprovalHandler(mode="cli", auto_approve=auto_approve),
        verbose=True,
        region=region,
        kubeconfig_path=str(kubeconfig) if kubeconfig else None,
        remediation_role_arn=remediation_role_arn,
        dry_run=dry_run,
    )
    report = copilot.investigate(alert=alert)
    _print_report(report)


@main.command()
def version() -> None:
    """Show version information."""
    console.print(f"AWS Incident Copilot v{__version__}")


def _print_banner() -> None:
    """Print the application banner."""
    banner = r"""
   ___        _______   ____          _     __           __
  / _ | _    / __/ _ ) /  _/___  ____(_)___/ /__ ___  __/ /_
 / __ |(_)  _\ \/ _  |_/ // _ \/ __/ / __  / -_) _ \/ __  /
/_/ |_|(_) /___/____//___/_//_/\__/_/\__,_/\__/_//_/\__,_/

  _____            _ __     __
 / ___/__  ___  (_) /__  / /_
/ /__/ _ \/ _ \/ / / _ \/ __/
\___/\___/ .__/_/_/\___/\__/
        /_/
"""
    console.print(f"[bold cyan]{banner}[/bold cyan]")
    console.print(f"[dim]Version {__version__} | AI-Powered Incident Investigation[/dim]")
    console.print()


def _print_report(report: IncidentReport) -> None:
    """Print an incident report to console."""
    console.print()
    console.print(
        Panel(
            "[bold]Investigation Complete[/bold]",
            border_style="green",
        )
    )
    console.print()

    if report.summary:
        console.print(report.summary, markup=False)
    else:
        console.print("[dim]No summary generated[/dim]")


if __name__ == "__main__":
    main()

"""CLI interface for AWS Incident Copilot.

This module provides the command-line interface for running the
incident copilot in both demo and live modes.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aws_incident_copilot import __version__
from aws_incident_copilot.agents import ApprovalHandler, IncidentCopilot
from aws_incident_copilot.demo.fixtures import DemoDataProvider
from aws_incident_copilot.demo.scenarios import list_scenarios, load_scenario
from aws_incident_copilot.mcp_servers import (
    create_cloudwatch_server,
    create_ecs_server,
    create_kubernetes_server,
)

if TYPE_CHECKING:
    from aws_incident_copilot.models.incident import IncidentReport

console = Console()


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """AWS Incident Copilot - AI-powered incident investigation for AWS.

    Investigates EKS/ECS incidents using MCP tools and proposes fixes
    with human-in-the-loop approval.
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
def demo(scenario: str, auto_approve: bool, quiet: bool) -> None:
    """Run a demo incident investigation.

    This mode uses pre-recorded fixture data and scripted model responses
    to demonstrate the incident investigation workflow without requiring
    AWS credentials.

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

    demo_provider = DemoDataProvider(scenario=scenario)

    approval_handler = ApprovalHandler(
        mode="cli",
        auto_approve=auto_approve,
    )

    copilot = IncidentCopilot(
        demo_mode=True,
        scenario=scenario,
        approval_handler=approval_handler,
        verbose=verbose,
    )

    cw_server = create_cloudwatch_server(demo_mode=True, demo_provider=demo_provider)
    k8s_server = create_kubernetes_server(demo_mode=True, demo_provider=demo_provider)
    ecs_server = create_ecs_server(demo_mode=True, demo_provider=demo_provider)

    mcp_tools = _collect_mcp_tools([cw_server, k8s_server, ecs_server])

    report = copilot.investigate(
        alert=scenario_data.alert,
        mcp_tools=mcp_tools,
    )

    if verbose:
        _print_report(report)

    if verbose:
        console.print()
        console.print("[bold green]Demo complete![/bold green]")
        console.print()
        console.print("[dim]This was a demonstration using pre-recorded data.")
        console.print("In live mode, the copilot would query actual AWS resources.[/dim]")


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
    "--alert-id",
    help="Alert ID to investigate",
)
def run(
    mode: str,
    region: str,
    cluster: str | None,
    namespace: str,
    alert_id: str | None,
) -> None:
    """Run the incident copilot.

    In demo mode, uses pre-recorded data. In live mode, requires AWS
    credentials and queries actual AWS resources.
    """
    _print_banner()

    if mode == "live":
        console.print("[yellow]Live mode not yet fully implemented.[/yellow]")
        console.print("Use demo mode to see the incident copilot in action.")
        console.print()
        console.print("[dim]Run: incident-copilot demo --scenario crashloop[/dim]")
        sys.exit(0)

    console.print("[dim]Starting in demo mode...[/dim]")
    console.print("[dim]Run 'incident-copilot demo --scenario <name>' for specific scenarios[/dim]")


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
        console.print(report.summary)
    else:
        console.print("[dim]No summary generated[/dim]")


def _collect_mcp_tools(servers: list) -> list:
    """Collect tools from MCP servers.

    For demo mode, we directly collect the tool functions from
    the MCP servers rather than connecting via transport.
    """
    tools = []
    for server in servers:
        for tool_name in server._tool_manager._tools:
            tool_func = server._tool_manager._tools[tool_name]
            tools.append(tool_func.fn)
    return tools


if __name__ == "__main__":
    main()

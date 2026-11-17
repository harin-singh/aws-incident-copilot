"""Strands investigation tools for CloudWatch, Kubernetes, and ECS."""

from aws_incident_copilot.tools.cloudwatch import create_cloudwatch_tools
from aws_incident_copilot.tools.context import InvestigationContext
from aws_incident_copilot.tools.ecs import create_ecs_tools
from aws_incident_copilot.tools.kubernetes import create_kubernetes_tools


def collect_investigation_tools(ctx: InvestigationContext) -> list:
    """Return all investigation tools as Strands ``@tool`` wrappers.

    This is the supported registration path for the agent. It does not
    reach into MCP server private attributes.
    """
    return [
        *create_cloudwatch_tools(ctx),
        *create_kubernetes_tools(ctx),
        *create_ecs_tools(ctx),
    ]


__all__ = [
    "InvestigationContext",
    "collect_investigation_tools",
    "create_cloudwatch_tools",
    "create_ecs_tools",
    "create_kubernetes_tools",
]

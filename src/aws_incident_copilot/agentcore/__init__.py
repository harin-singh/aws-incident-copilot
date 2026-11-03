"""Amazon Bedrock AgentCore integration for AWS Incident Copilot.

This module provides the AgentCore Runtime entrypoint and related utilities
for deploying the incident copilot as an AgentCore agent.
"""

from aws_incident_copilot.agentcore.entrypoint import create_app, invoke_handler

__all__ = ["create_app", "invoke_handler"]

"""Amazon Bedrock AgentCore Runtime entrypoint for AWS Incident Copilot.

This module provides the main entrypoint for running the incident copilot
on Amazon Bedrock AgentCore Runtime. It handles:
- Incoming investigation requests via POST /invocations
- Health checks via GET /ping
- Streaming responses for long-running investigations

The entrypoint can run in two modes:
1. Live mode: Uses actual AWS APIs and Bedrock models
2. Demo mode: Uses fixture data for offline testing/demos

Environment Variables:
    DEMO_MODE: Set to "true" to enable demo mode (default: false)
    DEMO_SCENARIO: Demo scenario to use (crashloop, oom, alb-5xx)
    AWS_REGION: AWS region for Bedrock and other services
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from aws_incident_copilot.agents.copilot import IncidentCopilot
from aws_incident_copilot.models.incident import Alert

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from bedrock_agentcore.runtime import BedrockAgentCoreApp

logger = logging.getLogger(__name__)

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def _is_demo_mode() -> bool:
    """Check if demo mode is enabled via environment variable."""
    return os.environ.get("DEMO_MODE", "false").lower() in ("true", "1", "yes")


def _get_demo_scenario() -> str:
    """Get the demo scenario from environment variable."""
    return os.environ.get("DEMO_SCENARIO", "crashloop")


def _create_alert_from_payload(payload: dict[str, Any]) -> Alert:
    """Create an Alert object from the incoming request payload.

    Args:
        payload: The incoming request payload with alert details.

    Returns:
        An Alert object for investigation.

    Raises:
        ValueError: If required fields are missing from the payload.
    """
    alert_type = payload.get("alert_type")
    if not alert_type:
        raise ValueError("alert_type is required in the payload")

    source = payload.get("source", "manual")
    severity = payload.get("severity", "warning")
    title = payload.get("title", f"Investigation request: {alert_type}")
    description = payload.get("description", "")

    eks_context = payload.get("eks_context")
    ecs_context = payload.get("ecs_context")

    return Alert(
        alert_type=alert_type,
        source=source,
        severity=severity,
        title=title,
        description=description,
        eks_context=eks_context,
        ecs_context=ecs_context,
        raw_payload=payload,
    )


async def invoke_handler(
    payload: dict[str, Any],
    context: Any = None,
) -> AsyncIterator[dict[str, Any]]:
    """Handle incoming investigation requests.

    This is the main entrypoint handler that processes investigation requests
    and streams back results. It can operate in demo mode or live mode.

    Args:
        payload: The incoming request payload containing:
            - alert_type: Type of alert (e.g., "eks-crashloop", "ecs-oom", "alb-5xx")
            - source: Alert source (e.g., "cloudwatch", "pagerduty")
            - severity: Alert severity (critical, warning, info)
            - title: Alert title
            - description: Alert description
            - eks_context: Optional EKS context (cluster, namespace, pod)
            - ecs_context: Optional ECS context (cluster, service)
            - prompt: Optional free-form prompt for investigation
        context: Optional request context from AgentCore Runtime.

    Yields:
        Streaming response chunks with investigation progress and results.
    """
    logger.info("Received investigation request: %s", json.dumps(payload, default=str)[:500])

    demo_mode = _is_demo_mode()
    scenario = _get_demo_scenario()

    if demo_mode:
        logger.info("Running in demo mode with scenario: %s", scenario)

    yield {"status": "started", "message": "Investigation initiated"}

    try:
        if "prompt" in payload and not payload.get("alert_type"):
            prompt = payload["prompt"]
            yield {"status": "processing", "message": f"Processing prompt: {prompt[:100]}..."}

            copilot = IncidentCopilot(
                demo_mode=demo_mode,
                scenario=scenario,
                verbose=False,
            )

            result = await copilot.investigate_prompt_async(prompt)

            yield {
                "status": "completed",
                "result": result,
            }
        else:
            alert = _create_alert_from_payload(payload)

            yield {
                "status": "processing",
                "message": f"Investigating alert: {alert.title}",
                "alert_type": alert.alert_type,
            }

            copilot = IncidentCopilot(
                demo_mode=demo_mode,
                scenario=scenario,
                verbose=False,
            )

            report = await copilot.investigate_alert_async(alert)

            yield {
                "status": "completed",
                "report": report.model_dump() if report else None,
                "summary": report.executive_summary if report else "Investigation completed",
            }

    except ValueError as e:
        logger.warning("Validation error: %s", e)
        yield {"status": "error", "error": str(e), "error_type": "validation"}
    except Exception as e:
        logger.exception("Investigation failed")
        yield {"status": "error", "error": str(e), "error_type": "internal"}


def create_app() -> BedrockAgentCoreApp:
    """Create and configure the BedrockAgentCoreApp instance.

    Returns:
        Configured BedrockAgentCoreApp ready to run.

    Raises:
        ImportError: If bedrock-agentcore is not installed.
    """
    try:
        from bedrock_agentcore.runtime import BedrockAgentCoreApp
    except ImportError as e:
        raise ImportError(
            "bedrock-agentcore is required for AgentCore deployment. "
            "Install it with: pip install aws-incident-copilot[agentcore]"
        ) from e

    app = BedrockAgentCoreApp()

    @app.entrypoint
    async def _invoke(
        payload: dict[str, Any], context: Any = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Entrypoint wrapper for BedrockAgentCoreApp."""
        async for chunk in invoke_handler(payload, context):
            yield chunk

    return app


def main() -> None:
    """Main entry point for running the AgentCore server locally.

    This can be used for local development and testing.
    The server listens on port 8080 by default.
    """
    app = create_app()
    port = int(os.environ.get("PORT", "8080"))
    logger.info("Starting AgentCore server on port %d (demo_mode=%s)", port, _is_demo_mode())
    app.run(port=port)


if __name__ == "__main__":
    main()

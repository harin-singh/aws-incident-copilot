"""Standalone Lambda handler packaged by Terraform.

Prefers the installed ``aws_incident_copilot`` package (container/layer).
Falls back to EventBridge parsing plus optional AgentCore invoke so the
zip artifact still does useful work without the rest of the package.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def _alert_payload_from_event(event: dict[str, Any]) -> dict[str, Any]:
    if "alert_type" in event:
        return event
    detail = event.get("detail") or {}
    alarm_name = detail.get("alarmName") or event.get("alarmName") or "unknown-alarm"
    state = (detail.get("state") or {}).get("value") or event.get("state", "ALARM")
    reason = (detail.get("state") or {}).get("reason") or ""
    return {
        "alert_type": "cloudwatch-alarm",
        "source": "cloudwatch",
        "severity": "high" if state == "ALARM" else "info",
        "title": f"CloudWatch alarm {alarm_name} is {state}",
        "description": reason or f"Alarm {alarm_name} changed state to {state}",
        "region": event.get("region") or os.environ.get("AWS_REGION", "us-west-2"),
        "resource_id": alarm_name,
        "raw_payload": event,
    }


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """AWS Lambda handler used by the EventBridge alarm rule."""
    try:
        from aws_incident_copilot.lambda_handler import lambda_handler as packaged

        return packaged(event, context)
    except ImportError:
        logger.info("Package not installed; using standalone invoker")

    payload = _alert_payload_from_event(event)
    runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN")
    if not runtime_arn:
        return {
            "statusCode": 200,
            "body": {
                "invoked": "parse-only",
                "alert": payload,
                "note": "Set AGENTCORE_RUNTIME_ARN or deploy the container image.",
            },
        }

    import boto3

    client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        payload=json.dumps(payload).encode("utf-8"),
    )
    return {"statusCode": 200, "body": {"invoked": "agentcore", "response": str(response)[:2000]}}

"""EventBridge/Lambda entrypoint for AWS Incident Copilot.

The zip-deployed function is a thin invoker:
- Parse a CloudWatch Alarm State Change event
- Invoke AgentCore Runtime when ``AGENTCORE_RUNTIME_ARN`` is set
- Otherwise run ``IncidentCopilot`` in-process when the package is installed
  (container image / layer)

This is the missing EventBridge target that the original Terraform declared
but never attached.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def alert_payload_from_event(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize an EventBridge or direct invocation into an alert payload."""
    if "alert_type" in event:
        return event

    detail = event.get("detail") or {}
    alarm_name = detail.get("alarmName") or event.get("alarmName") or "unknown-alarm"
    state = (detail.get("state") or {}).get("value") or event.get("state", "ALARM")
    reason = (detail.get("state") or {}).get("reason") or ""
    region = event.get("region") or os.environ.get("AWS_REGION", "us-west-2")

    return {
        "alert_type": "cloudwatch-alarm",
        "source": "cloudwatch",
        "severity": "high" if state == "ALARM" else "info",
        "title": f"CloudWatch alarm {alarm_name} is {state}",
        "description": reason or f"Alarm {alarm_name} changed state to {state}",
        "region": region,
        "resource_id": alarm_name,
        "metadata": {
            "alarm_name": alarm_name,
            "state": state,
            "account": event.get("account"),
        },
        "raw_payload": event,
    }


def invoke_agentcore(
    runtime_arn: str,
    payload: dict[str, Any],
    client: Any | None = None,
) -> dict[str, Any]:
    """Invoke an AgentCore runtime with the alert payload."""
    if client is None:
        import boto3

        client = boto3.client(
            "bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-west-2")
        )

    body = json.dumps(payload).encode("utf-8")
    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        payload=body,
    )
    raw = response.get("response") or response.get("payload") or b""
    if hasattr(raw, "read"):
        raw = raw.read()
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    try:
        parsed: Any = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"raw": text}
    return {"invoked": "agentcore", "runtime_arn": runtime_arn, "result": parsed}


def invoke_inprocess(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the copilot in-process when the package is available."""
    from aws_incident_copilot.agents.copilot import IncidentCopilot
    from aws_incident_copilot.models.incident import Alert

    demo_mode = os.environ.get("DEMO_MODE", "false").lower() in ("true", "1", "yes")
    scenario = os.environ.get("DEMO_SCENARIO", "crashloop")
    alert = Alert.model_validate(payload)
    copilot = IncidentCopilot(demo_mode=demo_mode, scenario=scenario, verbose=False)
    report = copilot.investigate(alert=alert)
    return {
        "invoked": "inprocess",
        "status": report.status,
        "summary": report.summary,
    }


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """AWS Lambda handler for EventBridge alarm events."""
    logger.info("Received event: %s", json.dumps(event, default=str)[:1000])
    payload = alert_payload_from_event(event)
    runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN")
    if runtime_arn:
        result = invoke_agentcore(runtime_arn, payload)
    else:
        try:
            result = invoke_inprocess(payload)
        except Exception:
            logger.exception("In-process investigation failed; returning parsed alert")
            result = {
                "invoked": "parse-only",
                "alert": payload,
                "note": (
                    "Package not available in this runtime. "
                    "Set AGENTCORE_RUNTIME_ARN or deploy the container image."
                ),
            }
    return {"statusCode": 200, "body": result}

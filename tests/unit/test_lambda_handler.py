"""Tests for the EventBridge/Lambda entrypoint."""

from unittest.mock import MagicMock, patch

from aws_incident_copilot.lambda_handler import (
    alert_payload_from_event,
    invoke_agentcore,
    lambda_handler,
)


def test_alert_from_eventbridge_alarm() -> None:
    event = {
        "region": "us-west-2",
        "account": "123456789012",
        "detail-type": "CloudWatch Alarm State Change",
        "detail": {
            "alarmName": "api-5xx-high",
            "state": {"value": "ALARM", "reason": "Threshold crossed"},
        },
    }
    payload = alert_payload_from_event(event)
    assert payload["alert_type"] == "cloudwatch-alarm"
    assert payload["resource_id"] == "api-5xx-high"
    assert payload["severity"] == "high"


def test_alert_passthrough() -> None:
    event = {"alert_type": "eks-crashloop", "title": "already an alert"}
    assert alert_payload_from_event(event)["title"] == "already an alert"


def test_invoke_agentcore_uses_injected_client() -> None:
    client = MagicMock()
    client.invoke_agent_runtime.return_value = {"payload": b'{"ok": true}'}
    result = invoke_agentcore(
        "arn:aws:bedrock:us-west-2:1:runtime/x", {"alert_type": "x"}, client=client
    )
    client.invoke_agent_runtime.assert_called_once()
    assert result["invoked"] == "agentcore"
    assert result["result"]["ok"] is True


def test_invoke_inprocess_demo() -> None:
    from aws_incident_copilot.lambda_handler import invoke_inprocess

    with patch.dict("os.environ", {"DEMO_MODE": "true", "DEMO_SCENARIO": "crashloop"}):
        result = invoke_inprocess(
            {
                "alert_type": "eks-crashloop",
                "title": "Pod CrashLoopBackOff",
                "description": "demo",
            }
        )
    assert result["invoked"] == "inprocess"
    assert result["status"] == "complete"


def test_lambda_handler_parse_only_without_package_path() -> None:
    event = {
        "detail": {"alarmName": "cpu", "state": {"value": "ALARM", "reason": "hot"}},
        "region": "us-west-2",
    }
    with (
        patch.dict("os.environ", {}, clear=True),
        patch(
            "aws_incident_copilot.lambda_handler.invoke_inprocess",
            side_effect=RuntimeError("no package"),
        ),
    ):
        result = lambda_handler(event)
    assert result["statusCode"] == 200
    assert result["body"]["invoked"] == "parse-only"
    assert result["body"]["alert"]["resource_id"] == "cpu"

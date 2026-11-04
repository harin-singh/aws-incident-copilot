"""Tests for demo model grounding."""

from aws_incident_copilot.demo.model_stub import (
    UNGROUNDED_MARKER,
    DemoModelProvider,
    evaluate_grounding,
    extract_tool_result_text,
)


def test_extract_tool_result_text_from_strands_blocks() -> None:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "status": "success",
                        "content": [{"json": {"reason": "CrashLoopBackOff"}}],
                    }
                }
            ],
        }
    ]
    text = extract_tool_result_text(messages)
    assert "CrashLoopBackOff" in text


def test_evaluate_grounding_requires_tool_evidence() -> None:
    ok, errors = evaluate_grounding("crashloop", "")
    assert ok is False
    assert errors

    ok, errors = evaluate_grounding(
        "crashloop",
        'success {"reason": "CrashLoopBackOff"} password authentication failed',
    )
    assert ok is True
    assert errors == []


def test_evaluate_grounding_flags_tool_not_found() -> None:
    ok, errors = evaluate_grounding(
        "crashloop",
        "tool not found CrashLoopBackOff password authentication failed",
    )
    assert ok is False
    assert any("tool invocation failed" in e for e in errors)


async def test_model_refuses_ungrounded_rca() -> None:
    model = DemoModelProvider(scenario="crashloop")
    # Skip to the final scripted RCA turn without any tool results.
    model.call_count = len(model._responses) - 1
    events = []
    async for event in model.stream(messages=[]):
        events.append(event)
    text = ""
    for event in events:
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            text += delta["text"]
    assert UNGROUNDED_MARKER in text
    assert "Confidence: 95%" not in text
    assert model.grounded is False


async def test_model_emits_rca_when_evidence_present() -> None:
    model = DemoModelProvider(scenario="crashloop")
    model.call_count = len(model._responses) - 1
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "status": "success",
                        "content": [
                            {
                                "json": {
                                    "reason": "CrashLoopBackOff",
                                    "logs": (
                                        "FATAL: password authentication failed "
                                        'for user "payment_svc"'
                                    ),
                                }
                            }
                        ],
                    }
                }
            ],
        }
    ]
    events = []
    async for event in model.stream(messages=messages):
        events.append(event)
    text = ""
    for event in events:
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            text += delta["text"]
    assert "Incident Investigation Complete" in text
    assert UNGROUNDED_MARKER not in text
    assert model.grounded is True

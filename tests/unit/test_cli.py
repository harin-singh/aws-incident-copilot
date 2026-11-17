"""CLI tests, including MarkupError-prone output and live-mode guards."""

from click.testing import CliRunner

from aws_incident_copilot.cli import main


def test_demo_crashloop_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["demo", "--scenario", "crashloop", "--auto-approve"])
    assert result.exit_code == 0, result.output
    assert "tool not found" not in result.output.lower()
    assert "UNGROUNDED" not in result.output
    assert "MarkupError" not in result.output
    assert "Demo complete" in result.output
    assert "95%" in result.output
    assert "authentication failed" in result.output.lower()


def test_live_mode_requires_alert_file() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--mode", "live"])
    assert result.exit_code == 1
    assert "alert-file" in result.output


def test_scenarios_lists_all() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["scenarios"])
    assert result.exit_code == 0
    assert "crashloop" in result.output
    assert "oom" in result.output
    assert "alb-5xx" in result.output

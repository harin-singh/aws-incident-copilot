"""Tests for demo fixture data provider."""

from aws_incident_copilot.demo.fixtures import DemoDataProvider


class TestDemoDataProvider:
    """Tests for the DemoDataProvider class."""

    def test_load_crashloop_scenario(self, demo_provider_crashloop):
        """Test loading crashloop scenario data."""
        provider = demo_provider_crashloop

        pod = provider.get_pod_description(
            name="payment-service-7d4f8b9c5d-x2k9m",
            namespace="production",
        )

        assert pod["name"] == "payment-service-7d4f8b9c5d-x2k9m"
        assert pod["namespace"] == "production"
        assert len(pod["container_statuses"]) > 0

        container = pod["container_statuses"][0]
        assert container["restart_count"] == 8
        assert container["reason"] == "CrashLoopBackOff"

    def test_load_oom_scenario(self, demo_provider_oom):
        """Test loading OOM scenario data."""
        provider = demo_provider_oom

        service = provider.get_ecs_service(
            cluster="production-cluster",
            service="order-processor",
        )

        assert service["service_name"] == "order-processor"
        assert service["running_count"] < service["desired_count"]

        stopped_tasks = provider.get_stopped_tasks(
            cluster="production-cluster",
            service="order-processor",
        )

        assert len(stopped_tasks["stopped_tasks"]) > 0
        assert stopped_tasks["stopped_tasks"][0]["containers"][0]["exit_code"] == 137

    def test_load_alb_scenario(self, demo_provider_alb):
        """Test loading ALB 5xx scenario data."""
        provider = demo_provider_alb

        metrics = provider.get_cloudwatch_metrics(
            namespace="AWS/ApplicationELB",
            metric_name="HTTPCode_Target_5XX_Count",
            dimensions={},
        )

        assert "datapoints" in metrics
        assert len(metrics["datapoints"]) > 0

        alarms = provider.get_cloudwatch_alarms(state="ALARM")
        assert len(alarms["alarms"]) > 0
        assert any("5xx" in a["name"].lower() for a in alarms["alarms"])

    def test_cloudwatch_logs_query(self, demo_provider_crashloop):
        """Test CloudWatch logs query."""
        provider = demo_provider_crashloop

        logs = provider.get_cloudwatch_logs(
            log_group="/eks/production/payment-service",
            query="fields @timestamp, @message | filter @message like /error/",
        )

        assert logs["status"] == "Complete"
        assert "results" in logs

    def test_kubernetes_events(self, demo_provider_crashloop):
        """Test Kubernetes events retrieval."""
        provider = demo_provider_crashloop

        events = provider.get_kubernetes_events(
            namespace="production",
            resource_name="payment-service-7d4f8b9c5d-x2k9m",
            resource_kind="Pod",
        )

        assert "events" in events
        assert len(events["events"]) > 0
        assert any(e["reason"] == "BackOff" for e in events["events"])

    def test_pod_logs(self, demo_provider_crashloop):
        """Test pod logs retrieval."""
        provider = demo_provider_crashloop

        logs = provider.get_pod_logs(
            name="payment-service-7d4f8b9c5d-x2k9m",
            namespace="production",
            previous=True,
        )

        assert "logs" in logs
        assert "authentication failed" in logs["logs"].lower()

    def test_unknown_scenario_falls_back_to_crashloop(self):
        """Test that unknown scenarios fall back to crashloop scenario."""
        provider = DemoDataProvider(scenario="nonexistent")

        pod = provider.get_pod_description(name="test", namespace="default")
        assert pod["name"] == "payment-service-7d4f8b9c5d-x2k9m"

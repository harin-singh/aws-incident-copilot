"""Tests for demo and live remediation backends."""

from __future__ import annotations

from moto import mock_aws

from aws_incident_copilot.agents.approval import ApprovalHandler, create_remediation_tools
from aws_incident_copilot.remediation.backends import (
    DemoRemediationBackend,
    LiveECSBackend,
    LiveKubernetesBackend,
    create_remediation_backend,
)
from tests.fakes.aws import create_fargate_service
from tests.fakes.k8s import FakeAppsV1Api


def test_demo_backend_never_returns_executed() -> None:
    backend = DemoRemediationBackend()
    restart = backend.restart_deployment("pay", "production")
    rollback = backend.rollback_deployment("pay", "production")
    scale = backend.scale_ecs_service("prod", "api", 4)
    force = backend.force_ecs_deployment("prod", "api")

    assert restart["status"] == "simulated"
    assert rollback["status"] == "simulated"
    assert scale["status"] == "simulated"
    assert force["status"] == "simulated"
    assert all(item["status"] != "executed" for item in (restart, rollback, scale, force))
    assert backend.deployments[("production", "pay")]["revision"] == 1
    assert backend.ecs_services[("prod", "api")]["desired_count"] == 4


def test_demo_backend_dry_run() -> None:
    backend = DemoRemediationBackend()
    result = backend.restart_deployment("pay", "production", dry_run=True)
    assert result["status"] == "dry_run"
    assert ("production", "pay") not in backend.deployments
    assert backend.rollback_deployment("pay", "production", dry_run=True)["status"] == "dry_run"
    assert backend.scale_ecs_service("prod", "api", 2, dry_run=True)["status"] == "dry_run"
    assert backend.force_ecs_deployment("prod", "api", dry_run=True)["status"] == "dry_run"


def test_approved_demo_tools_return_simulated() -> None:
    handler = ApprovalHandler(auto_approve=True)
    backend = DemoRemediationBackend()
    tools = create_remediation_tools(handler, backend=backend)
    result = tools[0](name="pay", namespace="production")
    assert result["status"] == "simulated"
    assert result["backend"] == "demo"
    assert result["approval"]["decision"] == "approved"


def test_live_kubernetes_restart_and_rollback() -> None:
    apps = FakeAppsV1Api()
    apps.add_deployment("pay", "production", generation=4)
    backend = LiveKubernetesBackend(apps_api=apps)

    dry = backend.restart_deployment("pay", "production", dry_run=True)
    assert dry["status"] == "dry_run"

    restarted = backend.restart_deployment("pay", "production")
    assert restarted["status"] == "executed"
    assert restarted["backend"] == "kubernetes"
    assert apps.patches
    assert "kubectl.kubernetes.io/restartedAt" in str(apps.patches[0]["body"])

    rolled = backend.rollback_deployment("pay", "production")
    assert rolled["status"] == "executed"
    assert rolled["revision"] == 1


@mock_aws
def test_live_ecs_scale_and_force() -> None:
    ecs = create_fargate_service("us-west-2")
    backend = LiveECSBackend(ecs_client=ecs, region="us-west-2")
    dry = backend.scale_ecs_service("prod", "api", 3, dry_run=True)
    assert dry["status"] == "dry_run"

    scaled = backend.scale_ecs_service("prod", "api", 3)
    assert scaled["status"] == "executed"
    assert scaled["desired_count"] == 3

    forced = backend.force_ecs_deployment("prod", "api")
    assert forced["status"] == "executed"

    missing = backend.scale_ecs_service("prod", "nope", 2)
    assert missing["status"] == "failed"


@mock_aws
def test_live_ecs_assumes_remediation_role() -> None:
    import json

    import boto3

    iam = boto3.client("iam", region_name="us-west-2")
    iam.create_role(
        RoleName="remediation",
        AssumeRolePolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "sts:AssumeRole"}
                ],
            }
        ),
    )
    ecs = create_fargate_service("us-west-2")
    role_arn = iam.get_role(RoleName="remediation")["Role"]["Arn"]
    backend = LiveECSBackend(
        ecs_client=None,
        sts_client=boto3.client("sts", region_name="us-west-2"),
        session=boto3,
        remediation_role_arn=role_arn,
        external_id="x-account",
        region="us-west-2",
    )
    # Inject the already-populated ECS client after assume-role wiring is exercised.
    client = backend._client()
    assert backend.assumed_credentials is not None
    backend._ecs_client = ecs
    result = backend.scale_ecs_service("prod", "api", 2, dry_run=True)
    assert result["status"] == "dry_run"
    assert client is not None


def test_create_remediation_backend_demo_vs_live() -> None:
    demo = create_remediation_backend(demo_mode=True)
    assert isinstance(demo, DemoRemediationBackend)
    live = create_remediation_backend(demo_mode=False, apps_api=FakeAppsV1Api())
    assert live.kubernetes.restart_deployment  # type: ignore[union-attr]

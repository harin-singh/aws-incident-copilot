"""Remediation backends for Kubernetes and ECS.

Demo backends simulate mutations against in-memory fixture state and never
report ``executed``. Live backends call the Kubernetes API or boto3 ECS,
optionally after assuming a dedicated remediation role.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aws_incident_copilot.demo.fixtures import DemoDataProvider  # noqa: TC001


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DemoRemediationBackend:
    """In-memory backend used by demo mode and tests.

    Records every attempted action and updates fixture-like state. Status is
    always ``simulated`` or ``dry_run``, never ``executed``.
    """

    def __init__(self, provider: DemoDataProvider | None = None):
        self.provider = provider
        self.actions: list[dict[str, Any]] = []
        self.deployments: dict[tuple[str, str], dict[str, Any]] = {}
        self.ecs_services: dict[tuple[str, str], dict[str, Any]] = {}

    def _record(self, action: str, **details: Any) -> dict[str, Any]:
        entry = {"action": action, "timestamp": _now(), **details}
        self.actions.append(entry)
        return entry

    def restart_deployment(
        self,
        name: str,
        namespace: str = "default",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Simulate a kubectl rollout restart against demo state."""
        key = (namespace, name)
        if dry_run:
            self._record("restart_deployment", name=name, namespace=namespace, dry_run=True)
            return {
                "status": "dry_run",
                "backend": "demo",
                "action": f"Would restart deployment {name} in {namespace}",
                "resource": f"deployment/{namespace}/{name}",
            }

        self.deployments[key] = {
            "name": name,
            "namespace": namespace,
            "restarted_at": _now(),
            "revision": self.deployments.get(key, {}).get("revision", 1) + 1,
        }
        self._record("restart_deployment", name=name, namespace=namespace, dry_run=False)
        return {
            "status": "simulated",
            "backend": "demo",
            "action": f"Simulated restart of deployment {name} in {namespace}",
            "resource": f"deployment/{namespace}/{name}",
            "state": self.deployments[key],
        }

    def rollback_deployment(
        self,
        name: str,
        namespace: str = "default",
        revision: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Simulate a kubectl rollout undo against demo state."""
        key = (namespace, name)
        target = (
            revision
            if revision is not None
            else max(self.deployments.get(key, {}).get("revision", 2) - 1, 1)
        )
        if dry_run:
            self._record(
                "rollback_deployment",
                name=name,
                namespace=namespace,
                revision=target,
                dry_run=True,
            )
            return {
                "status": "dry_run",
                "backend": "demo",
                "action": f"Would roll back deployment {name} to revision {target}",
                "resource": f"deployment/{namespace}/{name}",
                "revision": target,
            }

        self.deployments[key] = {
            "name": name,
            "namespace": namespace,
            "rolled_back_at": _now(),
            "revision": target,
        }
        self._record(
            "rollback_deployment",
            name=name,
            namespace=namespace,
            revision=target,
            dry_run=False,
        )
        return {
            "status": "simulated",
            "backend": "demo",
            "action": f"Simulated rollback of deployment {name} to revision {target}",
            "resource": f"deployment/{namespace}/{name}",
            "state": self.deployments[key],
        }

    def scale_ecs_service(
        self,
        cluster: str,
        service: str,
        desired_count: int,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Simulate ecs update-service --desired-count against demo state."""
        key = (cluster, service)
        if dry_run:
            self._record(
                "scale_ecs_service",
                cluster=cluster,
                service=service,
                desired_count=desired_count,
                dry_run=True,
            )
            return {
                "status": "dry_run",
                "backend": "demo",
                "action": f"Would scale {service} to {desired_count} tasks",
                "resource": f"ecs/{cluster}/{service}",
                "desired_count": desired_count,
            }

        previous = self.ecs_services.get(key, {}).get("desired_count")
        self.ecs_services[key] = {
            "cluster": cluster,
            "service": service,
            "desired_count": desired_count,
            "previous_desired_count": previous,
            "updated_at": _now(),
        }
        self._record(
            "scale_ecs_service",
            cluster=cluster,
            service=service,
            desired_count=desired_count,
            dry_run=False,
        )
        return {
            "status": "simulated",
            "backend": "demo",
            "action": f"Simulated scale of {service} to {desired_count} tasks",
            "resource": f"ecs/{cluster}/{service}",
            "state": self.ecs_services[key],
        }

    def force_ecs_deployment(
        self,
        cluster: str,
        service: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Simulate ecs update-service --force-new-deployment against demo state."""
        key = (cluster, service)
        if dry_run:
            self._record("force_ecs_deployment", cluster=cluster, service=service, dry_run=True)
            return {
                "status": "dry_run",
                "backend": "demo",
                "action": f"Would force a new deployment for {service}",
                "resource": f"ecs/{cluster}/{service}",
            }

        current = self.ecs_services.get(key, {})
        self.ecs_services[key] = {
            **current,
            "cluster": cluster,
            "service": service,
            "force_new_deployment": True,
            "redeployed_at": _now(),
        }
        self._record("force_ecs_deployment", cluster=cluster, service=service, dry_run=False)
        return {
            "status": "simulated",
            "backend": "demo",
            "action": f"Simulated force-new-deployment for {service}",
            "resource": f"ecs/{cluster}/{service}",
            "state": self.ecs_services[key],
        }


class LiveKubernetesBackend:
    """Execute deployment remediations via the Kubernetes API."""

    def __init__(
        self,
        apps_api: Any = None,
        kubeconfig_path: str | None = None,
        cluster_name: str | None = None,
        session: Any = None,
        sts_client: Any = None,
        remediation_role_arn: str | None = None,
        external_id: str | None = None,
        region: str = "us-west-2",
    ):
        self._apps_api = apps_api
        self.kubeconfig_path = kubeconfig_path
        self.cluster_name = cluster_name
        self.session = session
        self.sts_client = sts_client
        self.remediation_role_arn = remediation_role_arn
        self.external_id = external_id
        self.region = region
        self.assumed_credentials: dict[str, Any] | None = None

    def _assume_role(self) -> dict[str, Any] | None:
        if not self.remediation_role_arn:
            return self.assumed_credentials
        if self.assumed_credentials is not None:
            return self.assumed_credentials

        sts = self.sts_client
        if sts is None:
            session = self.session
            if session is None:
                import boto3

                session = boto3
            sts = session.client("sts", region_name=self.region)

        kwargs: dict[str, Any] = {
            "RoleArn": self.remediation_role_arn,
            "RoleSessionName": "incident-copilot-remediation",
        }
        if self.external_id:
            kwargs["ExternalId"] = self.external_id
        self.assumed_credentials = sts.assume_role(**kwargs)["Credentials"]
        return self.assumed_credentials

    def _apps(self) -> Any:
        if self._apps_api is not None:
            return self._apps_api

        self._assume_role()
        from kubernetes import client, config

        if self.kubeconfig_path:
            config.load_kube_config(config_file=self.kubeconfig_path)
        else:
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()
        self._apps_api = client.AppsV1Api()
        return self._apps_api

    def restart_deployment(
        self,
        name: str,
        namespace: str = "default",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Patch the deployment pod-template annotation to trigger a rollout."""
        apps = self._apps()
        deployment = apps.read_namespaced_deployment(name=name, namespace=namespace)
        restarted_at = _now()
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": restarted_at,
                        }
                    }
                }
            }
        }
        if dry_run:
            return {
                "status": "dry_run",
                "backend": "kubernetes",
                "action": f"Would restart deployment {name} in {namespace}",
                "resource": f"deployment/{namespace}/{name}",
                "generation": getattr(deployment.metadata, "generation", None),
            }

        updated = apps.patch_namespaced_deployment(name=name, namespace=namespace, body=patch)
        return {
            "status": "executed",
            "backend": "kubernetes",
            "action": f"Restarted deployment {name}",
            "resource": f"deployment/{namespace}/{name}",
            "restarted_at": restarted_at,
            "generation": getattr(updated.metadata, "generation", None),
        }

    def rollback_deployment(
        self,
        name: str,
        namespace: str = "default",
        revision: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Roll a deployment back to a previous ReplicaSet revision."""
        apps = self._apps()
        current = apps.read_namespaced_deployment(name=name, namespace=namespace)
        rs_list = apps.list_namespaced_replica_set(namespace=namespace)

        candidates: list[tuple[int, Any]] = []
        for rs in rs_list.items:
            owners = getattr(rs.metadata, "owner_references", None) or []
            owned = any(
                getattr(ref, "kind", None) == "Deployment" and ref.name == name for ref in owners
            )
            if not owned:
                continue
            annotations = getattr(rs.metadata, "annotations", None) or {}
            rev_raw = annotations.get("deployment.kubernetes.io/revision")
            if rev_raw is None:
                continue
            candidates.append((int(rev_raw), rs))

        if not candidates:
            return {
                "status": "failed",
                "backend": "kubernetes",
                "action": f"No ReplicaSet history for {name}",
                "resource": f"deployment/{namespace}/{name}",
            }

        candidates.sort(key=lambda item: item[0], reverse=True)
        if revision is None:
            # Skip the current (highest) revision when possible.
            target_rev, target_rs = candidates[1] if len(candidates) > 1 else candidates[0]
        else:
            match = next((item for item in candidates if item[0] == revision), None)
            if match is None:
                return {
                    "status": "failed",
                    "backend": "kubernetes",
                    "action": f"Revision {revision} not found for {name}",
                    "resource": f"deployment/{namespace}/{name}",
                }
            target_rev, target_rs = match

        patch = {"spec": {"template": target_rs.spec.template}}
        if dry_run:
            return {
                "status": "dry_run",
                "backend": "kubernetes",
                "action": f"Would roll back deployment {name} to revision {target_rev}",
                "resource": f"deployment/{namespace}/{name}",
                "revision": target_rev,
                "current_generation": getattr(current.metadata, "generation", None),
            }

        updated = apps.patch_namespaced_deployment(name=name, namespace=namespace, body=patch)
        return {
            "status": "executed",
            "backend": "kubernetes",
            "action": f"Rolled back deployment {name}",
            "resource": f"deployment/{namespace}/{name}",
            "revision": target_rev,
            "generation": getattr(updated.metadata, "generation", None),
        }


class LiveECSBackend:
    """Execute ECS remediations via boto3, optionally under a remediation role."""

    def __init__(
        self,
        ecs_client: Any = None,
        sts_client: Any = None,
        session: Any = None,
        remediation_role_arn: str | None = None,
        external_id: str | None = None,
        region: str = "us-west-2",
    ):
        self._ecs_client = ecs_client
        self.sts_client = sts_client
        self.session = session
        self.remediation_role_arn = remediation_role_arn
        self.external_id = external_id
        self.region = region
        self.assumed_credentials: dict[str, Any] | None = None

    def _client(self) -> Any:
        if self._ecs_client is not None:
            return self._ecs_client

        session = self.session
        if session is None:
            import boto3

            session = boto3

        if self.remediation_role_arn:
            sts = self.sts_client or session.client("sts", region_name=self.region)
            kwargs: dict[str, Any] = {
                "RoleArn": self.remediation_role_arn,
                "RoleSessionName": "incident-copilot-remediation",
            }
            if self.external_id:
                kwargs["ExternalId"] = self.external_id
            creds = sts.assume_role(**kwargs)["Credentials"]
            self.assumed_credentials = creds
            self._ecs_client = session.client(
                "ecs",
                region_name=self.region,
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
            )
            return self._ecs_client

        self._ecs_client = session.client("ecs", region_name=self.region)
        return self._ecs_client

    def scale_ecs_service(
        self,
        cluster: str,
        service: str,
        desired_count: int,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Update an ECS service desired count."""
        client = self._client()
        described = client.describe_services(cluster=cluster, services=[service])
        if not described.get("services"):
            return {
                "status": "failed",
                "backend": "ecs",
                "action": f"Service {service} not found in {cluster}",
                "resource": f"ecs/{cluster}/{service}",
            }

        current = described["services"][0]["desiredCount"]
        if dry_run:
            return {
                "status": "dry_run",
                "backend": "ecs",
                "action": f"Would scale {service} from {current} to {desired_count} tasks",
                "resource": f"ecs/{cluster}/{service}",
                "current_desired_count": current,
                "desired_count": desired_count,
            }

        response = client.update_service(
            cluster=cluster,
            service=service,
            desiredCount=desired_count,
        )
        updated = response["service"]
        return {
            "status": "executed",
            "backend": "ecs",
            "action": f"Scaled {service} to {desired_count} tasks",
            "resource": f"ecs/{cluster}/{service}",
            "desired_count": updated.get("desiredCount", desired_count),
            "running_count": updated.get("runningCount"),
        }

    def force_ecs_deployment(
        self,
        cluster: str,
        service: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Force a new ECS deployment so tasks are replaced."""
        client = self._client()
        described = client.describe_services(cluster=cluster, services=[service])
        if not described.get("services"):
            return {
                "status": "failed",
                "backend": "ecs",
                "action": f"Service {service} not found in {cluster}",
                "resource": f"ecs/{cluster}/{service}",
            }

        if dry_run:
            return {
                "status": "dry_run",
                "backend": "ecs",
                "action": f"Would force a new deployment for {service}",
                "resource": f"ecs/{cluster}/{service}",
            }

        response = client.update_service(
            cluster=cluster,
            service=service,
            forceNewDeployment=True,
        )
        updated = response["service"]
        return {
            "status": "executed",
            "backend": "ecs",
            "action": f"Forced new deployment for {service}",
            "resource": f"ecs/{cluster}/{service}",
            "desired_count": updated.get("desiredCount"),
            "running_count": updated.get("runningCount"),
        }


class CompositeRemediationBackend:
    """Route Kubernetes vs ECS remediations to the matching backend."""

    def __init__(self, kubernetes: LiveKubernetesBackend, ecs: LiveECSBackend):
        self.kubernetes = kubernetes
        self.ecs = ecs

    def restart_deployment(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.kubernetes.restart_deployment(*args, **kwargs)

    def rollback_deployment(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.kubernetes.rollback_deployment(*args, **kwargs)

    def scale_ecs_service(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.ecs.scale_ecs_service(*args, **kwargs)

    def force_ecs_deployment(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.ecs.force_ecs_deployment(*args, **kwargs)


def create_remediation_backend(
    *,
    demo_mode: bool = True,
    demo_provider: DemoDataProvider | None = None,
    apps_api: Any = None,
    ecs_client: Any = None,
    sts_client: Any = None,
    session: Any = None,
    kubeconfig_path: str | None = None,
    cluster_name: str | None = None,
    remediation_role_arn: str | None = None,
    external_id: str | None = None,
    region: str = "us-west-2",
) -> DemoRemediationBackend | CompositeRemediationBackend:
    """Build a demo or live remediation backend."""
    if demo_mode:
        return DemoRemediationBackend(provider=demo_provider)

    return CompositeRemediationBackend(
        kubernetes=LiveKubernetesBackend(
            apps_api=apps_api,
            kubeconfig_path=kubeconfig_path,
            cluster_name=cluster_name,
            session=session,
            sts_client=sts_client,
            remediation_role_arn=remediation_role_arn,
            external_id=external_id,
            region=region,
        ),
        ecs=LiveECSBackend(
            ecs_client=ecs_client,
            sts_client=sts_client,
            session=session,
            remediation_role_arn=remediation_role_arn,
            external_id=external_id,
            region=region,
        ),
    )

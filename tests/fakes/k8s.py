"""In-memory Kubernetes API doubles used by unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any


def _now() -> datetime:
    return datetime.now(UTC)


def _ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


class FakeKubernetesError(Exception):
    """Raised when a fake API object is missing."""


class FakeCoreV1Api:
    """Subset of CoreV1Api used by investigation tools."""

    def __init__(self) -> None:
        self.pods: dict[tuple[str, str], Any] = {}
        self.events: list[Any] = []
        self.nodes: dict[str, Any] = {}
        self.pod_logs: dict[tuple[str, str, bool], str] = {}

    def add_pod(
        self,
        name: str,
        namespace: str = "default",
        *,
        phase: str = "Running",
        restart_count: int = 0,
        waiting_reason: str | None = "CrashLoopBackOff",
        logs: str = "ready",
        previous_logs: str = "error",
    ) -> None:
        container_state = _ns(
            running=None,
            waiting=_ns(reason=waiting_reason, message="back-off") if waiting_reason else None,
            terminated=None,
        )
        pod = _ns(
            metadata=_ns(
                name=name,
                namespace=namespace,
                creation_timestamp=_now(),
                labels={"app": name},
            ),
            spec=_ns(
                node_name="ip-10-0-1-1",
                containers=[
                    _ns(
                        name=name,
                        resources=_ns(requests={"cpu": "100m"}, limits={"cpu": "200m"}),
                    )
                ],
            ),
            status=_ns(
                phase=phase,
                container_statuses=[
                    _ns(
                        name=name,
                        ready=False,
                        restart_count=restart_count,
                        image="example/app:1",
                        state=container_state,
                        last_state=_ns(
                            terminated=_ns(reason="Error", exit_code=1, finished_at=_now())
                        ),
                    )
                ],
                conditions=[
                    _ns(
                        type="Ready",
                        status="False",
                        reason="ContainersNotReady",
                        message="not ready",
                        last_transition_time=_now(),
                    )
                ],
            ),
        )
        self.pods[(namespace, name)] = pod
        self.pod_logs[(namespace, name, False)] = logs
        self.pod_logs[(namespace, name, True)] = previous_logs

    def add_event(self, name: str, namespace: str, reason: str, message: str) -> None:
        self.events.append(
            _ns(
                type="Warning",
                reason=reason,
                message=message,
                count=1,
                first_timestamp=_now(),
                last_timestamp=_now(),
                source=_ns(component="kubelet"),
                involved_object=_ns(kind="Pod", name=name),
            )
        )

    def add_node(self, name: str) -> None:
        self.nodes[name] = _ns(
            metadata=_ns(name=name, labels={"node": name}),
            status=_ns(
                conditions=[
                    _ns(
                        type="Ready",
                        status="True",
                        reason="KubeletReady",
                        message="ok",
                        last_heartbeat_time=_now(),
                    )
                ],
                capacity={"cpu": "4", "memory": "8Gi"},
                allocatable={"cpu": "4", "memory": "8Gi"},
                node_info=_ns(
                    os_image="Amazon Linux",
                    kernel_version="6.1",
                    container_runtime_version="containerd://1.7",
                    kubelet_version="v1.31.0",
                ),
            ),
        )

    def read_namespaced_pod(self, name: str, namespace: str) -> Any:
        try:
            return self.pods[(namespace, name)]
        except KeyError as exc:
            raise FakeKubernetesError(f"pod {namespace}/{name} not found") from exc

    def list_namespaced_event(
        self,
        namespace: str,
        field_selector: str | None = None,
        limit: int = 50,
    ) -> Any:
        items = list(self.events)
        if field_selector and "involvedObject.name=" in field_selector:
            want = field_selector.split("involvedObject.name=")[1].split(",")[0]
            items = [e for e in items if e.involved_object.name == want]
        return _ns(items=items[:limit])

    def list_namespaced_pod(
        self,
        namespace: str,
        label_selector: str | None = None,
        field_selector: str | None = None,
    ) -> Any:
        items = [pod for (ns, _name), pod in self.pods.items() if ns == namespace]
        return _ns(items=items)

    def read_namespaced_pod_log(
        self,
        name: str,
        namespace: str,
        container: str | None = None,
        previous: bool = False,
        tail_lines: int = 100,
    ) -> str:
        return self.pod_logs.get((namespace, name, previous), "")

    def read_node(self, name: str) -> Any:
        try:
            return self.nodes[name]
        except KeyError as exc:
            raise FakeKubernetesError(f"node {name} not found") from exc


class FakeAppsV1Api:
    """Subset of AppsV1Api used by investigation and remediation tools."""

    def __init__(self) -> None:
        self.deployments: dict[tuple[str, str], Any] = {}
        self.replicasets: list[Any] = []
        self.patches: list[dict[str, Any]] = []

    def add_deployment(self, name: str, namespace: str = "default", generation: int = 1) -> None:
        self.deployments[(namespace, name)] = _ns(
            metadata=_ns(
                name=name,
                namespace=namespace,
                generation=generation,
                creation_timestamp=_now(),
            ),
            spec=_ns(
                replicas=3,
                strategy=_ns(type="RollingUpdate"),
                selector=_ns(match_labels={"app": name}),
                template=_ns(spec=_ns(containers=[_ns(image="example/app:2")])),
            ),
            status=_ns(
                ready_replicas=2,
                available_replicas=2,
                updated_replicas=2,
                observed_generation=generation,
                conditions=[
                    _ns(
                        type="Available",
                        status="True",
                        reason="MinimumReplicasAvailable",
                        message="ok",
                        last_update_time=_now(),
                    )
                ],
            ),
        )
        self.replicasets.extend(
            [
                _ns(
                    metadata=_ns(
                        name=f"{name}-prev",
                        owner_references=[_ns(kind="Deployment", name=name)],
                        annotations={"deployment.kubernetes.io/revision": "1"},
                        creation_timestamp=_now(),
                    ),
                    spec=_ns(
                        replicas=0,
                        template=_ns(spec=_ns(containers=[_ns(image="example/app:1")])),
                    ),
                    status=_ns(ready_replicas=0, available_replicas=0),
                ),
                _ns(
                    metadata=_ns(
                        name=f"{name}-curr",
                        owner_references=[_ns(kind="Deployment", name=name)],
                        annotations={"deployment.kubernetes.io/revision": "2"},
                        creation_timestamp=_now(),
                    ),
                    spec=_ns(
                        replicas=3,
                        template=_ns(spec=_ns(containers=[_ns(image="example/app:2")])),
                    ),
                    status=_ns(ready_replicas=2, available_replicas=2),
                ),
            ]
        )

    def read_namespaced_deployment(self, name: str, namespace: str) -> Any:
        try:
            return self.deployments[(namespace, name)]
        except KeyError as exc:
            raise FakeKubernetesError(f"deployment {namespace}/{name} not found") from exc

    def list_namespaced_replica_set(self, namespace: str) -> Any:
        return _ns(items=list(self.replicasets))

    def patch_namespaced_deployment(self, name: str, namespace: str, body: dict[str, Any]) -> Any:
        self.patches.append({"name": name, "namespace": namespace, "body": body})
        current = self.read_namespaced_deployment(name, namespace)
        current.metadata.generation = (current.metadata.generation or 1) + 1
        return current

"""Kubernetes MCP Server for EKS cluster investigation.

This MCP server provides tools for investigating Kubernetes resources,
events, and pod states in EKS clusters. In demo mode, it returns fixture
data. In live mode, it queries the Kubernetes API.
"""

from datetime import UTC, datetime
from typing import Any

from mcp.server.mcpserver import MCPServer

from aws_incident_copilot.demo.fixtures import DemoDataProvider


def create_kubernetes_server(
    demo_mode: bool = True,
    demo_provider: DemoDataProvider | None = None,
    kubeconfig_path: str | None = None,
) -> MCPServer:
    """Create a Kubernetes MCP server.

    Args:
        demo_mode: If True, return fixture data instead of querying K8s.
        demo_provider: Provider for demo fixture data.
        kubeconfig_path: Path to kubeconfig for live mode.

    Returns:
        Configured MCPServer instance.
    """
    server = MCPServer(
        name="kubernetes-tools",
        title="Kubernetes Investigation Tools",
        description="Tools for investigating Kubernetes pods, events, and deployments in EKS",
        version="1.0.0",
    )

    provider = demo_provider or DemoDataProvider()

    @server.tool(
        description="Get detailed information about a pod, including status, containers, "
        "conditions, and recent events. Essential for investigating pod failures."
    )
    def describe_pod(
        name: str,
        namespace: str = "default",
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """Get detailed pod information."""
        if demo_mode:
            return provider.get_pod_description(
                name=name,
                namespace=namespace,
            )

        # Live mode implementation
        from kubernetes import client, config

        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()

        v1 = client.CoreV1Api()
        pod = v1.read_namespaced_pod(name=name, namespace=namespace)

        container_statuses = []
        for cs in pod.status.container_statuses or []:
            status_info = {
                "name": cs.name,
                "ready": cs.ready,
                "restart_count": cs.restart_count,
                "image": cs.image,
            }
            if cs.state.running:
                status_info["state"] = "Running"
                status_info["started_at"] = cs.state.running.started_at.isoformat()
            elif cs.state.waiting:
                status_info["state"] = "Waiting"
                status_info["reason"] = cs.state.waiting.reason
                status_info["message"] = cs.state.waiting.message
            elif cs.state.terminated:
                status_info["state"] = "Terminated"
                status_info["reason"] = cs.state.terminated.reason
                status_info["exit_code"] = cs.state.terminated.exit_code

            if cs.last_state and cs.last_state.terminated:
                status_info["last_termination"] = {
                    "reason": cs.last_state.terminated.reason,
                    "exit_code": cs.last_state.terminated.exit_code,
                    "finished_at": cs.last_state.terminated.finished_at.isoformat()
                    if cs.last_state.terminated.finished_at
                    else None,
                }

            container_statuses.append(status_info)

        conditions = [
            {
                "type": c.type,
                "status": c.status,
                "reason": c.reason,
                "message": c.message,
                "last_transition": c.last_transition_time.isoformat()
                if c.last_transition_time
                else None,
            }
            for c in pod.status.conditions or []
        ]

        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "created": pod.metadata.creation_timestamp.isoformat(),
            "labels": pod.metadata.labels or {},
            "container_statuses": container_statuses,
            "conditions": conditions,
            "resource_requests": _extract_resources(pod, "requests"),
            "resource_limits": _extract_resources(pod, "limits"),
        }

    @server.tool(
        description="Get Kubernetes events for a resource or namespace. Events show "
        "scheduling failures, OOM kills, image pull errors, and other issues."
    )
    def get_events(
        namespace: str = "default",
        resource_name: str | None = None,
        resource_kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get Kubernetes events."""
        if demo_mode:
            return provider.get_kubernetes_events(
                namespace=namespace,
                resource_name=resource_name,
                resource_kind=resource_kind,
            )

        # Live mode implementation
        from kubernetes import client, config

        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()

        v1 = client.CoreV1Api()

        field_selector = None
        if resource_name and resource_kind:
            field_selector = (
                f"involvedObject.name={resource_name},involvedObject.kind={resource_kind}"
            )
        elif resource_name:
            field_selector = f"involvedObject.name={resource_name}"

        events_list = v1.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector,
            limit=limit,
        )

        events = [
            {
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "count": e.count,
                "first_seen": e.first_timestamp.isoformat() if e.first_timestamp else None,
                "last_seen": e.last_timestamp.isoformat() if e.last_timestamp else None,
                "source": e.source.component if e.source else None,
                "involved_object": {
                    "kind": e.involved_object.kind,
                    "name": e.involved_object.name,
                }
                if e.involved_object
                else None,
            }
            for e in sorted(
                events_list.items,
                key=lambda x: (
                    x.last_timestamp or x.first_timestamp or datetime.min.replace(tzinfo=UTC)
                ),
                reverse=True,
            )
        ]

        return {"events": events}

    @server.tool(
        description="List pods in a namespace with optional label selector. Use this to "
        "find pods matching specific criteria or to see overall namespace health."
    )
    def list_pods(
        namespace: str = "default",
        label_selector: str | None = None,
        field_selector: str | None = None,
    ) -> dict[str, Any]:
        """List pods in a namespace."""
        if demo_mode:
            return provider.list_pods(
                namespace=namespace,
                label_selector=label_selector,
            )

        # Live mode implementation
        from kubernetes import client, config

        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()

        v1 = client.CoreV1Api()
        pods_list = v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
            field_selector=field_selector,
        )

        pods = [
            {
                "name": p.metadata.name,
                "phase": p.status.phase,
                "ready": _pod_ready(p),
                "restarts": sum(
                    (cs.restart_count or 0) for cs in (p.status.container_statuses or [])
                ),
                "age": p.metadata.creation_timestamp.isoformat(),
                "node": p.spec.node_name,
            }
            for p in pods_list.items
        ]

        return {"pods": pods}

    @server.tool(
        description="Get deployment details including replica status, strategy, and "
        "conditions. Use this to check deployment health and recent rollouts."
    )
    def describe_deployment(
        name: str,
        namespace: str = "default",
    ) -> dict[str, Any]:
        """Get deployment details."""
        if demo_mode:
            return provider.get_deployment_description(
                name=name,
                namespace=namespace,
            )

        # Live mode implementation
        from kubernetes import client, config

        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()

        apps_v1 = client.AppsV1Api()
        deployment = apps_v1.read_namespaced_deployment(name=name, namespace=namespace)

        conditions = [
            {
                "type": c.type,
                "status": c.status,
                "reason": c.reason,
                "message": c.message,
                "last_update": c.last_update_time.isoformat() if c.last_update_time else None,
            }
            for c in deployment.status.conditions or []
        ]

        return {
            "name": deployment.metadata.name,
            "namespace": deployment.metadata.namespace,
            "replicas": {
                "desired": deployment.spec.replicas,
                "ready": deployment.status.ready_replicas or 0,
                "available": deployment.status.available_replicas or 0,
                "updated": deployment.status.updated_replicas or 0,
            },
            "strategy": deployment.spec.strategy.type if deployment.spec.strategy else None,
            "selector": deployment.spec.selector.match_labels if deployment.spec.selector else {},
            "conditions": conditions,
            "created": deployment.metadata.creation_timestamp.isoformat(),
            "generation": deployment.metadata.generation,
            "observed_generation": deployment.status.observed_generation,
        }

    @server.tool(
        description="Get recent ReplicaSet history for a deployment. Useful for tracking "
        "rollout history and identifying when issues started."
    )
    def list_replicasets(
        namespace: str = "default",
        deployment_name: str | None = None,
    ) -> dict[str, Any]:
        """List ReplicaSets, optionally filtered by deployment."""
        if demo_mode:
            return provider.list_replicasets(
                namespace=namespace,
                deployment_name=deployment_name,
            )

        # Live mode implementation
        from kubernetes import client, config

        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()

        apps_v1 = client.AppsV1Api()
        rs_list = apps_v1.list_namespaced_replica_set(namespace=namespace)

        replicasets = []
        for rs in rs_list.items:
            # Filter by deployment if specified
            if deployment_name:
                owner_refs = rs.metadata.owner_references or []
                is_owned = any(
                    ref.kind == "Deployment" and ref.name == deployment_name for ref in owner_refs
                )
                if not is_owned:
                    continue

            replicasets.append(
                {
                    "name": rs.metadata.name,
                    "replicas": {
                        "desired": rs.spec.replicas,
                        "ready": rs.status.ready_replicas or 0,
                        "available": rs.status.available_replicas or 0,
                    },
                    "created": rs.metadata.creation_timestamp.isoformat(),
                    "revision": rs.metadata.annotations.get(
                        "deployment.kubernetes.io/revision", "unknown"
                    )
                    if rs.metadata.annotations
                    else "unknown",
                }
            )

        return {"replicasets": sorted(replicasets, key=lambda x: x["created"], reverse=True)}

    @server.tool(
        description="Get container logs from a pod. Essential for debugging application "
        "errors and crashes. Can get logs from previous container instance after restarts."
    )
    def get_pod_logs(
        name: str,
        namespace: str = "default",
        container: str | None = None,
        previous: bool = False,
        tail_lines: int = 100,
    ) -> dict[str, Any]:
        """Get logs from a pod container."""
        if demo_mode:
            return provider.get_pod_logs(
                name=name,
                namespace=namespace,
                container=container,
                previous=previous,
            )

        # Live mode implementation
        from kubernetes import client, config

        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()

        v1 = client.CoreV1Api()

        logs = v1.read_namespaced_pod_log(
            name=name,
            namespace=namespace,
            container=container,
            previous=previous,
            tail_lines=tail_lines,
        )

        return {
            "pod": name,
            "namespace": namespace,
            "container": container or "default",
            "previous": previous,
            "logs": logs,
        }

    @server.tool(
        description="Get node information and conditions. Use this to check if node "
        "issues (memory pressure, disk pressure) are causing pod problems."
    )
    def describe_node(
        name: str,
    ) -> dict[str, Any]:
        """Get node details."""
        if demo_mode:
            return provider.get_node_description(name=name)

        # Live mode implementation
        from kubernetes import client, config

        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path)
        else:
            config.load_incluster_config()

        v1 = client.CoreV1Api()
        node = v1.read_node(name=name)

        conditions = [
            {
                "type": c.type,
                "status": c.status,
                "reason": c.reason,
                "message": c.message,
                "last_heartbeat": c.last_heartbeat_time.isoformat()
                if c.last_heartbeat_time
                else None,
            }
            for c in node.status.conditions or []
        ]

        allocatable = node.status.allocatable or {}
        capacity = node.status.capacity or {}

        return {
            "name": node.metadata.name,
            "labels": node.metadata.labels or {},
            "conditions": conditions,
            "capacity": dict(capacity.items()),
            "allocatable": dict(allocatable.items()),
            "info": {
                "os": node.status.node_info.os_image if node.status.node_info else None,
                "kernel": node.status.node_info.kernel_version if node.status.node_info else None,
                "container_runtime": node.status.node_info.container_runtime_version
                if node.status.node_info
                else None,
                "kubelet": node.status.node_info.kubelet_version if node.status.node_info else None,
            },
        }

    return server


def _extract_resources(pod: Any, resource_type: str) -> dict[str, Any]:
    """Extract resource requests or limits from a pod."""
    result: dict[str, Any] = {}
    for container in pod.spec.containers or []:
        if container.resources:
            resources = getattr(container.resources, resource_type, None) or {}
            result[container.name] = dict(resources)
    return result


def _pod_ready(pod: Any) -> bool:
    """Check if a pod is ready."""
    for condition in pod.status.conditions or []:
        if condition.type == "Ready":
            return bool(condition.status == "True")
    return False

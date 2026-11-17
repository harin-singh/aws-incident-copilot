"""Kubernetes investigation tools (Strands @tool wrappers + shared impl)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from strands import tool

from aws_incident_copilot.tools.context import InvestigationContext  # noqa: TC001


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


def describe_pod_impl(
    ctx: InvestigationContext,
    name: str,
    namespace: str = "default",
    cluster: str | None = None,
) -> dict[str, Any]:
    """Get detailed pod information."""
    if ctx.demo_mode:
        return ctx.provider().get_pod_description(name=name, namespace=namespace)

    core, _ = ctx.kubernetes_apis()
    pod = core.read_namespaced_pod(name=name, namespace=namespace)

    container_statuses = []
    for cs in pod.status.container_statuses or []:
        status_info: dict[str, Any] = {
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
            finished = cs.last_state.terminated.finished_at
            status_info["last_termination"] = {
                "reason": cs.last_state.terminated.reason,
                "exit_code": cs.last_state.terminated.exit_code,
                "finished_at": finished.isoformat() if finished else None,
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
        "cluster": cluster,
    }


def get_events_impl(
    ctx: InvestigationContext,
    namespace: str = "default",
    resource_name: str | None = None,
    resource_kind: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Get Kubernetes events."""
    if ctx.demo_mode:
        return ctx.provider().get_kubernetes_events(
            namespace=namespace,
            resource_name=resource_name,
            resource_kind=resource_kind,
        )

    core, _ = ctx.kubernetes_apis()
    field_selector = None
    if resource_name and resource_kind:
        field_selector = f"involvedObject.name={resource_name},involvedObject.kind={resource_kind}"
    elif resource_name:
        field_selector = f"involvedObject.name={resource_name}"

    events_list = core.list_namespaced_event(
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
            key=lambda x: x.last_timestamp or x.first_timestamp or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
    ]
    return {"events": events}


def list_pods_impl(
    ctx: InvestigationContext,
    namespace: str = "default",
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> dict[str, Any]:
    """List pods in a namespace."""
    if ctx.demo_mode:
        return ctx.provider().list_pods(namespace=namespace, label_selector=label_selector)

    core, _ = ctx.kubernetes_apis()
    pods_list = core.list_namespaced_pod(
        namespace=namespace,
        label_selector=label_selector,
        field_selector=field_selector,
    )
    pods = [
        {
            "name": p.metadata.name,
            "phase": p.status.phase,
            "ready": _pod_ready(p),
            "restarts": sum((cs.restart_count or 0) for cs in (p.status.container_statuses or [])),
            "age": p.metadata.creation_timestamp.isoformat(),
            "node": p.spec.node_name,
        }
        for p in pods_list.items
    ]
    return {"pods": pods}


def describe_deployment_impl(
    ctx: InvestigationContext,
    name: str,
    namespace: str = "default",
) -> dict[str, Any]:
    """Get deployment details."""
    if ctx.demo_mode:
        return ctx.provider().get_deployment_description(name=name, namespace=namespace)

    _, apps = ctx.kubernetes_apis()
    deployment = apps.read_namespaced_deployment(name=name, namespace=namespace)
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


def list_replicasets_impl(
    ctx: InvestigationContext,
    namespace: str = "default",
    deployment_name: str | None = None,
) -> dict[str, Any]:
    """List ReplicaSets, optionally filtered by deployment."""
    if ctx.demo_mode:
        return ctx.provider().list_replicasets(namespace=namespace, deployment_name=deployment_name)

    _, apps = ctx.kubernetes_apis()
    rs_list = apps.list_namespaced_replica_set(namespace=namespace)
    replicasets = []
    for rs in rs_list.items:
        if deployment_name:
            owner_refs = rs.metadata.owner_references or []
            is_owned = any(
                ref.kind == "Deployment" and ref.name == deployment_name for ref in owner_refs
            )
            if not is_owned:
                continue
        annotations = rs.metadata.annotations or {}
        replicasets.append(
            {
                "name": rs.metadata.name,
                "replicas": {
                    "desired": rs.spec.replicas,
                    "ready": rs.status.ready_replicas or 0,
                    "available": rs.status.available_replicas or 0,
                },
                "created": rs.metadata.creation_timestamp.isoformat(),
                "revision": annotations.get("deployment.kubernetes.io/revision", "unknown"),
            }
        )
    return {"replicasets": sorted(replicasets, key=lambda x: x["created"], reverse=True)}


def get_pod_logs_impl(
    ctx: InvestigationContext,
    name: str,
    namespace: str = "default",
    container: str | None = None,
    previous: bool = False,
    tail_lines: int = 100,
) -> dict[str, Any]:
    """Get logs from a pod container."""
    if ctx.demo_mode:
        return ctx.provider().get_pod_logs(
            name=name,
            namespace=namespace,
            container=container,
            previous=previous,
        )

    core, _ = ctx.kubernetes_apis()
    logs = core.read_namespaced_pod_log(
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


def describe_node_impl(ctx: InvestigationContext, name: str) -> dict[str, Any]:
    """Get node details."""
    if ctx.demo_mode:
        return ctx.provider().get_node_description(name=name)

    core, _ = ctx.kubernetes_apis()
    node = core.read_node(name=name)
    conditions = [
        {
            "type": c.type,
            "status": c.status,
            "reason": c.reason,
            "message": c.message,
            "last_heartbeat": c.last_heartbeat_time.isoformat() if c.last_heartbeat_time else None,
        }
        for c in node.status.conditions or []
    ]
    info = node.status.node_info
    return {
        "name": node.metadata.name,
        "labels": node.metadata.labels or {},
        "conditions": conditions,
        "capacity": dict((node.status.capacity or {}).items()),
        "allocatable": dict((node.status.allocatable or {}).items()),
        "info": {
            "os": info.os_image if info else None,
            "kernel": info.kernel_version if info else None,
            "container_runtime": info.container_runtime_version if info else None,
            "kubelet": info.kubelet_version if info else None,
        },
    }


def create_kubernetes_tools(ctx: InvestigationContext) -> list[Any]:
    """Create Strands-decorated Kubernetes investigation tools."""

    @tool(
        description="Get detailed information about a pod, including status, containers, "
        "conditions, and recent events. Essential for investigating pod failures."
    )
    def describe_pod(
        name: str,
        namespace: str = "default",
        cluster: str | None = None,
    ) -> dict[str, Any]:
        """Get detailed pod information."""
        return describe_pod_impl(ctx, name, namespace, cluster)

    @tool(
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
        return get_events_impl(ctx, namespace, resource_name, resource_kind, limit)

    @tool(
        description="List pods in a namespace with optional label selector. Use this to "
        "find pods matching specific criteria or to see overall namespace health."
    )
    def list_pods(
        namespace: str = "default",
        label_selector: str | None = None,
        field_selector: str | None = None,
    ) -> dict[str, Any]:
        """List pods in a namespace."""
        return list_pods_impl(ctx, namespace, label_selector, field_selector)

    @tool(
        description="Get deployment details including replica status, strategy, and "
        "conditions. Use this to check deployment health and recent rollouts."
    )
    def describe_deployment(
        name: str,
        namespace: str = "default",
    ) -> dict[str, Any]:
        """Get deployment details."""
        return describe_deployment_impl(ctx, name, namespace)

    @tool(
        description="Get recent ReplicaSet history for a deployment. Useful for tracking "
        "rollout history and identifying when issues started."
    )
    def list_replicasets(
        namespace: str = "default",
        deployment_name: str | None = None,
    ) -> dict[str, Any]:
        """List ReplicaSets, optionally filtered by deployment."""
        return list_replicasets_impl(ctx, namespace, deployment_name)

    @tool(
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
        return get_pod_logs_impl(ctx, name, namespace, container, previous, tail_lines)

    @tool(
        description="Get node information and conditions. Use this to check if node "
        "issues (memory pressure, disk pressure) are causing pod problems."
    )
    def describe_node(name: str) -> dict[str, Any]:
        """Get node details."""
        return describe_node_impl(ctx, name)

    return [
        describe_pod,
        get_events,
        list_pods,
        describe_deployment,
        list_replicasets,
        get_pod_logs,
        describe_node,
    ]

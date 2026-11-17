"""ECS investigation tools (Strands @tool wrappers + shared impl)."""

from __future__ import annotations

from typing import Any

from strands import tool

from aws_incident_copilot.tools.context import InvestigationContext  # noqa: TC001


def describe_service_impl(
    ctx: InvestigationContext,
    cluster: str,
    service: str,
) -> dict[str, Any]:
    """Describe an ECS service."""
    if ctx.demo_mode:
        return ctx.provider().get_ecs_service(cluster=cluster, service=service)

    client = ctx.client("ecs")
    response = client.describe_services(cluster=cluster, services=[service])
    if not response.get("services"):
        return {"error": f"Service {service} not found in cluster {cluster}"}

    svc = response["services"][0]
    deployments = [
        {
            "id": d["id"],
            "status": d["status"],
            "task_definition": d["taskDefinition"].split("/")[-1],
            "desired_count": d["desiredCount"],
            "running_count": d["runningCount"],
            "pending_count": d["pendingCount"],
            "rollout_state": d.get("rolloutState"),
            "created_at": d["createdAt"].isoformat() if d.get("createdAt") else None,
        }
        for d in svc.get("deployments", [])
    ]
    events = [
        {"timestamp": e["createdAt"].isoformat(), "message": e["message"]}
        for e in svc.get("events", [])[:10]
    ]
    return {
        "service_name": svc["serviceName"],
        "cluster": svc["clusterArn"].split("/")[-1],
        "status": svc["status"],
        "desired_count": svc["desiredCount"],
        "running_count": svc["runningCount"],
        "pending_count": svc["pendingCount"],
        "launch_type": svc.get("launchType"),
        "task_definition": svc["taskDefinition"].split("/")[-1],
        "deployments": deployments,
        "events": events,
        "created_at": svc["createdAt"].isoformat() if svc.get("createdAt") else None,
    }


def list_tasks_impl(
    ctx: InvestigationContext,
    cluster: str,
    service: str | None = None,
    status: str = "RUNNING",
) -> dict[str, Any]:
    """List ECS tasks."""
    if ctx.demo_mode:
        return ctx.provider().list_ecs_tasks(cluster=cluster, service=service, status=status)

    client = ctx.client("ecs")
    params: dict[str, Any] = {"cluster": cluster, "desiredStatus": status}
    if service:
        params["serviceName"] = service

    task_arns = client.list_tasks(**params).get("taskArns", [])
    if not task_arns:
        return {"tasks": []}

    tasks_response = client.describe_tasks(cluster=cluster, tasks=task_arns)
    tasks = []
    for task in tasks_response.get("tasks", []):
        containers = [
            {
                "name": c["name"],
                "status": c.get("lastStatus"),
                "health_status": c.get("healthStatus"),
                "exit_code": c.get("exitCode"),
                "reason": c.get("reason"),
            }
            for c in task.get("containers", [])
        ]
        tasks.append(
            {
                "task_arn": task["taskArn"],
                "task_id": task["taskArn"].split("/")[-1],
                "status": task["lastStatus"],
                "desired_status": task["desiredStatus"],
                "health_status": task.get("healthStatus"),
                "started_at": task["startedAt"].isoformat() if task.get("startedAt") else None,
                "stopped_at": task["stoppedAt"].isoformat() if task.get("stoppedAt") else None,
                "stopped_reason": task.get("stoppedReason"),
                "stop_code": task.get("stopCode"),
                "containers": containers,
                "cpu": task.get("cpu"),
                "memory": task.get("memory"),
            }
        )
    return {"tasks": tasks}


def describe_stopped_tasks_impl(
    ctx: InvestigationContext,
    cluster: str,
    service: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Get details of recently stopped tasks."""
    if ctx.demo_mode:
        return ctx.provider().get_stopped_tasks(cluster=cluster, service=service)

    client = ctx.client("ecs")
    params: dict[str, Any] = {"cluster": cluster, "desiredStatus": "STOPPED"}
    if service:
        params["serviceName"] = service

    task_arns = client.list_tasks(**params).get("taskArns", [])
    if not task_arns:
        return {"stopped_tasks": []}

    tasks_response = client.describe_tasks(cluster=cluster, tasks=task_arns[:limit])
    stopped_tasks = []
    for task in tasks_response.get("tasks", []):
        containers = []
        for c in task.get("containers", []):
            container_info = {
                "name": c["name"],
                "exit_code": c.get("exitCode"),
                "reason": c.get("reason"),
            }
            if c.get("exitCode") == 137:
                container_info["likely_oom"] = True
            containers.append(container_info)
        stopped_tasks.append(
            {
                "task_id": task["taskArn"].split("/")[-1],
                "stopped_at": task["stoppedAt"].isoformat() if task.get("stoppedAt") else None,
                "stopped_reason": task.get("stoppedReason"),
                "stop_code": task.get("stopCode"),
                "containers": containers,
            }
        )
    return {
        "stopped_tasks": sorted(
            stopped_tasks, key=lambda x: x.get("stopped_at") or "", reverse=True
        )
    }


def describe_task_definition_impl(
    ctx: InvestigationContext,
    task_definition: str,
) -> dict[str, Any]:
    """Get task definition details."""
    if ctx.demo_mode:
        return ctx.provider().get_task_definition(task_definition=task_definition)

    client = ctx.client("ecs")
    td = client.describe_task_definition(taskDefinition=task_definition)["taskDefinition"]
    containers = [
        {
            "name": c["name"],
            "image": c["image"],
            "cpu": c.get("cpu"),
            "memory": c.get("memory"),
            "memory_reservation": c.get("memoryReservation"),
            "essential": c.get("essential", True),
            "health_check": bool(c.get("healthCheck")),
            "log_driver": c.get("logConfiguration", {}).get("logDriver"),
        }
        for c in td.get("containerDefinitions", [])
    ]
    return {
        "family": td["family"],
        "revision": td["revision"],
        "status": td["status"],
        "cpu": td.get("cpu"),
        "memory": td.get("memory"),
        "network_mode": td.get("networkMode"),
        "requires_compatibilities": td.get("requiresCompatibilities", []),
        "containers": containers,
        "registered_at": td["registeredAt"].isoformat() if td.get("registeredAt") else None,
    }


def describe_cluster_impl(ctx: InvestigationContext, cluster: str) -> dict[str, Any]:
    """Get ECS cluster details."""
    if ctx.demo_mode:
        return ctx.provider().get_ecs_cluster(cluster=cluster)

    client = ctx.client("ecs")
    response = client.describe_clusters(clusters=[cluster], include=["STATISTICS", "SETTINGS"])
    if not response.get("clusters"):
        return {"error": f"Cluster {cluster} not found"}

    c = response["clusters"][0]
    statistics = {s["name"]: s["value"] for s in c.get("statistics", [])}
    return {
        "cluster_name": c["clusterName"],
        "status": c["status"],
        "registered_container_instances": c.get("registeredContainerInstancesCount", 0),
        "running_tasks": c.get("runningTasksCount", 0),
        "pending_tasks": c.get("pendingTasksCount", 0),
        "active_services": c.get("activeServicesCount", 0),
        "statistics": statistics,
        "capacity_providers": c.get("capacityProviders", []),
    }


def create_ecs_tools(ctx: InvestigationContext) -> list[Any]:
    """Create Strands-decorated ECS investigation tools."""

    @tool(
        description="Describe an ECS service including deployment status, task counts, "
        "and recent events. Use this to understand service health."
    )
    def describe_service(cluster: str, service: str) -> dict[str, Any]:
        """Describe an ECS service."""
        return describe_service_impl(ctx, cluster, service)

    @tool(
        description="List and describe ECS tasks in a service. Shows task status, "
        "container health, and stopped reasons."
    )
    def list_tasks(
        cluster: str,
        service: str | None = None,
        status: str = "RUNNING",
    ) -> dict[str, Any]:
        """List ECS tasks."""
        return list_tasks_impl(ctx, cluster, service, status)

    @tool(
        description="Get stopped task details with exit codes and stop reasons. "
        "Essential for debugging OOM kills and task failures."
    )
    def describe_stopped_tasks(
        cluster: str,
        service: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get details of recently stopped tasks."""
        return describe_stopped_tasks_impl(ctx, cluster, service, limit)

    @tool(
        description="Get task definition details including container definitions, "
        "resource limits, and environment variables."
    )
    def describe_task_definition(task_definition: str) -> dict[str, Any]:
        """Get task definition details."""
        return describe_task_definition_impl(ctx, task_definition)

    @tool(
        description="Describe an ECS cluster including capacity provider status "
        "and registered container instances."
    )
    def describe_cluster(cluster: str) -> dict[str, Any]:
        """Get ECS cluster details."""
        return describe_cluster_impl(ctx, cluster)

    return [
        describe_service,
        list_tasks,
        describe_stopped_tasks,
        describe_task_definition,
        describe_cluster,
    ]

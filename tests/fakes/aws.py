"""Moto helpers for AWS live-path tests."""

from __future__ import annotations

import boto3


def create_fargate_service(region: str = "us-west-2"):
    """Create a VPC, subnet, cluster, and Fargate service. Returns the ECS client."""
    ec2 = boto3.client("ec2", region_name=region)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc, CidrBlock="10.0.1.0/24")["Subnet"]["SubnetId"]
    sg = ec2.create_security_group(GroupName="ecs-sg", Description="test", VpcId=vpc)["GroupId"]
    ecs = boto3.client("ecs", region_name=region)
    ecs.create_cluster(clusterName="prod")
    ecs.register_task_definition(
        family="api",
        cpu="256",
        memory="512",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        containerDefinitions=[
            {"name": "api", "image": "public.ecr.aws/docker/library/nginx:1", "essential": True}
        ],
    )
    ecs.create_service(
        cluster="prod",
        serviceName="api",
        taskDefinition="api",
        desiredCount=1,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [subnet],
                "securityGroups": [sg],
                "assignPublicIp": "ENABLED",
            }
        },
    )
    return ecs

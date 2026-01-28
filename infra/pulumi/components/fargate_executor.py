"""Fargate Executor Component for sandboxed code execution."""

import pulumi
import pulumi_aws as aws
import json


class FargateExecutorComponent(pulumi.ComponentResource):
    """AWS Fargate based sandboxed executor for running untrusted code."""

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        ecr_repository_url: pulumi.Input[str],
        image_tag: str = "latest",
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:compute:FargateExecutor", name, None, opts)

        self.tags = tags or {}

        # ECS Cluster
        self.cluster = aws.ecs.Cluster(
            f"{name}-cluster",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # CloudWatch Log Group for container logs
        self.log_group = aws.cloudwatch.LogGroup(
            f"{name}-logs",
            name=f"/ecs/{name}-executor",
            retention_in_days=7,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # IAM Role for Task Execution (pulling images, writing logs)
        self.execution_role = aws.iam.Role(
            f"{name}-exec-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Effect": "Allow",
                        }
                    ],
                }
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.iam.RolePolicyAttachment(
            f"{name}-exec-policy",
            role=self.execution_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # IAM Role for Task (what the container can do - should be minimal!)
        self.task_role = aws.iam.Role(
            f"{name}-task-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Effect": "Allow",
                        }
                    ],
                }
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Security Group - No egress (isolated sandbox)
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for Fargate executor (no egress)",
            # No ingress - tasks don't need incoming connections
            ingress=[],
            # No egress - sandboxed code should not access the internet
            egress=[],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Store subnet IDs for later use
        self.subnet_ids = subnet_ids

        # Task Definition
        self.task_definition = aws.ecs.TaskDefinition(
            f"{name}-task",
            family=f"{name}-executor",
            cpu="256",
            memory="512",
            network_mode="awsvpc",
            requires_compatibilities=["FARGATE"],
            execution_role_arn=self.execution_role.arn,
            task_role_arn=self.task_role.arn,
            container_definitions=pulumi.Output.all(
                ecr_repository_url, self.log_group.name
            ).apply(
                lambda args: json.dumps(
                    [
                        {
                            "name": "executor",
                            "image": f"{args[0]}:{image_tag}",
                            "essential": True,
                            "logConfiguration": {
                                "logDriver": "awslogs",
                                "options": {
                                    "awslogs-group": args[1],
                                    "awslogs-region": "us-east-1",
                                    "awslogs-stream-prefix": "ecs",
                                },
                            },
                            "environment": [
                                {"name": "RELAXED_MODE", "value": "false"},
                                {"name": "EXECUTION_TIMEOUT_SECONDS", "value": "30"},
                            ],
                            # Resource limits for security
                            "ulimits": [
                                {
                                    "name": "nofile",
                                    "softLimit": 1024,
                                    "hardLimit": 1024,
                                },
                                {
                                    "name": "nproc",
                                    "softLimit": 50,
                                    "hardLimit": 100,
                                },
                            ],
                            # Read-only root filesystem for security
                            "readonlyRootFilesystem": False,  # Python needs write access to /tmp
                        }
                    ]
                )
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.log_group]),
        )

        self.register_outputs(
            {
                "cluster_name": self.cluster.name,
                "cluster_arn": self.cluster.arn,
                "task_definition_arn": self.task_definition.arn,
                "security_group_id": self.security_group.id,
                "log_group_name": self.log_group.name,
            }
        )

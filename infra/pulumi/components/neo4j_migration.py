"""Neo4j Migration Lambda Component for graph schema migrations."""

import json

import pulumi
import pulumi_aws as aws


class Neo4jMigrationComponent(pulumi.ComponentResource):
    """Lambda function for running Neo4j schema migrations.

    This Lambda:
    - Uses the same Docker image as the API Lambda
    - Runs Neo4j migrations via a separate handler
    - Has outbound access to connect to Neo4j AuraDB
    - Is invoked during CI/CD deployment after PostgreSQL migrations
    """

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        ecr_repository_url: pulumi.Input[str],
        neo4j_secret_arn: pulumi.Input[str],
        image_tag: str = "latest",
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        """Initialize Neo4j migration component.

        Args:
            name: Resource name prefix.
            environment: Deployment environment.
            vpc_id: VPC ID for Lambda networking.
            subnet_ids: Private subnet IDs for Lambda.
            ecr_repository_url: ECR repository URL for Lambda image.
            neo4j_secret_arn: ARN of Neo4j credentials secret.
            image_tag: Docker image tag.
            tags: Common resource tags.
            opts: Pulumi resource options.
        """
        super().__init__("coderemote:compute:Neo4jMigration", name, None, opts)

        self.tags = tags or {}

        # Security Group for Migration Lambda
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for Neo4j Migration Lambda",
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow outbound to Neo4j AuraDB",
                )
            ],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # IAM Role for Lambda
        self.role = aws.iam.Role(
            f"{name}-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Effect": "Allow",
                        }
                    ],
                }
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # VPC access policy (for NAT Gateway outbound)
        aws.iam.RolePolicyAttachment(
            f"{name}-vpc-exec",
            role=self.role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # X-Ray tracing policy
        aws.iam.RolePolicyAttachment(
            f"{name}-xray",
            role=self.role.name,
            policy_arn="arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Secrets Manager access policy for Neo4j credentials
        secrets_policy = aws.iam.Policy(
            f"{name}-secrets-policy",
            policy=pulumi.Output.all(neo4j_secret_arn).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["secretsmanager:GetSecretValue"],
                                "Resource": args[0],
                            }
                        ],
                    }
                )
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.iam.RolePolicyAttachment(
            f"{name}-secrets-attach",
            role=self.role.name,
            policy_arn=secrets_policy.arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Lambda Function
        self.function = aws.lambda_.Function(
            f"{name}-function",
            name=f"code-remote-{environment}-neo4j-migrate",
            package_type="Image",
            image_uri=pulumi.Output.concat(ecr_repository_url, ":", image_tag),
            image_config=aws.lambda_.FunctionImageConfigArgs(
                commands=["api.neo4j_migrate_handler.handler"],
            ),
            role=self.role.arn,
            memory_size=256,  # Light-weight, just runs Cypher queries
            timeout=120,  # 2 minutes should be plenty for migrations
            vpc_config=aws.lambda_.FunctionVpcConfigArgs(
                subnet_ids=subnet_ids,
                security_group_ids=[self.security_group.id],
            ),
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "NEO4J_SECRET_ARN": neo4j_secret_arn,
                },
            ),
            tracing_config=aws.lambda_.FunctionTracingConfigArgs(
                mode="Active",
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "function_name": self.function.name,
                "function_arn": self.function.arn,
            }
        )

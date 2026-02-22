"""Migration Lambda Component for database migrations."""

import json

import pulumi
import pulumi_aws as aws


class MigrationComponent(pulumi.ComponentResource):
    """Lambda function for running database migrations.

    This Lambda:
    - Uses the same Docker image as the API Lambda
    - Runs Alembic migrations via a separate handler
    - Has VPC access to connect to the database
    - Is invoked during CI/CD deployment
    """

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        ecr_repository_url: pulumi.Input[str],
        database_secret_arn: pulumi.Input[str],
        database_security_group_id: pulumi.Input[str],
        image_tag: str = "latest",
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:compute:Migration", name, None, opts)

        self.tags = tags or {}

        # Security Group for Migration Lambda
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for Migration Lambda",
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow all outbound traffic",
                )
            ],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Allow Migration Lambda to connect to database
        aws.ec2.SecurityGroupRule(
            f"{name}-to-db",
            type="ingress",
            from_port=5432,
            to_port=5432,
            protocol="tcp",
            security_group_id=database_security_group_id,
            source_security_group_id=self.security_group.id,
            description="Allow Migration Lambda to connect to PostgreSQL",
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

        # VPC access policy
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

        # Secrets Manager access policy for database credentials
        secrets_policy = aws.iam.Policy(
            f"{name}-secrets-policy",
            policy=pulumi.Output.all(database_secret_arn).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "secretsmanager:GetSecretValue",
                                ],
                                "Resource": [
                                    args[0],
                                    # Allow access to any secret in the code-remote path
                                    args[0].rsplit("/", 1)[0] + "/*",
                                ],
                            }
                        ],
                    }
                )
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.iam.RolePolicyAttachment(
            f"{name}-secrets-policy-attachment",
            role=self.role.name,
            policy_arn=secrets_policy.arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # CloudWatch Log Group
        self.log_group = aws.cloudwatch.LogGroup(
            f"{name}-logs",
            name=f"/aws/lambda/{name}-func",
            retention_in_days=30,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Lambda Function
        self.function = aws.lambda_.Function(
            f"{name}-func",
            package_type="Image",
            image_uri=pulumi.Output.concat(ecr_repository_url, ":", image_tag),
            role=self.role.arn,
            timeout=300,  # 5 minutes for migrations
            memory_size=512,
            image_config=aws.lambda_.FunctionImageConfigArgs(
                commands=["api.migrate_handler.handler"],
            ),
            vpc_config=aws.lambda_.FunctionVpcConfigArgs(
                subnet_ids=subnet_ids,
                security_group_ids=[self.security_group.id],
            ),
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "DATABASE_SECRET_ARN": database_secret_arn,
                    "ENVIRONMENT": environment,
                }
            ),
            tracing_config=aws.lambda_.FunctionTracingConfigArgs(
                mode="Active",
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.log_group]),
        )

        self.register_outputs(
            {
                "function_name": self.function.name,
                "function_arn": self.function.arn,
            }
        )

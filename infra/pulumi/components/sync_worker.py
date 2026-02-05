"""Sync Worker Lambda Component - SQS consumer for Neo4j synchronization."""

import json

import pulumi
import pulumi_aws as aws


class SyncWorkerComponent(pulumi.ComponentResource):
    """Sync Worker Lambda that processes snippet sync events from SQS.

    Generates embeddings and syncs snippets to Neo4j AuraDB.
    """

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        ecr_repository_url: pulumi.Input[str],
        sync_queue_arn: pulumi.Input[str],
        neo4j_secret_arn: pulumi.Input[str],
        gemini_secret_arn: pulumi.Input[str],
        database_secret_arn: pulumi.Input[str],
        database_security_group_id: pulumi.Input[str],
        image_tag: str = "latest",
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        """Initialize sync worker component.

        Args:
            name: Resource name prefix.
            environment: Deployment environment.
            vpc_id: VPC ID for Lambda networking.
            subnet_ids: Private subnet IDs for Lambda.
            ecr_repository_url: ECR repository URL for Lambda image.
            sync_queue_arn: ARN of the snippet sync SQS queue.
            neo4j_secret_arn: ARN of Neo4j credentials secret.
            gemini_secret_arn: ARN of Gemini API key secret.
            database_secret_arn: ARN of database connection secret.
            database_security_group_id: Security group ID for database access.
            image_tag: Docker image tag.
            tags: Common resource tags.
            opts: Pulumi resource options.
        """
        super().__init__("coderemote:compute:SyncWorker", name, None, opts)

        self.tags = tags or {}

        # Security Group for Lambda in VPC
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for Sync Worker Lambda",
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow all outbound (Neo4j AuraDB, Gemini API)",
                )
            ],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Allow access to database
        aws.ec2.SecurityGroupRule(
            f"{name}-db-access",
            type="ingress",
            from_port=5432,
            to_port=5432,
            protocol="tcp",
            security_group_id=database_security_group_id,
            source_security_group_id=self.security_group.id,
            description="Allow Sync Worker to access PostgreSQL",
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

        # SQS access policy
        sqs_policy = aws.iam.Policy(
            f"{name}-sqs-policy",
            policy=pulumi.Output.all(sync_queue_arn).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "sqs:ReceiveMessage",
                                    "sqs:DeleteMessage",
                                    "sqs:GetQueueAttributes",
                                ],
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
            f"{name}-sqs-attach",
            role=self.role.name,
            policy_arn=sqs_policy.arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Secrets access policy (Neo4j + Gemini + Database)
        secrets_policy = aws.iam.Policy(
            f"{name}-secrets-policy",
            policy=pulumi.Output.all(
                neo4j_secret_arn, gemini_secret_arn, database_secret_arn
            ).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "secretsmanager:GetSecretValue",
                                ],
                                "Resource": list(args),
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
            name=f"code-remote-{environment}-sync-worker",
            package_type="Image",
            image_uri=pulumi.Output.concat(ecr_repository_url, ":", image_tag),
            image_config=aws.lambda_.FunctionImageConfigArgs(
                commands=["api.handlers.sync_worker.handler"],
            ),
            role=self.role.arn,
            memory_size=512,  # Modest memory for embedding + Neo4j
            timeout=60,  # 60s max (embedding ~100ms, Neo4j write ~200ms)
            vpc_config=aws.lambda_.FunctionVpcConfigArgs(
                subnet_ids=subnet_ids,
                security_group_ids=[self.security_group.id],
            ),
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "NEO4J_SECRET_ARN": neo4j_secret_arn,
                    "GEMINI_API_KEY_SECRET_ARN": gemini_secret_arn,
                    "DATABASE_SECRET_ARN": database_secret_arn,
                    "GEMINI_EMBEDDING_MODEL": "text-embedding-004",
                },
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # SQS Event Source Mapping
        self.event_source = aws.lambda_.EventSourceMapping(
            f"{name}-sqs-trigger",
            event_source_arn=sync_queue_arn,
            function_name=self.function.arn,
            batch_size=10,  # Process up to 10 messages per invocation
            function_response_types=["ReportBatchItemFailures"],
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "function_name": self.function.name,
                "function_arn": self.function.arn,
                "security_group_id": self.security_group.id,
            }
        )

"""Worker Lambda Component - SQS consumer for code execution."""

import json

import pulumi
import pulumi_aws as aws


class WorkerComponent(pulumi.ComponentResource):
    """Worker Lambda that processes execution jobs from SQS.

    Executes code and pushes results directly to WebSocket connections.
    """

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        ecr_repository_url: pulumi.Input[str],
        queue_arn: pulumi.Input[str],
        websocket_api_id: pulumi.Input[str],
        websocket_endpoint: pulumi.Input[str],
        secrets_arn: pulumi.Input[str],
        image_tag: str = "latest",
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:compute:Worker", name, None, opts)

        self.tags = tags or {}

        # Security Group for Lambda in VPC
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for Worker Lambda",
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
            policy=pulumi.Output.all(queue_arn).apply(
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

        # WebSocket Management API access policy
        ws_policy = aws.iam.Policy(
            f"{name}-ws-policy",
            policy=pulumi.Output.all(websocket_api_id).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["execute-api:ManageConnections"],
                                "Resource": f"arn:aws:execute-api:*:*:{args[0]}/*",
                            }
                        ],
                    }
                )
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.iam.RolePolicyAttachment(
            f"{name}-ws-attach",
            role=self.role.name,
            policy_arn=ws_policy.arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Secrets Manager access policy (for Gemini API key if needed)
        secrets_policy = aws.iam.Policy(
            f"{name}-secrets-policy",
            policy=pulumi.Output.all(secrets_arn).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["secretsmanager:GetSecretValue"],
                                "Resource": [args[0], f"{args[0]}*"],
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

        # CloudWatch Logs
        self.log_group = aws.cloudwatch.LogGroup(
            f"{name}-logs",
            name=f"/aws/lambda/{name}-func",
            retention_in_days=30,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Lambda Function (Container image based, same image as API)
        self.function = aws.lambda_.Function(
            f"{name}-func",
            package_type="Image",
            image_uri=pulumi.Output.concat(ecr_repository_url, ":", image_tag),
            role=self.role.arn,
            timeout=60,  # 2x max execution time for safety
            memory_size=512,  # Less memory than API, execution is lighter
            image_config=aws.lambda_.FunctionImageConfigArgs(
                commands=["api.handlers.worker.handler"],
            ),
            vpc_config=aws.lambda_.FunctionVpcConfigArgs(
                subnet_ids=subnet_ids,
                security_group_ids=[self.security_group.id],
            ),
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "ENVIRONMENT": environment,
                    "WEBSOCKET_ENDPOINT": websocket_endpoint,
                }
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.log_group]),
        )

        # SQS Event Source Mapping
        self.event_source = aws.lambda_.EventSourceMapping(
            f"{name}-sqs-trigger",
            event_source_arn=queue_arn,
            function_name=self.function.name,
            batch_size=1,  # Process one job at a time for isolation
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "function_arn": self.function.arn,
                "function_name": self.function.name,
            }
        )

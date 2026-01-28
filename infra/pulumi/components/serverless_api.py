"""Serverless API Component using AWS Lambda and API Gateway."""

import pulumi
import pulumi_aws as aws
import json


class ServerlessAPIComponent(pulumi.ComponentResource):
    """AWS Lambda based API with API Gateway integration."""

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        ecr_repository_url: pulumi.Input[str],
        cognito_user_pool_arn: pulumi.Input[str],
        cognito_user_pool_client_id: pulumi.Input[str],
        secrets_arn: pulumi.Input[str],
        fargate_cluster_arn: pulumi.Input[str],
        fargate_task_definition_arn: pulumi.Input[str],
        fargate_subnets: pulumi.Input[str],
        fargate_security_group_id: pulumi.Input[str],
        image_tag: str = "latest",
        env_vars: dict | None = None,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:compute:ServerlessAPI", name, None, opts)

        self.tags = tags or {}
        base_env_vars = env_vars or {}

        # Security Group for Lambda in VPC
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for API Lambda",
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

        # Secrets Manager access policy
        secrets_policy = aws.iam.Policy(
            f"{name}-secrets-policy",
            policy=pulumi.Output.all(secrets_arn).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "secretsmanager:GetSecretValue",
                                ],
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

        # ECS access policy (to run Fargate tasks)
        ecs_policy = aws.iam.Policy(
            f"{name}-ecs-policy",
            policy=pulumi.Output.all(
                fargate_cluster_arn, fargate_task_definition_arn
            ).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "ecs:RunTask",
                                    "ecs:StopTask",
                                    "ecs:DescribeTasks",
                                ],
                                "Resource": "*",
                                "Condition": {"ArnEquals": {"ecs:cluster": args[0]}},
                            },
                            {
                                "Effect": "Allow",
                                "Action": ["iam:PassRole"],
                                "Resource": "*",
                                "Condition": {
                                    "StringLike": {
                                        "iam:PassedToService": "ecs-tasks.amazonaws.com"
                                    }
                                },
                            },
                        ],
                    }
                )
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.iam.RolePolicyAttachment(
            f"{name}-ecs-attach",
            role=self.role.name,
            policy_arn=ecs_policy.arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # CloudWatch Logs
        self.log_group = aws.cloudwatch.LogGroup(
            f"{name}-logs",
            name=f"/aws/lambda/{name}-func",
            retention_in_days=14,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Merge environment variables
        lambda_env_vars = {
            **base_env_vars,
            "ENVIRONMENT": environment,
            "FARGATE_CLUSTER_ARN": fargate_cluster_arn,
            "FARGATE_TASK_DEFINITION_ARN": fargate_task_definition_arn,
            "FARGATE_SUBNETS": fargate_subnets,
            "FARGATE_SECURITY_GROUP_ID": fargate_security_group_id,
        }

        # Lambda Function (Container image based)
        self.function = aws.lambda_.Function(
            f"{name}-func",
            package_type="Image",
            image_uri=pulumi.Output.concat(ecr_repository_url, ":", image_tag),
            role=self.role.arn,
            timeout=30,
            memory_size=1024,
            image_config=aws.lambda_.FunctionImageConfigArgs(
                commands=["api.lambda_handler.handler"],
            ),
            vpc_config=aws.lambda_.FunctionVpcConfigArgs(
                subnet_ids=subnet_ids,
                security_group_ids=[self.security_group.id],
            ),
            environment=aws.lambda_.FunctionEnvironmentArgs(variables=lambda_env_vars),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.log_group]),
        )

        # API Gateway (HTTP API v2)
        self.api = aws.apigatewayv2.Api(
            f"{name}-api",
            protocol_type="HTTP",
            cors_configuration=aws.apigatewayv2.ApiCorsConfigurationArgs(
                allow_origins=["*"],
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["*"],
                max_age=300,
            ),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # JWT Authorizer using Cognito
        self.authorizer = aws.apigatewayv2.Authorizer(
            f"{name}-authorizer",
            api_id=self.api.id,
            authorizer_type="JWT",
            identity_sources=["$request.header.Authorization"],
            jwt_configuration=aws.apigatewayv2.AuthorizerJwtConfigurationArgs(
                audiences=[cognito_user_pool_client_id],
                issuer=pulumi.Output.concat(
                    "https://cognito-idp.us-east-1.amazonaws.com/",
                    cognito_user_pool_arn.apply(lambda arn: arn.split("/")[-1]),
                ),
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Lambda integration
        self.integration = aws.apigatewayv2.Integration(
            f"{name}-integration",
            api_id=self.api.id,
            integration_type="AWS_PROXY",
            integration_uri=self.function.arn,
            payload_format_version="2.0",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Route for all methods (with auth)
        aws.apigatewayv2.Route(
            f"{name}-route-proxy",
            api_id=self.api.id,
            route_key="ANY /{proxy+}",
            target=pulumi.Output.concat("integrations/", self.integration.id),
            authorization_type="JWT",
            authorizer_id=self.authorizer.id,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Health check route (no auth)
        aws.apigatewayv2.Route(
            f"{name}-route-health",
            api_id=self.api.id,
            route_key="GET /health",
            target=pulumi.Output.concat("integrations/", self.integration.id),
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Default stage with auto-deploy
        self.stage = aws.apigatewayv2.Stage(
            f"{name}-stage",
            api_id=self.api.id,
            name="$default",
            auto_deploy=True,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Permission for API Gateway to invoke Lambda
        aws.lambda_.Permission(
            f"{name}-permission",
            action="lambda:InvokeFunction",
            function=self.function.name,
            principal="apigateway.amazonaws.com",
            source_arn=pulumi.Output.concat(self.api.execution_arn, "/*/*"),
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Export api_endpoint property
        self.api_endpoint = self.api.api_endpoint

        self.register_outputs(
            {
                "api_endpoint": self.api.api_endpoint,
                "function_arn": self.function.arn,
                "function_name": self.function.name,
            }
        )

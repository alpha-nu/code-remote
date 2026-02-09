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
        queue_url: pulumi.Input[str] | None = None,
        database_security_group_id: pulumi.Input[str] | None = None,
        neo4j_secret_arn: pulumi.Input[str] | None = None,
        image_tag: str = "latest",
        env_vars: dict | None = None,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:compute:ServerlessAPI", name, None, opts)

        self.tags = tags or {}
        base_env_vars = env_vars or {}
        self.database_security_group_id = database_security_group_id

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

        # Allow Lambda to connect to database if database SG provided
        if database_security_group_id:
            aws.ec2.SecurityGroupRule(
                f"{name}-to-db",
                type="ingress",
                from_port=5432,
                to_port=5432,
                protocol="tcp",
                security_group_id=database_security_group_id,
                source_security_group_id=self.security_group.id,
                description="Allow Lambda to connect to Aurora PostgreSQL",
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

        # Secrets Manager access policy (Gemini API key + Database connection + Neo4j)
        # Build list of secret ARNs to allow access to
        secret_arns_to_allow = [secrets_arn]
        if neo4j_secret_arn:
            secret_arns_to_allow.append(neo4j_secret_arn)

        secrets_policy = aws.iam.Policy(
            f"{name}-secrets-policy",
            policy=pulumi.Output.all(*secret_arns_to_allow).apply(
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
                                    arn for a in args for arn in [a, f"{a}*"] if a
                                ]
                                + [
                                    # Database secrets (pattern matches code-remote/*/db-*)
                                    f"arn:aws:secretsmanager:*:*:secret:code-remote/{environment}/db-*",
                                ],
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

        # SQS access policy (for sending execution jobs)
        if queue_url:
            # Extract ARN from URL pattern
            sqs_policy = aws.iam.Policy(
                f"{name}-sqs-policy",
                policy=json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["sqs:SendMessage"],
                                "Resource": "*",  # Will be scoped by queue URL in code
                            }
                        ],
                    }
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

        # CloudWatch Logs
        self.log_group = aws.cloudwatch.LogGroup(
            f"{name}-logs",
            name=f"/aws/lambda/{name}-func",
            retention_in_days=14,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Policy to allow Lambda to read the specific Gemini API Key secret
        if secrets_arn:
            aws.iam.RolePolicyAttachment(
                f"{name}-gemini-secret-read-policy",
                role=self.role.name,
                policy_arn=aws.iam.Policy(
                    f"{name}-gemini-secret-policy",
                    policy=pulumi.Output.json_dumps(
                        {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Action": "secretsmanager:GetSecretValue",
                                    "Resource": secrets_arn,
                                }
                            ],
                        }
                    ),
                    opts=pulumi.ResourceOptions(parent=self),
                ).arn,
                opts=pulumi.ResourceOptions(parent=self),
            )

        # Retrieve Gemini API Key secret value
        gemini_api_key = pulumi.Output.secret(secrets_arn).apply(
            lambda arn: aws.secretsmanager.get_secret_version(
                secret_id=arn
            ).secret_string
            if arn
            else ""
        )

        # Merge environment variables
        lambda_env_vars = {
            **base_env_vars,
            "ENVIRONMENT": environment,
            "GEMINI_API_KEY": gemini_api_key,
        }

        # Add queue URL if provided
        if queue_url:
            lambda_env_vars["EXECUTION_QUEUE_URL"] = queue_url

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
            tracing_config=aws.lambda_.FunctionTracingConfigArgs(
                mode="Active",
            ),
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

        # OPTIONS preflight route (no auth) - required for CORS
        # The HTTP API CORS config handles the response, but we need a route without auth
        aws.apigatewayv2.Route(
            f"{name}-route-options",
            api_id=self.api.id,
            route_key="OPTIONS /{proxy+}",
            target=pulumi.Output.concat("integrations/", self.integration.id),
            authorization_type="NONE",
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

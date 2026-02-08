"""WebSocket API Gateway Component for real-time communication."""

import json

import pulumi
import pulumi_aws as aws


class WebSocketComponent(pulumi.ComponentResource):
    """WebSocket API Gateway for real-time execution updates.

    This is a minimal WebSocket setup - connections are stateless.
    The connection_id is passed back to the client who includes it
    in execute requests for direct push notifications.
    """

    def __init__(
        self,
        name: str,
        environment: str,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:websocket:API", name, None, opts)

        self.tags = tags or {}

        # WebSocket API
        self.api = aws.apigatewayv2.Api(
            f"{name}-ws-api",
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # IAM Role for Lambda handlers
        self.lambda_role = aws.iam.Role(
            f"{name}-ws-lambda-role",
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

        # Basic Lambda execution policy
        aws.iam.RolePolicyAttachment(
            f"{name}-ws-lambda-basic",
            role=self.lambda_role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Policy to allow Lambda to post to WebSocket connections
        ws_manage_policy = aws.iam.Policy(
            f"{name}-ws-manage-policy",
            policy=self.api.execution_arn.apply(
                lambda arn: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": "execute-api:ManageConnections",
                                "Resource": f"{arn}/*",
                            }
                        ],
                    }
                )
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        aws.iam.RolePolicyAttachment(
            f"{name}-ws-manage-attach",
            role=self.lambda_role.name,
            policy_arn=ws_manage_policy.arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # CloudWatch Log Group
        self.log_group = aws.cloudwatch.LogGroup(
            f"{name}-ws-logs",
            name=f"/aws/lambda/{name}-ws-handler",
            retention_in_days=7,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Lambda handler for WebSocket events
        # Uses API Gateway Management API to send messages back to clients
        handler_code = '''
import json
import boto3
import os

def handler(event, context):
    """Handle WebSocket connect/disconnect/default events."""
    route_key = event.get("requestContext", {}).get("routeKey")
    connection_id = event.get("requestContext", {}).get("connectionId")
    domain = event.get("requestContext", {}).get("domainName")
    stage = event.get("requestContext", {}).get("stage")

    if route_key == "$connect":
        print(f"Connected: {connection_id}")
        return {"statusCode": 200}

    elif route_key == "$disconnect":
        print(f"Disconnected: {connection_id}")
        return {"statusCode": 200}

    elif route_key == "$default":
        # Handle ping/pong - send connection_id back via Management API
        body = json.loads(event.get("body", "{}"))
        action = body.get("action")

        if action == "ping":
            # Use Management API to send message back to client
            endpoint_url = f"https://{domain}/{stage}"
            client = boto3.client(
                "apigatewaymanagementapi",
                endpoint_url=endpoint_url
            )
            try:
                client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps({
                        "type": "pong",
                        "connection_id": connection_id
                    }).encode("utf-8")
                )
            except client.exceptions.GoneException:
                print(f"Connection {connection_id} is gone")
            except Exception as e:
                print(f"Error sending to {connection_id}: {e}")

        return {"statusCode": 200}

    return {"statusCode": 200}
'''

        # Lambda function for WebSocket handlers
        self.handler = aws.lambda_.Function(
            f"{name}-ws-handler",
            runtime="python3.11",
            handler="index.handler",
            role=self.lambda_role.arn,
            timeout=10,
            memory_size=128,
            code=pulumi.AssetArchive({"index.py": pulumi.StringAsset(handler_code)}),
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.log_group]),
        )

        # Integration for Lambda
        self.integration = aws.apigatewayv2.Integration(
            f"{name}-ws-integration",
            api_id=self.api.id,
            integration_type="AWS_PROXY",
            integration_uri=self.handler.invoke_arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Routes
        for route in ["$connect", "$disconnect", "$default"]:
            route_name = route.replace("$", "")
            aws.apigatewayv2.Route(
                f"{name}-ws-route-{route_name}",
                api_id=self.api.id,
                route_key=route,
                target=pulumi.Output.concat("integrations/", self.integration.id),
                opts=pulumi.ResourceOptions(parent=self),
            )

        # Permission for API Gateway to invoke Lambda
        aws.lambda_.Permission(
            f"{name}-ws-permission",
            action="lambda:InvokeFunction",
            function=self.handler.name,
            principal="apigateway.amazonaws.com",
            source_arn=pulumi.Output.concat(self.api.execution_arn, "/*/*"),
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Stage with auto-deploy
        self.stage = aws.apigatewayv2.Stage(
            f"{name}-ws-stage",
            api_id=self.api.id,
            name=environment,
            auto_deploy=True,
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # WebSocket endpoint URL
        self.endpoint = pulumi.Output.concat(
            "wss://",
            self.api.id,
            ".execute-api.",
            aws.get_region().name,
            ".amazonaws.com/",
            environment,
        )

        # Management API endpoint (for posting to connections)
        self.management_endpoint = pulumi.Output.concat(
            "https://",
            self.api.id,
            ".execute-api.",
            aws.get_region().name,
            ".amazonaws.com/",
            environment,
        )

        self.register_outputs(
            {
                "api_id": self.api.id,
                "endpoint": self.endpoint,
                "management_endpoint": self.management_endpoint,
            }
        )

# Infrastructure

## Overview

Code Remote uses Pulumi (Python) for infrastructure as code. The architecture is designed to be cloud-agnostic through provider abstractions, with AWS as the initial implementation.

## AWS Resources

### Compute

| Resource | Service | Purpose |
|----------|---------|---------|
| API Handler | Lambda (Container) | FastAPI with Mangum adapter |
| Worker | Lambda | SQS consumer, executes code, pushes WebSocket updates |
| WebSocket Handlers | Lambda | $connect, $disconnect, $default routes |

### Networking & API

| Resource | Service | Purpose |
|----------|---------|---------|
| REST API | API Gateway v2 (HTTP) | /execute, /analyze, /health endpoints |
| WebSocket API | API Gateway v2 (WebSocket) | Real-time job updates |
| CDN | CloudFront | Frontend static assets |

### Storage

| Resource | Service | Purpose |
|----------|---------|---------|
| Jobs Table | DynamoDB | Job state and results |
| Connections Table | DynamoDB | WebSocket connection tracking |
| Frontend Assets | S3 | React build artifacts |
| Container Images | ECR | Lambda container images |

### Messaging

| Resource | Service | Purpose |
|----------|---------|---------|
| Execution Queue | SQS FIFO | Job queue with ordering |
| Dead Letter Queue | SQS | Failed job storage |

### Security

| Resource | Service | Purpose |
|----------|---------|---------|
| User Pool | Cognito | Authentication |
| Secrets | Secrets Manager | API keys (Gemini) |

## Pulumi Structure

```
infra/pulumi/
├── __main__.py              # Entry point, orchestrates components
├── Pulumi.yaml              # Project configuration
├── Pulumi.dev.yaml          # Dev environment config
├── Pulumi.prod.yaml         # Prod environment config
├── requirements.txt         # Python dependencies
└── components/
    ├── __init__.py
    ├── api.py               # API Gateway (HTTP)
    ├── websocket.py         # API Gateway (WebSocket)
    ├── compute.py           # Lambda functions
    ├── database.py          # DynamoDB tables
    ├── messaging.py         # SQS queues
    ├── storage.py           # S3, ECR
    ├── cdn.py               # CloudFront
    └── auth.py              # Cognito
```

## Key Components

### WebSocket API Gateway

```python
# components/websocket.py

import pulumi
import pulumi_aws as aws

class WebSocketAPI(pulumi.ComponentResource):
    def __init__(self, name: str, opts=None, **kwargs):
        super().__init__("coderemote:websocket:API", name, None, opts)
        
        env = pulumi.get_stack()
        
        # WebSocket API
        self.api = aws.apigatewayv2.Api(
            f"{name}-ws-api",
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
            opts=pulumi.ResourceOptions(parent=self),
        )
        
        # Stage
        self.stage = aws.apigatewayv2.Stage(
            f"{name}-ws-stage",
            api_id=self.api.id,
            name=env,
            auto_deploy=True,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs({
            "api_id": self.api.id,
            "endpoint": self.stage.invoke_url,
        })
```

### DynamoDB Tables

```python
# components/database.py

class Database(pulumi.ComponentResource):
    def __init__(self, name: str, opts=None, **kwargs):
        super().__init__("coderemote:database:Tables", name, None, opts)
        
        env = pulumi.get_stack()
        
        # Jobs table
        self.jobs_table = aws.dynamodb.Table(
            f"{name}-jobs",
            name=f"code-remote-{env}-jobs",
            billing_mode="PAY_PER_REQUEST",
            hash_key="job_id",
            attributes=[
                {"name": "job_id", "type": "S"},
                {"name": "user_id", "type": "S"},
                {"name": "created_at", "type": "S"},
            ],
            global_secondary_indexes=[{
                "name": "user_id-created_at-index",
                "hash_key": "user_id",
                "range_key": "created_at",
                "projection_type": "ALL",
            }],
            ttl={"attribute_name": "ttl", "enabled": True},
            opts=pulumi.ResourceOptions(parent=self),
        )
        
        # Connections table
        self.connections_table = aws.dynamodb.Table(
            f"{name}-connections",
            name=f"code-remote-{env}-connections",
            billing_mode="PAY_PER_REQUEST",
            hash_key="connection_id",
            attributes=[
                {"name": "connection_id", "type": "S"},
                {"name": "user_id", "type": "S"},
            ],
            global_secondary_indexes=[{
                "name": "user_id-index",
                "hash_key": "user_id",
                "projection_type": "ALL",
            }],
            ttl={"attribute_name": "ttl", "enabled": True},
            opts=pulumi.ResourceOptions(parent=self),
        )
```

### SQS FIFO Queue

```python
# components/messaging.py

class Messaging(pulumi.ComponentResource):
    def __init__(self, name: str, opts=None, **kwargs):
        super().__init__("coderemote:messaging:Queues", name, None, opts)
        
        env = pulumi.get_stack()
        
        # Dead letter queue
        self.dlq = aws.sqs.Queue(
            f"{name}-dlq",
            name=f"code-remote-{env}-execution-dlq.fifo",
            fifo_queue=True,
            message_retention_seconds=1209600,  # 14 days
            opts=pulumi.ResourceOptions(parent=self),
        )
        
        # Main execution queue
        self.queue = aws.sqs.Queue(
            f"{name}-queue",
            name=f"code-remote-{env}-execution.fifo",
            fifo_queue=True,
            content_based_deduplication=False,  # Using job_id
            visibility_timeout_seconds=60,  # 2x max execution time
            redrive_policy=self.dlq.arn.apply(lambda arn: json.dumps({
                "deadLetterTargetArn": arn,
                "maxReceiveCount": 3,
            })),
            opts=pulumi.ResourceOptions(parent=self),
        )
```

## IAM Policies

### Worker Lambda Permissions

```python
worker_policy = aws.iam.Policy(
    "worker-policy",
    policy=pulumi.Output.all(
        jobs_table.arn,
        connections_table.arn,
        queue.arn,
        ws_api.id,
    ).apply(lambda args: json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                ],
                "Resource": [args[0], f"{args[0]}/index/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["dynamodb:Query"],
                "Resource": [args[1], f"{args[1]}/index/*"],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                ],
                "Resource": args[2],
            },
            {
                "Effect": "Allow",
                "Action": ["execute-api:ManageConnections"],
                "Resource": f"arn:aws:execute-api:*:*:{args[3]}/*",
            },
        ],
    })),
)
```

## Stack Outputs

```python
# __main__.py exports

pulumi.export("api_endpoint", api.endpoint)
pulumi.export("websocket_endpoint", websocket.endpoint)
pulumi.export("api_function_name", compute.api_function.name)
pulumi.export("worker_function_name", compute.worker_function.name)
pulumi.export("ecr_api_repository_url", storage.api_repo.repository_url)
pulumi.export("frontend_url", cdn.distribution_domain)
pulumi.export("frontend_bucket_name", storage.frontend_bucket.bucket)
pulumi.export("cognito_user_pool_id", auth.user_pool.id)
pulumi.export("cognito_user_pool_client_id", auth.user_pool_client.id)
pulumi.export("jobs_table_name", database.jobs_table.name)
pulumi.export("connections_table_name", database.connections_table.name)
pulumi.export("execution_queue_url", messaging.queue.url)
```

## Environment Configuration

### Pulumi.dev.yaml

```yaml
config:
  aws:region: us-east-1
  code-remote:environment: dev
  code-remote:domain: ""  # No custom domain for dev
  code-remote:log_level: DEBUG
```

### Pulumi.prod.yaml

```yaml
config:
  aws:region: us-east-1
  code-remote:environment: prod
  code-remote:domain: "coderemote.example.com"  # Custom domain
  code-remote:log_level: INFO
```

## Deployment Commands

```bash
# Preview changes
pulumi preview --stack dev

# Deploy
pulumi up --stack dev --yes

# Get outputs
pulumi stack output --stack dev

# Destroy (careful!)
pulumi destroy --stack dev --yes
```

## Cost Optimization

| Service | Optimization | Monthly Estimate |
|---------|-------------|------------------|
| Lambda | ARM64, 256MB memory | ~$5-20 |
| DynamoDB | On-demand, TTL cleanup | ~$1-5 |
| API Gateway | Pay per request | ~$1-10 |
| SQS | FIFO with dedup | ~$1 |
| S3 + CloudFront | Minimal static hosting | ~$1 |
| **Total Dev** | | **~$10-40/month** |

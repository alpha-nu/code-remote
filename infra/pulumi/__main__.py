"""Code Remote Infrastructure - Main Entry Point.

This module orchestrates all AWS infrastructure components for the
Code Remote application using Pulumi with a serverless architecture.

Architecture:
- API: AWS Lambda + API Gateway (HTTP API v2) with in-process code execution
- WebSocket: API Gateway WebSocket for real-time updates
- Queue: SQS FIFO for async job processing
- Worker: Lambda consumer for code execution
- Auth: AWS Cognito
- Frontend: S3 + CloudFront CDN
- Secrets: AWS Secrets Manager
"""

import pulumi

from components.cognito import CognitoComponent
from components.database import DatabaseComponent
from components.ecr import ECRComponent
from components.frontend import FrontendComponent
from components.messaging import MessagingComponent
from components.migration import MigrationComponent
from components.neo4j import Neo4jComponent
from components.neo4j_migration import Neo4jMigrationComponent
from components.secrets import SecretsComponent
from components.serverless_api import ServerlessAPIComponent
from components.sync_worker import SyncWorkerComponent
from components.vpc import VPCComponent
from components.websocket import WebSocketComponent
from components.worker import WorkerComponent

# Get configuration
config = pulumi.Config()
aws_config = pulumi.Config("aws")
environment = pulumi.get_stack()  # dev, staging, or prod
aws_region = aws_config.require("region")  # Get from aws:region config

# LLM Configuration (hierarchical)
llm_config = config.require_object("llm")
llm_analysis = llm_config.get("analysis", {})
llm_cypher = llm_config.get("cypher", {})
llm_embedding = llm_config.get("embedding", {})

# Extract LLM settings with defaults
llm_analysis_model = llm_analysis.get("model", "gemini-2.5-flash")
llm_analysis_temperature = str(llm_analysis.get("temperature", 0.1))
llm_analysis_max_tokens = str(llm_analysis.get("max_tokens", 2048))
llm_analysis_thinking_budget = str(
    llm_analysis.get("thinking_budget", -1)
)  # -1 = dynamic
llm_cypher_model = llm_cypher.get("model", "gemini-2.5-flash")
llm_cypher_temperature = str(llm_cypher.get("temperature", 0.1))
llm_cypher_max_tokens = str(llm_cypher.get("max_tokens", 500))
llm_cypher_thinking_budget = str(llm_cypher.get("thinking_budget", -1))  # -1 = dynamic
llm_embedding_model = llm_embedding.get("model", "gemini-embedding-001")

# Sync provider & Neo4j Configuration
sync_provider = (
    config.get("sync_provider") or ""
)  # Optional: e.g., api.services.sync.sqs.SQSSyncProvider
neo4j_uri = config.get("neo4j_uri") or ""  # Optional: Neo4j AuraDB URI
neo4j_password = config.get_secret(
    "neo4j_password"
)  # Optional: Neo4j password (secret)

# Common tags for all resources
common_tags = {
    "Project": "code-remote",
    "Environment": environment,
    "ManagedBy": "pulumi",
}

# =============================================================================
# VPC - Network Foundation
# =============================================================================
vpc = VPCComponent(
    f"{environment}-vpc",
    environment=environment,
    cidr_block=config.get("vpc_cidr") or "10.0.0.0/16",
    availability_zones=config.get_int("az_count") or 2,
    tags=common_tags,
)

# =============================================================================
# ECR - Container Registry
# =============================================================================
ecr = ECRComponent(
    f"{environment}-ecr",
    environment=environment,
    tags=common_tags,
)

# =============================================================================
# Secrets Manager
# =============================================================================
secrets = SecretsComponent(
    f"{environment}-secrets",
    environment=environment,
    tags=common_tags,
)

# =============================================================================
# Frontend - S3 + CloudFront (before Cognito so we can set callback URLs)
# =============================================================================
frontend = FrontendComponent(
    f"{environment}-frontend",
    environment=environment,
    tags=common_tags,
)

# =============================================================================
# Cognito - Authentication
# =============================================================================
cognito = CognitoComponent(
    f"{environment}-cognito",
    environment=environment,
    frontend_url=frontend.distribution.domain_name.apply(lambda d: f"https://{d}"),
    tags=common_tags,
)

# =============================================================================
# Messaging - SQS Queues (before API so queue URL can be passed)
# =============================================================================
messaging = MessagingComponent(
    f"{environment}-messaging",
    environment=environment,
    tags=common_tags,
)

# =============================================================================
# Database - Aurora PostgreSQL Serverless v2
# =============================================================================
database = DatabaseComponent(
    f"{environment}-database",
    environment=environment,
    vpc_id=vpc.vpc.id,
    subnet_ids=vpc.private_subnet_ids,
    tags=common_tags,
)

# =============================================================================
# Neo4j - AuraDB Configuration & Sync Queue
# =============================================================================
neo4j = (
    Neo4jComponent(
        f"{environment}-neo4j",
        environment=environment,
        neo4j_uri=neo4j_uri,
        neo4j_password=neo4j_password or pulumi.Output.from_input(""),
        tags=common_tags,
    )
    if neo4j_uri and neo4j_password
    else None
)

# =============================================================================
# WebSocket - Real-time Communication
# =============================================================================
websocket = WebSocketComponent(
    f"{environment}-websocket",
    environment=environment,
    tags=common_tags,
)

# =============================================================================
# Serverless API - Lambda + API Gateway
# =============================================================================
api = ServerlessAPIComponent(
    f"{environment}-api",
    environment=environment,
    vpc_id=vpc.vpc.id,
    subnet_ids=vpc.private_subnet_ids,
    ecr_repository_url=ecr.api_repository.repository_url,
    cognito_user_pool_arn=cognito.user_pool.arn,
    cognito_user_pool_client_id=cognito.user_pool_client.id,
    secrets_arn=secrets.gemini_api_key.arn,
    queue_url=messaging.queue.url,
    database_security_group_id=database.security_group.id,
    neo4j_secret_arn=neo4j.credentials_secret.arn if neo4j else None,
    websocket_api_id=websocket.api.id,
    websocket_endpoint=websocket.management_endpoint,
    image_tag="latest",
    env_vars={
        # Note: AWS_REGION is automatically set by Lambda runtime
        "COGNITO_USER_POOL_ID": cognito.user_pool.id,
        "COGNITO_CLIENT_ID": cognito.user_pool_client.id,
        # LLM Analysis settings
        "LLM_ANALYSIS_MODEL": llm_analysis_model,
        "LLM_ANALYSIS_TEMPERATURE": llm_analysis_temperature,
        "LLM_ANALYSIS_MAX_TOKENS": llm_analysis_max_tokens,
        "LLM_ANALYSIS_THINKING_BUDGET": llm_analysis_thinking_budget,
        # LLM Cypher settings
        "LLM_CYPHER_MODEL": llm_cypher_model,
        "LLM_CYPHER_TEMPERATURE": llm_cypher_temperature,
        "LLM_CYPHER_MAX_TOKENS": llm_cypher_max_tokens,
        "LLM_CYPHER_THINKING_BUDGET": llm_cypher_thinking_budget,
        # LLM Embedding settings
        "LLM_EMBEDDING_MODEL": llm_embedding_model,
        "DEBUG": "false" if environment == "prod" else "true",
        "CORS_ORIGINS": '["*"]',  # API Gateway handles CORS
        "DATABASE_SECRET_ARN": database.connection_secret.arn,
        # Sync provider class (IoC — fully-qualified Python class name)
        "SYNC_PROVIDER": sync_provider,
        # Neo4j sync queue (if configured)
        "SNIPPET_SYNC_QUEUE_URL": neo4j.sync_queue.url if neo4j else "",
        "NEO4J_SECRET_ARN": neo4j.credentials_secret.arn if neo4j else "",
    },
    tags=common_tags,
)

# =============================================================================
# Worker - SQS Consumer for Code Execution
# =============================================================================
worker = WorkerComponent(
    f"{environment}-worker",
    environment=environment,
    vpc_id=vpc.vpc.id,
    subnet_ids=vpc.private_subnet_ids,
    ecr_repository_url=ecr.api_repository.repository_url,
    queue_arn=messaging.queue.arn,
    websocket_api_id=websocket.api.id,
    websocket_endpoint=websocket.management_endpoint,
    secrets_arn=secrets.gemini_api_key.arn,
    image_tag="latest",
    tags=common_tags,
)

# =============================================================================
# Sync Worker - SQS Consumer for Neo4j Synchronization
# =============================================================================
sync_worker = (
    SyncWorkerComponent(
        f"{environment}-sync-worker",
        environment=environment,
        vpc_id=vpc.vpc.id,
        subnet_ids=vpc.private_subnet_ids,
        ecr_repository_url=ecr.api_repository.repository_url,
        sync_queue_arn=neo4j.sync_queue.arn if neo4j else pulumi.Output.from_input(""),
        neo4j_secret_arn=neo4j.credentials_secret.arn
        if neo4j
        else pulumi.Output.from_input(""),
        gemini_secret_arn=secrets.gemini_api_key.arn,
        llm_embedding_model=llm_embedding_model,
        database_secret_arn=database.connection_secret.arn,
        database_security_group_id=database.security_group.id,
        image_tag="latest",
        tags=common_tags,
    )
    if neo4j
    else None
)

# =============================================================================
# Stack Outputs
# =============================================================================

# VPC outputs
pulumi.export("vpc_id", vpc.vpc.id)
pulumi.export("public_subnet_ids", vpc.public_subnet_ids)
pulumi.export("private_subnet_ids", vpc.private_subnet_ids)

# ECR outputs
pulumi.export("ecr_api_repository_url", ecr.api_repository.repository_url)

# Secrets outputs (ARNs only, not values)
pulumi.export("gemini_api_key_secret_arn", secrets.gemini_api_key.arn)

# Cognito outputs
pulumi.export("cognito_user_pool_id", cognito.user_pool.id)
pulumi.export("cognito_user_pool_client_id", cognito.user_pool_client.id)
pulumi.export("cognito_user_pool_endpoint", cognito.user_pool.endpoint)

# Database outputs
pulumi.export("database_endpoint", database.endpoint)
pulumi.export("database_connection_secret_arn", database.connection_secret.arn)

# Migration Lambda - runs Alembic migrations during deployment
migration = MigrationComponent(
    f"{environment}-migration",
    environment=environment,
    vpc_id=vpc.vpc.id,
    subnet_ids=vpc.private_subnet_ids,
    ecr_repository_url=ecr.api_repository.repository_url,
    database_secret_arn=database.connection_secret.arn,
    database_security_group_id=database.security_group.id,
    image_tag="latest",
    tags=common_tags,
)

# Neo4j Migration Lambda - runs Neo4j schema migrations during deployment
neo4j_migration = (
    Neo4jMigrationComponent(
        f"{environment}-neo4j-migration",
        environment=environment,
        vpc_id=vpc.vpc.id,
        subnet_ids=vpc.private_subnet_ids,
        ecr_repository_url=ecr.api_repository.repository_url,
        neo4j_secret_arn=neo4j.credentials_secret.arn
        if neo4j
        else pulumi.Output.from_input(""),
        image_tag="latest",
        tags=common_tags,
    )
    if neo4j
    else None
)

# API outputs
pulumi.export("api_endpoint", api.api_endpoint)
pulumi.export("api_function_name", api.function.name)
pulumi.export("migration_function_name", migration.function.name)

# Neo4j outputs (if configured)
if neo4j:
    pulumi.export("neo4j_credentials_secret_arn", neo4j.credentials_secret.arn)
    pulumi.export("snippet_sync_queue_url", neo4j.sync_queue.url)
    pulumi.export("snippet_sync_queue_arn", neo4j.sync_queue.arn)
if neo4j_migration:
    pulumi.export("neo4j_migration_function_name", neo4j_migration.function.name)
if sync_worker:
    pulumi.export("sync_worker_function_name", sync_worker.function.name)

# Messaging outputs
pulumi.export("execution_queue_url", messaging.queue.url)
pulumi.export("execution_queue_arn", messaging.queue.arn)

# WebSocket outputs
pulumi.export("websocket_endpoint", websocket.endpoint)
pulumi.export("websocket_api_id", websocket.api.id)

# Worker outputs
pulumi.export("worker_function_name", worker.function.name)

# Frontend outputs
pulumi.export("frontend_bucket_name", frontend.bucket.bucket)
pulumi.export("frontend_distribution_id", frontend.distribution.id)
pulumi.export(
    "frontend_url", frontend.distribution.domain_name.apply(lambda d: f"https://{d}")
)

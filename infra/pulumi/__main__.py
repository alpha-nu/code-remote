"""Code Remote Infrastructure - Main Entry Point.

This module orchestrates all AWS infrastructure components for the
Code Remote application using Pulumi with a serverless architecture.

Architecture:
- API: AWS Lambda + API Gateway (HTTP API v2) with in-process code execution
- Auth: AWS Cognito
- Frontend: S3 + CloudFront CDN
- Secrets: AWS Secrets Manager
"""

import pulumi

from components.cognito import CognitoComponent
from components.ecr import ECRComponent
from components.frontend import FrontendComponent
from components.secrets import SecretsComponent
from components.serverless_api import ServerlessAPIComponent
from components.vpc import VPCComponent

# Get configuration
config = pulumi.Config()
aws_config = pulumi.Config("aws")
environment = pulumi.get_stack()  # dev, staging, or prod
aws_region = aws_config.require("region")  # Get from aws:region config
gemini_model = config.require("gemini_model")  # Required: e.g., gemini-2.5-flash

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
# Cognito - Authentication
# =============================================================================
cognito = CognitoComponent(
    f"{environment}-cognito",
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
    image_tag="latest",
    env_vars={
        # Note: AWS_REGION is automatically set by Lambda runtime
        "COGNITO_USER_POOL_ID": cognito.user_pool.id,
        "COGNITO_CLIENT_ID": cognito.user_pool_client.id,
        "GEMINI_MODEL": gemini_model,
        "DEBUG": "false" if environment == "prod" else "true",
        "CORS_ORIGINS": '["*"]',  # API Gateway handles CORS
    },
    tags=common_tags,
)

# =============================================================================
# Frontend - S3 + CloudFront
# =============================================================================
frontend = FrontendComponent(
    f"{environment}-frontend",
    environment=environment,
    tags=common_tags,
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

# API outputs
pulumi.export("api_endpoint", api.api_endpoint)
pulumi.export("api_function_name", api.function.name)

# Frontend outputs
pulumi.export("frontend_bucket_name", frontend.bucket.bucket)
pulumi.export("frontend_distribution_id", frontend.distribution.id)
pulumi.export(
    "frontend_url", frontend.distribution.domain_name.apply(lambda d: f"https://{d}")
)

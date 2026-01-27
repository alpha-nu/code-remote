"""Code Remote Infrastructure - Main Entry Point.

This module orchestrates all AWS infrastructure components for the
Code Remote application using Pulumi.
"""

import pulumi

from components.cognito import CognitoComponent
from components.ecr import ECRComponent
from components.secrets import SecretsComponent
from components.vpc import VPCComponent

# Get configuration
config = pulumi.Config()
environment = pulumi.get_stack()  # dev, staging, or prod

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
# Stack Outputs
# =============================================================================

# VPC outputs
pulumi.export("vpc_id", vpc.vpc.id)
pulumi.export("public_subnet_ids", vpc.public_subnet_ids)
pulumi.export("private_subnet_ids", vpc.private_subnet_ids)

# ECR outputs
pulumi.export("ecr_api_repository_url", ecr.api_repository.repository_url)
pulumi.export("ecr_executor_repository_url", ecr.executor_repository.repository_url)

# Secrets outputs (ARNs only, not values)
pulumi.export("gemini_api_key_secret_arn", secrets.gemini_api_key.arn)

# Cognito outputs
pulumi.export("cognito_user_pool_id", cognito.user_pool.id)
pulumi.export("cognito_user_pool_client_id", cognito.user_pool_client.id)
pulumi.export("cognito_user_pool_endpoint", cognito.user_pool.endpoint)

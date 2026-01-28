"""Components package for Pulumi infrastructure.

Serverless Architecture:
- ServerlessAPIComponent: Lambda + API Gateway for the backend API
- FargateExecutorComponent: ECS Fargate for sandboxed code execution
- CognitoComponent: User authentication
- FrontendComponent: S3 + CloudFront for static site hosting
"""

from components.cognito import CognitoComponent
from components.ecr import ECRComponent
from components.fargate_executor import FargateExecutorComponent
from components.frontend import FrontendComponent
from components.secrets import SecretsComponent
from components.serverless_api import ServerlessAPIComponent
from components.vpc import VPCComponent

__all__ = [
    "CognitoComponent",
    "ECRComponent",
    "FargateExecutorComponent",
    "FrontendComponent",
    "SecretsComponent",
    "ServerlessAPIComponent",
    "VPCComponent",
]

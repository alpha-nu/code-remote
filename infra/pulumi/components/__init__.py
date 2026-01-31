"""Components package for Pulumi infrastructure.

Serverless Architecture:
- ServerlessAPIComponent: Lambda + API Gateway for the backend API
- CognitoComponent: User authentication
- FrontendComponent: S3 + CloudFront for static site hosting
"""

from components.cognito import CognitoComponent
from components.ecr import ECRComponent
from components.frontend import FrontendComponent
from components.secrets import SecretsComponent
from components.serverless_api import ServerlessAPIComponent
from components.vpc import VPCComponent

__all__ = [
    "CognitoComponent",
    "ECRComponent",
    "FrontendComponent",
    "SecretsComponent",
    "ServerlessAPIComponent",
    "VPCComponent",
]

"""Authentication module for JWT validation with AWS Cognito."""

from api.auth.cognito import CognitoAuth, get_cognito_auth
from api.auth.dependencies import get_current_user, get_optional_user
from api.auth.models import User

__all__ = [
    "CognitoAuth",
    "get_cognito_auth",
    "get_current_user",
    "get_optional_user",
    "User",
]

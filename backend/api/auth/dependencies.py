"""FastAPI dependencies for authentication."""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth.cognito import (
    CognitoAuth,
    CognitoAuthError,
    InvalidTokenError,
    TokenExpiredError,
    get_cognito_auth,
)
from api.auth.models import User

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for OpenAPI docs
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth: CognitoAuth = Depends(get_cognito_auth),
) -> User:
    """FastAPI dependency to get the current authenticated user.

    Extracts and validates the JWT token from the Authorization header.

    Args:
        credentials: Bearer token from Authorization header
        auth: Cognito auth validator

    Returns:
        Authenticated User object

    Raises:
        HTTPException: 401 if token is missing, expired, or invalid
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = auth.decode_token(token)
        return User.from_token_payload(payload)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth: CognitoAuth = Depends(get_cognito_auth),
) -> User | None:
    """FastAPI dependency to optionally get the current user.

    Same as get_current_user but returns None instead of raising
    an exception when no valid token is provided.

    Args:
        credentials: Bearer token from Authorization header
        auth: Cognito auth validator

    Returns:
        User object if authenticated, None otherwise
    """
    if credentials is None:
        return None

    try:
        payload = auth.decode_token(credentials.credentials)
        return User.from_token_payload(payload)
    except CognitoAuthError:
        return None

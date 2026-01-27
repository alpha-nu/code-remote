"""AWS Cognito JWT token validation."""

from functools import lru_cache

import jwt
from jwt import PyJWKClient, PyJWKClientError

from common.config import settings


class CognitoAuthError(Exception):
    """Base exception for Cognito authentication errors."""

    pass


class TokenExpiredError(CognitoAuthError):
    """Token has expired."""

    pass


class InvalidTokenError(CognitoAuthError):
    """Token is invalid or malformed."""

    pass


class CognitoAuth:
    """AWS Cognito JWT token validator.

    Validates JWT tokens issued by AWS Cognito using JWKS (JSON Web Key Set).
    Keys are cached and refreshed as needed.
    """

    def __init__(
        self,
        user_pool_id: str,
        client_id: str,
        region: str,
    ):
        """Initialize Cognito auth validator.

        Args:
            user_pool_id: Cognito User Pool ID (e.g., 'us-east-1_XXXXXXXXX')
            client_id: Cognito App Client ID
            region: AWS region (e.g., 'us-east-1')
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region

        # Cognito JWKS URL
        self.jwks_url = (
            f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        )

        # Expected issuer for token validation
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

        # JWKS client for fetching public keys
        self._jwk_client: PyJWKClient | None = None

    @property
    def jwk_client(self) -> PyJWKClient:
        """Lazily initialize JWKS client."""
        if self._jwk_client is None:
            self._jwk_client = PyJWKClient(self.jwks_url)
        return self._jwk_client

    def decode_token(self, token: str) -> dict:
        """Decode and validate a Cognito JWT token.

        Args:
            token: JWT token string (access or ID token)

        Returns:
            Decoded token payload as dictionary

        Raises:
            TokenExpiredError: If the token has expired
            InvalidTokenError: If the token is invalid or verification fails
        """
        try:
            # Get the signing key from JWKS
            signing_key = self.jwk_client.get_signing_key_from_jwt(token)

            # Decode and verify the token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )

            return payload

        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired") from e
        except jwt.InvalidAudienceError as e:
            raise InvalidTokenError("Invalid token audience") from e
        except jwt.InvalidIssuerError as e:
            raise InvalidTokenError("Invalid token issuer") from e
        except PyJWKClientError as e:
            raise InvalidTokenError(f"Failed to fetch signing key: {e}") from e
        except jwt.PyJWTError as e:
            raise InvalidTokenError(f"Token validation failed: {e}") from e

    def is_token_valid(self, token: str) -> bool:
        """Check if a token is valid without raising exceptions.

        Args:
            token: JWT token string

        Returns:
            True if token is valid, False otherwise
        """
        try:
            self.decode_token(token)
            return True
        except CognitoAuthError:
            return False


@lru_cache
def get_cognito_auth() -> CognitoAuth:
    """Get cached Cognito auth instance.

    Returns:
        CognitoAuth instance configured from settings
    """
    return CognitoAuth(
        user_pool_id=settings.cognito_user_pool_id,
        client_id=settings.cognito_client_id,
        region=settings.cognito_region,
    )

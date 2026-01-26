"""User model for authenticated requests."""

from dataclasses import dataclass


@dataclass
class User:
    """Authenticated user from Cognito JWT token."""

    id: str  # Cognito 'sub' claim
    email: str | None = None
    username: str | None = None
    groups: list[str] | None = None

    @classmethod
    def from_token_payload(cls, payload: dict) -> "User":
        """Create User from decoded JWT token payload.

        Args:
            payload: Decoded JWT claims from Cognito token.

        Returns:
            User instance with extracted claims.
        """
        return cls(
            id=payload.get("sub", ""),
            email=payload.get("email"),
            username=payload.get("cognito:username") or payload.get("username"),
            groups=payload.get("cognito:groups"),
        )

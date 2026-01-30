"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_secret_from_aws(secret_arn: str) -> str:
    """Fetch a secret value from AWS Secrets Manager.

    Args:
        secret_arn: The ARN or name of the secret.

    Returns:
        The secret value, or empty string if not found.
    """
    if not secret_arn:
        return ""

    try:
        import boto3

        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        return response.get("SecretString", "")
    except Exception:
        return ""


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All values must be provided via environment variables or .env file.
    See .env.example for required configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Code Remote"
    debug: bool = False
    environment: str = "development"

    # Server (not needed in Lambda mode)
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: list[str] = ["*"]

    # Execution limits
    execution_timeout_seconds: int = 30
    max_code_size_bytes: int = 10240  # 10KB

    # Redis (for queue) - optional in serverless mode
    redis_url: str = ""

    # Database - optional in serverless mode
    database_url: str = ""

    # Gemini LLM (API key only - no GCP project required)
    gemini_api_key: str = ""
    gemini_api_key_secret_arn: str = ""  # AWS Secrets Manager ARN
    gemini_model: str = "gemini-2.5-flash"  # Model name for Gemini API

    # AWS Configuration
    aws_region: str = "us-east-1"  # Default AWS region for all services

    # AWS Cognito Authentication
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = ""  # Falls back to aws_region if not set

    # Fargate Executor (for Lambda mode)
    fargate_cluster_arn: str = ""
    fargate_task_definition_arn: str = ""
    fargate_subnets: str = ""  # Comma-separated subnet IDs
    fargate_security_group_id: str = ""

    # Development settings (NEVER enable in production!)
    dev_auth_bypass: bool = False

    @property
    def resolved_gemini_api_key(self) -> str:
        """Get Gemini API key, fetching from Secrets Manager if needed."""
        if self.gemini_api_key:
            return self.gemini_api_key
        if self.gemini_api_key_secret_arn:
            return get_secret_from_aws(self.gemini_api_key_secret_arn)
        return ""

    @property
    def resolved_cognito_region(self) -> str:
        """Get Cognito region, falling back to aws_region if not set."""
        return self.cognito_region or self.aws_region
        return ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

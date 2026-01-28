"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # AWS Cognito Authentication
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

    # Fargate Executor (for Lambda mode)
    fargate_cluster_arn: str = ""
    fargate_task_definition_arn: str = ""
    fargate_subnets: str = ""  # Comma-separated subnet IDs
    fargate_security_group_id: str = ""

    # Development settings (NEVER enable in production!)
    dev_auth_bypass: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

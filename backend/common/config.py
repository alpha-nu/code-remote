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
    app_name: str
    debug: bool
    environment: str

    # Server
    host: str
    port: int

    # CORS
    cors_origins: list[str]

    # Execution limits
    execution_timeout_seconds: int
    max_code_size_bytes: int

    # Redis (for queue)
    redis_url: str

    # Database
    database_url: str

    # Gemini LLM (API key only - no GCP project required)
    gemini_api_key: str

    # AWS Cognito Authentication
    cognito_user_pool_id: str
    cognito_client_id: str
    cognito_region: str

    # Development settings (NEVER enable in production!)
    dev_auth_bypass: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

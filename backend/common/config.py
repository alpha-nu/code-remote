"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "code-remote"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Execution limits
    execution_timeout_seconds: int = 30
    max_code_size_bytes: int = 10240  # 10KB

    # Redis (for queue)
    redis_url: str = "redis://localhost:6379"

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/coderemote"

    # Gemini LLM (API key only - no GCP project required)
    gemini_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

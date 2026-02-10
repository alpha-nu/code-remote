"""Application configuration using Pydantic Settings."""

import json
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
        import logging

        import boto3

        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        return response.get("SecretString", "")
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(f"Failed to fetch secret {secret_arn}: {e}")
        return ""


def get_database_url_from_aws(secret_arn: str) -> str:
    """Fetch database URL from AWS Secrets Manager.

    The database secret is stored as JSON with a 'url' field.

    Args:
        secret_arn: The ARN or name of the secret.

    Returns:
        The database URL, or empty string if not found.
    """
    secret_string = get_secret_from_aws(secret_arn)
    if not secret_string:
        return ""

    try:
        secret_data = json.loads(secret_string)
        return secret_data.get("url", "")
    except (json.JSONDecodeError, TypeError):
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

    # Extra allowed imports (environment-specific, comma-separated)
    # Example: "numpy,pandas,scipy" to allow data science libs in dev
    extra_allowed_imports: str = ""

    # Redis (for queue) - optional in serverless mode
    redis_url: str = ""

    # Database - optional in serverless mode
    database_url: str = ""
    database_secret_arn: str = ""  # AWS Secrets Manager ARN for DB connection

    # Gemini LLM - API Key (shared across all LLM operations)
    gemini_api_key: str = ""
    gemini_api_key_secret_arn: str = ""  # AWS Secrets Manager ARN

    # LLM Analysis settings (complexity analysis)
    # All values MUST be set via environment variables (no defaults)
    llm_analysis_model: str = ""  # Required: e.g., gemini-2.5-flash
    llm_analysis_temperature: float | None = None  # Required: e.g., 0.1
    llm_analysis_max_tokens: int | None = None  # Required: e.g., 2048
    llm_analysis_thinking_budget: int | None = None  # Optional: -1=dynamic, 0=off

    # LLM Cypher settings (Text-to-Cypher generation)
    # All values MUST be set via environment variables (no defaults)
    llm_cypher_model: str = ""  # Required: e.g., gemini-2.5-flash
    llm_cypher_temperature: float | None = None  # Required: e.g., 0.1
    llm_cypher_max_tokens: int | None = None  # Required: e.g., 500
    llm_cypher_thinking_budget: int | None = None  # Optional: -1=dynamic, 0=off

    # LLM Embedding settings
    llm_embedding_model: str = ""  # Required: e.g., gemini-embedding-001

    # AWS Configuration
    aws_region: str = ""  # AWS region for all services

    # Async Execution (SQS + WebSocket)
    execution_queue_url: str = ""  # SQS FIFO queue for async execution jobs
    websocket_endpoint: str = ""  # WebSocket API Gateway endpoint (wss://...)

    # Neo4j AuraDB
    neo4j_uri: str = ""  # e.g., neo4j+ssc://xxx.databases.neo4j.io:7687
    neo4j_username: str = ""
    neo4j_password: str = ""
    neo4j_database: str = ""
    neo4j_secret_arn: str = ""  # AWS Secrets Manager ARN for Neo4j credentials

    # Embedding (Gemini embedding model)
    gemini_embedding_model: str = ""

    # Neo4j Sync Configuration
    # SYNC_PROVIDER: Fully-qualified Python class name of the SyncProvider to use.
    #   Production:  api.services.sync.sqs.SQSSyncProvider
    #   Local dev:   api.services.sync.direct.DirectSyncProvider
    #   Disabled:    "" (empty — semantic search won't be updated)
    sync_provider: str = ""
    snippet_sync_queue_url: str = ""  # Required when using SQSSyncProvider

    # AWS Cognito Authentication
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = ""  # Falls back to aws_region if not set

    @property
    def resolved_database_url(self) -> str:
        """Get database URL, fetching from Secrets Manager if needed."""
        if self.database_url:
            return self.database_url
        if self.database_secret_arn:
            return get_database_url_from_aws(self.database_secret_arn)
        return ""

    @property
    def resolved_gemini_api_key(self) -> str:
        """Get Gemini API key, fetching from Secrets Manager if needed."""
        if self.gemini_api_key:
            return self.gemini_api_key
        if self.gemini_api_key_secret_arn:
            return get_secret_from_aws(self.gemini_api_key_secret_arn)
        return ""

    @property
    def resolved_llm_analysis_model(self) -> str:
        """Get analysis model.

        Raises:
            ValueError: If not configured.
        """
        if not self.llm_analysis_model:
            raise ValueError("LLM_ANALYSIS_MODEL must be set")
        return self.llm_analysis_model

    @property
    def resolved_llm_cypher_model(self) -> str:
        """Get cypher model.

        Raises:
            ValueError: If not configured.
        """
        if not self.llm_cypher_model:
            raise ValueError("LLM_CYPHER_MODEL must be set")
        return self.llm_cypher_model

    @property
    def resolved_llm_embedding_model(self) -> str:
        """Get embedding model.

        Raises:
            ValueError: If not configured.
        """
        if not self.llm_embedding_model:
            raise ValueError("LLM_EMBEDDING_MODEL must be set")
        return self.llm_embedding_model

    @property
    def resolved_llm_analysis_temperature(self) -> float:
        """Get analysis temperature.

        Raises:
            ValueError: If not configured.
        """
        if self.llm_analysis_temperature is None:
            raise ValueError("LLM_ANALYSIS_TEMPERATURE must be set")
        return self.llm_analysis_temperature

    @property
    def resolved_llm_analysis_max_tokens(self) -> int:
        """Get analysis max tokens.

        Raises:
            ValueError: If not configured.
        """
        if self.llm_analysis_max_tokens is None:
            raise ValueError("LLM_ANALYSIS_MAX_TOKENS must be set")
        return self.llm_analysis_max_tokens

    @property
    def resolved_llm_cypher_temperature(self) -> float:
        """Get cypher temperature.

        Raises:
            ValueError: If not configured.
        """
        if self.llm_cypher_temperature is None:
            raise ValueError("LLM_CYPHER_TEMPERATURE must be set")
        return self.llm_cypher_temperature

    @property
    def resolved_llm_cypher_max_tokens(self) -> int:
        """Get cypher max tokens.

        Raises:
            ValueError: If not configured.
        """
        if self.llm_cypher_max_tokens is None:
            raise ValueError("LLM_CYPHER_MAX_TOKENS must be set")
        return self.llm_cypher_max_tokens

    @property
    def resolved_llm_analysis_thinking_budget(self) -> int | None:
        """Get analysis thinking budget.

        Returns:
            Thinking budget (-1=dynamic, 0=off, positive=budget), or None if not set.
        """
        return self.llm_analysis_thinking_budget

    @property
    def resolved_llm_cypher_thinking_budget(self) -> int | None:
        """Get cypher thinking budget.

        Returns:
            Thinking budget (-1=dynamic, 0=off, positive=budget), or None if not set.
        """
        return self.llm_cypher_thinking_budget

    @property
    def resolved_cognito_region(self) -> str:
        """Get Cognito region, falling back to aws_region if not set."""
        return self.cognito_region or self.aws_region

    @property
    def extra_allowed_imports_set(self) -> set[str]:
        """Parse extra_allowed_imports into a set of module names."""
        if not self.extra_allowed_imports:
            return set()
        return {m.strip() for m in self.extra_allowed_imports.split(",") if m.strip()}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

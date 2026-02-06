"""Database connection and session management.

Provides async database engine and session factory for use
throughout the application. Handles connection pooling and
Lambda-specific optimizations.
"""

import json
import logging
from collections.abc import AsyncGenerator
from contextvars import ContextVar

import boto3
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from common.config import settings

logger = logging.getLogger(__name__)

# Context variable for request-scoped session
_session_context: ContextVar[AsyncSession | None] = ContextVar("db_session", default=None)

# Global engine (initialized lazily)
_engine = None
_session_factory = None
_sync_engine = None
_sync_session_factory = None


def _get_database_url() -> str:
    """Get database URL from settings or AWS Secrets Manager.

    In Lambda, reads from DATABASE_SECRET_ARN environment variable.
    In local development, uses DATABASE_URL from .env.
    """
    # First check if URL is directly configured
    if settings.database_url:
        return settings.database_url

    # Try to load from Secrets Manager (Lambda environment)
    secret_arn = settings.database_secret_arn
    if not secret_arn:
        raise ValueError("Database not configured. Set DATABASE_URL or DATABASE_SECRET_ARN")

    try:
        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        response = client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response["SecretString"])
        return secret["url"]
    except Exception as e:
        logger.error(f"Failed to load database credentials from Secrets Manager: {e}")
        raise


def get_engine():
    """Get or create the async database engine.

    Uses lazy initialization and connection pooling optimized for Lambda.
    """
    global _engine

    if _engine is None:
        url = _get_database_url()

        # Lambda-optimized pool settings
        # - pool_size=1: Lambda runs single request at a time
        # - max_overflow=0: Don't create extra connections
        # - pool_pre_ping=True: Verify connections are alive
        _engine = create_async_engine(
            url,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
            echo=settings.debug,
        )

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    return _session_factory


def _get_sync_database_url() -> str:
    """Convert async database URL to sync URL.

    Replaces postgresql+asyncpg:// with postgresql+psycopg2://
    """
    async_url = _get_database_url()
    # Convert asyncpg URL to psycopg2 URL
    if "asyncpg" in async_url:
        return async_url.replace("postgresql+asyncpg", "postgresql+psycopg2")
    elif async_url.startswith("postgresql://"):
        return async_url.replace("postgresql://", "postgresql+psycopg2://")
    return async_url


def get_sync_engine():
    """Get or create the sync database engine.

    Uses lazy initialization and connection pooling optimized for Lambda.
    """
    global _sync_engine

    if _sync_engine is None:
        url = _get_sync_database_url()

        # Lambda-optimized pool settings
        _sync_engine = create_engine(
            url,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
            echo=settings.debug,
        )

    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    """Get or create the sync session factory."""
    global _sync_session_factory

    if _sync_session_factory is None:
        engine = get_sync_engine()
        _sync_session_factory = sessionmaker(
            engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    return _sync_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields an async session and ensures it's closed after the request.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Close the database engine.

    Call during application shutdown.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None

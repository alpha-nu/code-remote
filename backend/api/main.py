"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import analysis, execution, health, search, snippets, websocket
from api.services.database import close_db
from common.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    yield
    # Shutdown - close database connections
    await close_db()


app = FastAPI(
    title="Code Remote API",
    description="Remote Code Execution Engine",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(execution.router, tags=["Execution"])
app.include_router(analysis.router, tags=["Analysis"])
app.include_router(snippets.router, tags=["Snippets"])
app.include_router(search.router, tags=["Search"])
app.include_router(websocket.router, tags=["WebSocket"])

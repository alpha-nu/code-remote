"""Pydantic schemas for complexity analysis endpoint."""

from uuid import UUID

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request to analyze code complexity (sync HTTP fallback)."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=10240,
        description="Python code to analyze",
    )
    snippet_id: UUID | None = Field(
        default=None,
        description="Optional snippet ID to persist complexity results",
    )


class AsyncAnalyzeRequest(BaseModel):
    """Request for async streaming analysis via WebSocket."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=10240,
        description="Python code to analyze",
    )
    connection_id: str = Field(
        ...,
        description="WebSocket connection ID for streaming results",
    )
    snippet_id: UUID | None = Field(
        default=None,
        description="Optional snippet ID to persist complexity results",
    )


class AnalyzeJobSubmittedResponse(BaseModel):
    """Response after submitting an async analysis job."""

    job_id: str = Field(description="Unique job identifier")
    status: str = Field(description="Job status (e.g. 'streaming')")


class AnalyzeResponse(BaseModel):
    """Response from complexity analysis."""

    success: bool = Field(description="Whether analysis succeeded")
    time_complexity: str = Field(description="Big O time complexity")
    space_complexity: str = Field(description="Big O space complexity")
    narrative: str = Field(
        default="",
        description="Full Markdown narrative (algorithm, explanations, suggestions)",
    )
    error: str | None = Field(
        default=None,
        description="Error message if analysis failed",
    )
    available: bool = Field(
        default=True,
        description="Whether LLM analysis is available (API key configured)",
    )
    model: str | None = Field(
        default=None,
        description="LLM model used for analysis",
    )

"""Pydantic schemas for complexity analysis endpoint."""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request to analyze code complexity."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=10240,
        description="Python code to analyze",
    )


class AnalyzeResponse(BaseModel):
    """Response from complexity analysis."""

    success: bool = Field(description="Whether analysis succeeded")
    time_complexity: str = Field(description="Big O time complexity")
    space_complexity: str = Field(description="Big O space complexity")
    time_explanation: str = Field(description="Explanation of time complexity")
    space_explanation: str = Field(description="Explanation of space complexity")
    algorithm_identified: str | None = Field(
        default=None,
        description="Name of identified algorithm, if any",
    )
    suggestions: list[str] | None = Field(
        default=None,
        description="Improvement suggestions",
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

"""Pydantic schemas for code execution."""

from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    """Request to execute Python code."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=10240,
        description="Python code to execute (max 10KB)",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=30.0,
        description="Maximum execution time in seconds (max 30s)",
    )


class AsyncExecutionRequest(BaseModel):
    """Request to execute Python code asynchronously with WebSocket callback."""

    code: str = Field(
        ...,
        min_length=1,
        max_length=10240,
        description="Python code to execute (max 10KB)",
    )
    connection_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="WebSocket connection ID for result delivery",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=30.0,
        description="Maximum execution time in seconds (max 30s)",
    )


class JobSubmittedResponse(BaseModel):
    """Response when an async job is submitted."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(default="queued", description="Job status")


class SecurityViolationResponse(BaseModel):
    """A security violation found in the code."""

    line: int
    column: int
    message: str


class ExecutionResponse(BaseModel):
    """Response from code execution."""

    success: bool = Field(..., description="Whether execution completed successfully")
    stdout: str = Field(default="", description="Standard output from execution")
    stderr: str = Field(default="", description="Standard error from execution")
    error: str | None = Field(default=None, description="Error message if execution failed")
    error_type: str | None = Field(default=None, description="Type of error (e.g., ValueError)")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    timed_out: bool = Field(default=False, description="Whether execution timed out")
    security_violations: list[SecurityViolationResponse] = Field(
        default_factory=list,
        description="Security violations found in the code",
    )

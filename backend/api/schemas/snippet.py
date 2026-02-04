"""Pydantic schemas for snippet CRUD endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SnippetCreate(BaseModel):
    """Schema for creating a new snippet."""

    code: str = Field(..., min_length=1, max_length=50000, description="The code content")
    title: str | None = Field(None, max_length=255, description="Optional snippet title")
    language: str = Field("python", max_length=50, description="Programming language")
    description: str | None = Field(None, max_length=2000, description="Optional description")
    is_starred: bool = Field(False, description="Whether snippet is starred/favorited")


class SnippetUpdate(BaseModel):
    """Schema for updating a snippet. All fields optional."""

    code: str | None = Field(None, min_length=1, max_length=50000)
    title: str | None = Field(None, max_length=255)
    language: str | None = Field(None, max_length=50)
    description: str | None = Field(None, max_length=2000)
    is_starred: bool | None = Field(None, description="Whether snippet is starred/favorited")


class SnippetSummary(BaseModel):
    """Schema for snippet summary in list responses (excludes code for efficiency)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    language: str
    description: str | None
    execution_count: int
    is_starred: bool
    last_execution_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SnippetResponse(BaseModel):
    """Schema for snippet in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    language: str
    code: str
    description: str | None
    execution_count: int
    is_starred: bool
    last_execution_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SnippetListResponse(BaseModel):
    """Schema for paginated snippet list (summaries without code)."""

    items: list[SnippetSummary]
    total: int
    limit: int
    offset: int


class SnippetDeleteResponse(BaseModel):
    """Schema for delete confirmation."""

    deleted: bool
    id: uuid.UUID

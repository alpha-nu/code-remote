"""Search schemas for semantic and graph search."""

from typing import Literal

from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    """A single search result item."""

    snippet_id: str = Field(description="UUID of the matching snippet")
    title: str | None = Field(default=None, description="Snippet title")
    language: str | None = Field(default="python", description="Programming language")
    description: str | None = Field(default=None, description="Snippet description")
    time_complexity: str | None = Field(default=None, description="Time complexity")
    space_complexity: str | None = Field(default=None, description="Space complexity")
    score: float = Field(default=1.0, description="Similarity score (0-1, higher is better)")


class UnifiedSearchResponse(BaseModel):
    """Response from unified search endpoint."""

    query: str = Field(description="Original search query")
    results: list[SearchResultItem] = Field(description="Matching snippets")
    method: Literal["cypher", "semantic"] = Field(
        description="Search method used: 'cypher' for Text-to-Cypher, 'semantic' for fallback"
    )
    total: int = Field(description="Number of results returned")


class ComplexityFilterResponse(BaseModel):
    """Response from complexity filter endpoint."""

    complexity_type: Literal["time", "space"] = Field(description="'time' or 'space'")
    complexity_value: str = Field(description="Complexity notation filter applied")
    results: list[SearchResultItem] = Field(description="Matching snippets")
    total: int = Field(description="Number of results returned")


class SimilarSnippetsResponse(BaseModel):
    """Response from similar snippets endpoint."""

    source_snippet_id: str = Field(description="UUID of the source snippet")
    similar: list[SearchResultItem] = Field(description="Similar snippets")
    total: int = Field(description="Number of similar snippets found")

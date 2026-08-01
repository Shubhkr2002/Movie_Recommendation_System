"""
Request schemas.

Every endpoint in this API is GET-based and driven by query parameters
(the original design already validates those inline via FastAPI's
`Query(...)`, e.g. `min_length=1`, `ge=1`, `le=50`). These models exist so
that any *future* POST-style endpoint (or an internal service call) has a
single, reusable, validated shape to import instead of loose dicts.
"""

from pydantic import BaseModel, Field


class MovieSearchRequest(BaseModel):
    """Validated shape of a movie search / recommendation lookup."""

    query: str = Field(..., min_length=1, description="Movie title or search text")
    tfidf_top_n: int = Field(12, ge=1, le=30)
    genre_limit: int = Field(12, ge=1, le=30)


class TFIDFRecommendRequest(BaseModel):
    """Validated shape for a plain TF-IDF recommendation request."""

    title: str = Field(..., min_length=1)
    top_n: int = Field(10, ge=1, le=50)

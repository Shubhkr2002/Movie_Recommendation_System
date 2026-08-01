"""
Response schemas.

These are a direct, unmodified port of the Pydantic models that already
lived in the original `main.py`. The recommendation *algorithm* is not
touched anywhere in this refactor - only its surrounding structure - so
these response shapes stay byte-for-byte compatible with the deployed
Streamlit frontend (`app.py`), which already parses these exact fields.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RootResponse(BaseModel):
    """Response body for GET /"""

    message: str
    version: str


class HealthResponse(BaseModel):
    """Response body for GET /health"""

    status: str


class TMDBMovieCard(BaseModel):
    """A lightweight movie card used in grids/lists (home feed, search, recs)."""

    tmdb_id: int
    title: str
    poster_url: Optional[str] = None
    release_date: Optional[str] = None
    vote_average: Optional[float] = None


class TMDBMovieDetails(BaseModel):
    """Full movie details, used by the movie detail page."""

    tmdb_id: int
    title: str
    overview: Optional[str] = None
    release_date: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    genres: List[Dict[str, Any]] = []


class TFIDFRecItem(BaseModel):
    """A single TF-IDF based recommendation, with an optional TMDB poster card."""

    title: str
    score: float
    tmdb: Optional[TMDBMovieCard] = None


class SearchBundleResponse(BaseModel):
    """
    Combined response for GET /movie/search:
      - resolved movie details
      - local TF-IDF content-based recommendations
      - TMDB genre-based recommendations
    """

    query: str
    movie_details: TMDBMovieDetails
    tfidf_recommendations: List[TFIDFRecItem]
    genre_recommendations: List[TMDBMovieCard]


class TFIDFOnlyItem(BaseModel):
    """Response item for the debug/utility GET /recommend/tfidf endpoint."""

    title: str
    score: float

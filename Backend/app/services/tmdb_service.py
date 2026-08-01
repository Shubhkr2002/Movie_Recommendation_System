"""
TMDB service.

This is the original `tmdb_get` / `tmdb_search_movies` / `tmdb_movie_details`
logic from `main.py`, moved into a class so that:

  * a single `httpx.AsyncClient` is reused across requests instead of
    opening a brand-new connection (and doing a new TLS handshake) on
    every call, and
  * TMDB-specific error handling lives in one place.

The request/response shape and the error-mapping behavior (network errors
-> 502, non-200 TMDB responses -> 502) are unchanged from the original.
"""

from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.response import TMDBMovieCard, TMDBMovieDetails

logger = get_logger(__name__)


class TMDBService:
    """Thin, reusable async client around the TMDB v3 API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.TMDB_BASE_URL
        self._api_key = settings.TMDB_API_KEY
        self._img_base = settings.TMDB_IMAGE_BASE_URL
        # One client, reused for the lifetime of the app (see app.main lifespan).
        self._client = httpx.AsyncClient(timeout=settings.TMDB_TIMEOUT_SECONDS)

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool on shutdown."""
        await self._client.aclose()

    def make_img_url(self, path: Optional[str]) -> Optional[str]:
        """Build a full TMDB poster/backdrop URL from a relative path."""
        if not path:
            return None
        return f"{self._img_base}{path}"

    async def get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safe TMDB GET.

        Network errors -> 502
        TMDB API errors (non-200) -> 502 with details in the response
        """
        query = dict(params)
        query["api_key"] = self._api_key

        try:
            response = await self._client.get(f"{self._base_url}{path}", params=query)
        except httpx.RequestError as exc:
            logger.error("TMDB request error on %s: %r", path, exc)
            raise HTTPException(
                status_code=502,
                detail=f"TMDB request error: {type(exc).__name__} | {repr(exc)}",
            )

        if response.status_code != 200:
            logger.error(
                "TMDB non-200 response on %s: %s | %s",
                path,
                response.status_code,
                response.text,
            )
            raise HTTPException(
                status_code=502,
                detail=f"TMDB request error: {response.status_code}: {response.text}",
            )
        return response.json()

    async def cards_from_results(
        self, results: List[dict], limit: int = 20
    ) -> List[TMDBMovieCard]:
        """Convert a raw TMDB `results` list into TMDBMovieCard objects."""
        cards: List[TMDBMovieCard] = []
        for movie in (results or [])[:limit]:
            cards.append(
                TMDBMovieCard(
                    tmdb_id=int(movie.get("id")),
                    title=movie.get("title") or movie.get("name") or "",
                    poster_url=self.make_img_url(movie.get("poster_path")),
                    release_date=movie.get("release_date"),
                    vote_average=movie.get("vote_average"),
                )
            )
        return cards

    async def movie_details(self, movie_id: int) -> TMDBMovieDetails:
        """Fetch full details for a single TMDB movie id."""
        data = await self.get(f"/movie/{movie_id}", {"language": "en-US"})
        return TMDBMovieDetails(
            tmdb_id=int(data["id"]),
            title=data.get("title") or "",
            overview=data.get("overview") or "",
            release_date=data.get("release_date"),
            poster_url=self.make_img_url(data.get("poster_path")),
            backdrop_url=self.make_img_url(data.get("backdrop_path")),
            genres=data.get("genres", []) or [],
        )

    async def search_movies(self, query: str, page: int = 1) -> Dict[str, Any]:
        """Raw TMDB keyword search (returns the full TMDB response shape)."""
        return await self.get(
            "/search/movie",
            {
                "query": query,
                "include_adult": "True",
                "language": "en-US",
                "page": page,
            },
        )

    async def search_first(self, query: str) -> Optional[dict]:
        """Return the single best TMDB match for a free-text query, if any."""
        data = await self.search_movies(query=query, page=1)
        results = data.get("results", [])
        return results[0] if results else None

    async def discover_by_genre(self, genre_id: int, page: int = 1) -> Dict[str, Any]:
        """TMDB discover, sorted by popularity, filtered to a single genre."""
        return await self.get(
            "/discover/movie",
            {
                "with_genres": genre_id,
                "language": "en-US",
                "sort_by": "popularity.desc",
                "page": page,
            },
        )

    async def attach_card_by_title(self, title: str) -> Optional[TMDBMovieCard]:
        """
        Look up a poster/card for a local dataset title via TMDB search.
        Never raises - returns None on any failure so callers can degrade
        gracefully instead of failing the whole recommendation response.
        """
        try:
            match = await self.search_first(title)
            if not match:
                return None
            return TMDBMovieCard(
                tmdb_id=int(match["id"]),
                title=match.get("title") or title,
                poster_url=self.make_img_url(match.get("poster_path")),
                release_date=match.get("release_date"),
                vote_average=match.get("vote_average"),
            )
        except Exception as exc:  # noqa: BLE001 - intentional broad guard, see docstring
            logger.warning("TMDB poster lookup failed for '%s': %s", title, exc)
            return None

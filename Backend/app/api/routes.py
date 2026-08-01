"""
API routes.

Every endpoint here is a direct, behavior-preserving port of the routes
that already existed in the original `main.py` (which is what the
deployed Streamlit `app.py` frontend calls today). Nothing about the
request/response contract has changed - only where the logic lives
(service layer) and how dependencies are obtained (DI via `Depends`).

Endpoints:
    GET  /                    - basic API info
    GET  /health              - liveness/readiness check
    GET  /home                - TMDB home feed (trending/popular/etc.)
    GET  /tmdb/search         - raw TMDB keyword search
    GET  /movie/id/{tmdb_id}  - full movie details
    GET  /recommend/genre     - TMDB genre-based recommendations
    GET  /recommend/tfidf     - local TF-IDF recommendations (debug/utility)
    GET  /movie/search        - bundle: details + TF-IDF recs + genre recs
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_recommendation_service, get_tmdb_service
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.response import (
    HealthResponse,
    RootResponse,
    SearchBundleResponse,
    TFIDFOnlyItem,
    TFIDFRecItem,
    TMDBMovieCard,
    TMDBMovieDetails,
)
from app.services.recommendation_service import RecommendationService
from app.services.tmdb_service import TMDBService

logger = get_logger(__name__)

router = APIRouter()

_ALLOWED_HOME_CATEGORIES = {"popular", "top_rated", "upcoming", "now_playing"}


@router.get("/", response_model=RootResponse, tags=["meta"])
def root(settings: Settings = Depends(get_settings)) -> RootResponse:
    """Basic API identification endpoint."""
    return RootResponse(message=settings.APP_NAME, version=settings.API_VERSION)


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
) -> HealthResponse:
    """
    Liveness/readiness check.

    Reports "healthy" only once the recommendation dataset has finished
    loading, so an orchestrator (e.g. Render) won't route traffic to an
    instance that isn't ready yet.
    """
    if not recommendation_service.is_ready:
        raise HTTPException(status_code=503, detail="Recommendation dataset not ready")
    return HealthResponse(status="healthy")


@router.get("/home", response_model=List[TMDBMovieCard], tags=["discovery"])
async def home(
    category: str = Query("popular"),
    limit: int = Query(24, ge=1, le=50),
    tmdb: TMDBService = Depends(get_tmdb_service),
) -> List[TMDBMovieCard]:
    """
    Home feed for the frontend (posters).

    category:
      - trending    -> trending/movie/day
      - popular, top_rated, upcoming, now_playing -> movie/{category}
    """
    try:
        if category == "trending":
            data = await tmdb.get("/trending/movie/day", {"language": "en-US"})
            return await tmdb.cards_from_results(data.get("results", []), limit=limit)

        if category not in _ALLOWED_HOME_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")

        data = await tmdb.get(f"/movie/{category}", {"language": "en-US", "page": 1})
        return await tmdb.cards_from_results(data.get("results", []), limit=limit)

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Home route failed")
        raise HTTPException(status_code=500, detail=f"Home route failed: {exc}")


@router.get("/tmdb/search", tags=["discovery"])
async def tmdb_search(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1, le=10),
    tmdb: TMDBService = Depends(get_tmdb_service),
):
    """
    Returns the raw TMDB response shape with a 'results' list.
    Used by the frontend for dropdown suggestions and grid results.
    """
    return await tmdb.search_movies(query=query, page=page)


@router.get("/movie/id/{tmdb_id}", response_model=TMDBMovieDetails, tags=["discovery"])
async def movie_details_route(
    tmdb_id: int,
    tmdb: TMDBService = Depends(get_tmdb_service),
) -> TMDBMovieDetails:
    """Full details for a single TMDB movie id."""
    return await tmdb.movie_details(tmdb_id)


@router.get("/recommend/genre", response_model=List[TMDBMovieCard], tags=["recommendations"])
async def recommend_genre(
    tmdb_id: int = Query(...),
    limit: int = Query(18, ge=1, le=50),
    tmdb: TMDBService = Depends(get_tmdb_service),
) -> List[TMDBMovieCard]:
    """
    Given a TMDB movie id: fetch its details, take the first genre, and
    discover other popular movies in that same genre.
    """
    details = await tmdb.movie_details(tmdb_id)
    if not details.genres:
        return []

    genre_id = details.genres[0]["id"]
    discover = await tmdb.discover_by_genre(genre_id)
    cards = await tmdb.cards_from_results(discover.get("results", []), limit=limit)
    return [card for card in cards if card.tmdb_id != tmdb_id]


@router.get("/recommend/tfidf", response_model=List[TFIDFOnlyItem], tags=["recommendations"])
async def recommend_tfidf(
    title: str = Query(..., min_length=1),
    top_n: int = Query(10, ge=1, le=50),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
) -> List[TFIDFOnlyItem]:
    """Debug/utility endpoint: local TF-IDF recommendations, no TMDB posters."""
    logger.info("TF-IDF recommendation requested for title='%s'", title)
    recs = recommendation_service.recommend_titles(title, top_n=top_n)
    return [TFIDFOnlyItem(title=t, score=s) for t, s in recs]


@router.get("/movie/search", response_model=SearchBundleResponse, tags=["recommendations"])
async def search_bundle(
    query: str = Query(..., min_length=1),
    tfidf_top_n: int = Query(12, ge=1, le=30),
    genre_limit: int = Query(12, ge=1, le=30),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    tmdb: TMDBService = Depends(get_tmdb_service),
) -> SearchBundleResponse:
    """
    Bundle endpoint used by the movie detail page:
      - resolves the best TMDB match for `query`
      - fetches full movie details
      - computes local TF-IDF recommendations (never crashes the endpoint)
      - fetches TMDB genre-based recommendations

    NOTE: this selects the single BEST TMDB match for the query. For
    multiple candidate matches, the frontend should use /tmdb/search.
    """
    best = await tmdb.search_first(query)
    if not best:
        raise HTTPException(status_code=404, detail=f"No TMDB movie found for query: {query}")

    tmdb_id = int(best["id"])
    details = await tmdb.movie_details(tmdb_id)

    # 1) TF-IDF recommendations (never crash the endpoint on a miss)
    tfidf_items: List[TFIDFRecItem] = []
    try:
        recs = recommendation_service.recommend_titles(details.title, top_n=tfidf_top_n)
    except Exception:
        try:
            recs = recommendation_service.recommend_titles(query, top_n=tfidf_top_n)
        except Exception:
            recs = []

    for title, score in recs:
        card = await tmdb.attach_card_by_title(title)
        tfidf_items.append(TFIDFRecItem(title=title, score=score, tmdb=card))

    # 2) Genre recommendations (TMDB discover by the first genre)
    genre_recs: List[TMDBMovieCard] = []
    if details.genres:
        genre_id = details.genres[0]["id"]
        discover = await tmdb.discover_by_genre(genre_id)
        cards = await tmdb.cards_from_results(discover.get("results", []), limit=genre_limit)
        genre_recs = [card for card in cards if card.tmdb_id != details.tmdb_id]

    return SearchBundleResponse(
        query=query,
        movie_details=details,
        tfidf_recommendations=tfidf_items,
        genre_recommendations=genre_recs,
    )

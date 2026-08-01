"""
Dependency injection wiring.

FastAPI's `Depends()` mechanism is used to hand routes a reference to the
already-loaded, singleton service instances stored on `app.state`
(created once at startup - see `app/main.py`) instead of importing global
module-level variables directly. This keeps routes testable: tests can
override these dependencies with fakes via `app.dependency_overrides`.
"""

from fastapi import Request

from app.core.config import Settings, get_settings
from app.services.recommendation_service import RecommendationService
from app.services.tmdb_service import TMDBService


def get_app_settings() -> Settings:
    """Provide the cached application settings."""
    return get_settings()


def get_recommendation_service(request: Request) -> RecommendationService:
    """Provide the singleton RecommendationService created at startup."""
    return request.app.state.recommendation_service


def get_tmdb_service(request: Request) -> TMDBService:
    """Provide the singleton TMDBService created at startup."""
    return request.app.state.tmdb_service

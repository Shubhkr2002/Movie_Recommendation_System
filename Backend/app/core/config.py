"""
Application configuration.

Centralizes every environment-driven setting behind a single, typed
`Settings` object so the rest of the codebase never calls `os.getenv`
directly. Values are read once at import time and cached via
`get_settings()` (see the `lru_cache` below), which keeps configuration
consistent for the lifetime of the process and makes it trivial to
override during tests (just clear the cache and re-instantiate).
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from environment variables / .env."""

    # ---- App metadata -----------------------------------------------
    APP_NAME: str = "Movie Recommendation API"
    API_VERSION: str = "1.0"
    DEBUG: bool = False

    # ---- TMDB ---------------------------------------------------------
    TMDB_API_KEY: str = Field(..., description="TMDB API key, required at startup")
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE_URL: str = "https://image.tmdb.org/t/p/w500"
    TMDB_TIMEOUT_SECONDS: float = 20.0

    # ---- CORS / security -----------------------------------------------
    ALLOWED_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # ---- Data paths -----------------------------------------------------
    DATA_DIR: str = "data"
    DF_FILENAME: str = "df.pkl"
    INDICES_FILENAME: str = "indices.pkl"
    TFIDF_MATRIX_FILENAME: str = "tfidf_matrix.pkl"
    TFIDF_VECTORIZER_FILENAME: str = "tfidf.pkl"

    # ---- Logging --------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance.

    Using lru_cache means the .env file / environment is parsed once,
    and every part of the app that calls get_settings() shares the same
    object instead of re-reading and re-validating the environment.
    """
    return Settings()

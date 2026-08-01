"""
Application entrypoint.

Builds the FastAPI app: configures logging, loads settings, creates the
long-lived service singletons (loading pickles exactly once), registers
middleware, routes, and global exception handlers.

Run locally with:
    uvicorn app.main:app --reload

Deployed with (see Dockerfile / render.yaml):
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.services.recommendation_service import RecommendationService
from app.services.tmdb_service import TMDBService
from app.utils.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan.

    Startup: load the recommendation dataset once and create a reusable
    TMDB HTTP client, both stored on `app.state` so route dependencies
    (see app/api/dependencies.py) can fetch them without re-loading
    anything per-request.

    Shutdown: close the TMDB HTTP client cleanly.
    """
    logger.info("Starting %s v%s", settings.APP_NAME, settings.API_VERSION)

    recommendation_service = RecommendationService(settings)
    recommendation_service.load()
    app.state.recommendation_service = recommendation_service

    tmdb_service = TMDBService(settings)
    app.state.tmdb_service = tmdb_service

    logger.info("Startup complete - service is ready to accept traffic")
    yield

    logger.info("Shutting down %s", settings.APP_NAME)
    await tmdb_service.aclose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory - builds and returns a fully configured FastAPI app."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.API_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # ---- Middleware (order matters: added last = runs first on the way in) ----
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Routes ----
    app.include_router(api_router)

    # ---- Global exception handlers ----
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    return app


app = create_app()

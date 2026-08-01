"""
Global exception handlers.

Registered on the FastAPI app in `app/main.py`. Ensures every error -
expected (HTTPException) or not - comes back as a consistent JSON shape:

    {"error": "<short code>", "detail": "<message>"}

instead of leaking stack traces or Starlette's default HTML error pages.
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("app.errors")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle explicit HTTPException / 404s with a consistent JSON body."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": _error_code_for(exc.status_code), "detail": exc.detail},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic/FastAPI request validation failures (422)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "detail": "Request validation failed",
            "errors": exc.errors(),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for anything not already handled - always returns a 500."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error", "detail": "An unexpected error occurred"},
    )


def _error_code_for(status_code: int) -> str:
    return {
        404: "not_found",
        422: "validation_error",
        400: "bad_request",
        502: "upstream_error",
        503: "service_unavailable",
    }.get(status_code, "http_error")

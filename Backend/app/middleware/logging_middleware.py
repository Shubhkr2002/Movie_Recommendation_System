"""
Request logging middleware.

Logs every incoming request (method, path, status code, and duration) at
INFO level, and logs unhandled exceptions at ERROR level before
re-raising them so FastAPI's exception handlers can still produce the
JSON error response.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and duration for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "Unhandled error | %s %s | %.2fms",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "%s %s | status=%d | %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

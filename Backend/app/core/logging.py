"""
Logging configuration.

Sets up a single, consistent logging format for the whole application.
Call `configure_logging()` once, at startup, before anything else logs.
"""

import logging
import sys

from app.core.config import get_settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """Configure the root logger with a stream handler and formatted output.

    Idempotent: safe to call more than once (e.g. under a test suite that
    imports the app multiple times) without duplicating log lines.
    """
    settings = get_settings()
    root_logger = logging.getLogger()

    if root_logger.handlers:
        # Already configured (e.g. reload, repeated import) - avoid duplicate handlers.
        root_logger.setLevel(settings.LOG_LEVEL)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers a little, but keep our own app.* verbose.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper so callers don't need to import `logging` directly."""
    return logging.getLogger(name)

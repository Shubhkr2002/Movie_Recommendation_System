"""
Shared pytest fixtures.

The `client` fixture spins up the real FastAPI app (including its
lifespan, which loads the actual pickles from `data/`) once per test
session via TestClient's context manager, so tests exercise the same
startup path used in production.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client

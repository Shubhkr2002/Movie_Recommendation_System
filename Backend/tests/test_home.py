"""
Tests for TMDB-backed endpoints (/home, /movie/id/{id}).

These override the `get_tmdb_service` dependency with a fake that returns
canned data, so tests are fast, deterministic, and don't require a real
TMDB_API_KEY or network access.
"""

from app.api.dependencies import get_tmdb_service
from app.main import app
from app.schemas.response import TMDBMovieCard, TMDBMovieDetails


class FakeTMDBService:
    async def get(self, path, params):
        return {"results": [{"id": 1, "title": "Fake Movie", "poster_path": "/x.jpg"}]}

    async def cards_from_results(self, results, limit=20):
        return [
            TMDBMovieCard(tmdb_id=1, title="Fake Movie", poster_url="https://img/x.jpg")
            for _ in results[:limit]
        ]

    async def movie_details(self, movie_id):
        return TMDBMovieDetails(
            tmdb_id=movie_id,
            title="Fake Movie",
            overview="A fake movie for testing.",
            genres=[{"id": 1, "name": "Fake Genre"}],
        )


def _override_tmdb():
    app.dependency_overrides[get_tmdb_service] = lambda: FakeTMDBService()


def _clear_overrides():
    app.dependency_overrides.pop(get_tmdb_service, None)


def test_home_feed_returns_cards(client):
    _override_tmdb()
    try:
        response = client.get("/home", params={"category": "popular", "limit": 5})
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert body[0]["title"] == "Fake Movie"
    finally:
        _clear_overrides()


def test_home_feed_rejects_invalid_category(client):
    _override_tmdb()
    try:
        response = client.get("/home", params={"category": "not-a-real-category"})
        assert response.status_code == 400
    finally:
        _clear_overrides()


def test_movie_details_route(client):
    _override_tmdb()
    try:
        response = client.get("/movie/id/1")
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Fake Movie"
    finally:
        _clear_overrides()

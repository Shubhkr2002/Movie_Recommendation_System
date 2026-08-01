"""
Tests for GET /recommend/tfidf.

This endpoint only touches the local RecommendationService (no TMDB
network calls), so it is the fastest, most deterministic endpoint to
test the actual recommendation algorithm against.
"""


def test_tfidf_recommend_known_title_returns_results(client):
    response = client.get("/recommend/tfidf", params={"title": "Toy Story", "top_n": 5})
    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 5
    for item in body:
        assert "title" in item
        assert "score" in item
        assert item["title"] != "Toy Story"


def test_tfidf_recommend_unknown_title_returns_404(client):
    response = client.get(
        "/recommend/tfidf", params={"title": "Definitely Not A Real Movie Title 123"}
    )
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_tfidf_recommend_rejects_blank_title(client):
    response = client.get("/recommend/tfidf", params={"title": ""})
    assert response.status_code == 422

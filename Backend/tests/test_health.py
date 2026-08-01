"""Tests for GET / and GET /health."""


def test_root_returns_app_info(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert "version" in body


def test_health_returns_healthy_once_dataset_loaded(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

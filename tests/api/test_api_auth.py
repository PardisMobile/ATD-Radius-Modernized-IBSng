from fastapi.testclient import TestClient

from atd_radius.api.app import app
from atd_radius.config import settings


def test_api_requires_bearer_token_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "api_bearer_token", "test-secret")
    client = TestClient(app)

    assert client.get("/api/v1/meta").status_code == 401
    assert client.get(
        "/api/v1/meta", headers={"Authorization": "Bearer wrong-secret"}
    ).status_code == 401
    response = client.get(
        "/api/v1/meta", headers={"Authorization": "Bearer test-secret"}
    )
    assert response.status_code == 200


def test_non_development_api_fails_closed_without_token(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "api_bearer_token", "")
    client = TestClient(app)

    response = client.get("/api/v1/meta")
    assert response.status_code == 503
    assert response.json()["detail"] == "API authentication is not configured"
    assert client.get("/health").status_code == 200


def test_development_api_remains_usable_without_token(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "api_bearer_token", "")
    response = TestClient(app).get("/api/v1/meta")
    assert response.status_code == 200

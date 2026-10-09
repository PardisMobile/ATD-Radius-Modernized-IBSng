import asyncio

import httpx

from atd_radius.api.app import app
from atd_radius.config import settings


def request_get(path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path, headers=headers)

    return asyncio.run(run_request())


def request_post(path: str, headers: dict[str, str] | None = None, json: dict | None = None) -> httpx.Response:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(path, headers=headers, json=json)

    return asyncio.run(run_request())


def test_api_requires_bearer_token_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "api_bearer_token", "test-secret")

    assert request_get("/api/v1/meta").status_code == 401
    assert request_get(
        "/api/v1/meta", {"Authorization": "Bearer wrong-secret"}
    ).status_code == 401
    response = request_get(
        "/api/v1/meta", {"Authorization": "Bearer test-secret"}
    )
    assert response.status_code == 200


def test_non_development_api_fails_closed_without_token(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "api_bearer_token", "")

    response = request_get("/api/v1/meta")
    assert response.status_code == 503
    assert response.json()["detail"] == "API authentication is not configured"
    assert request_get("/health").status_code == 200


def test_development_api_remains_usable_without_token(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "api_bearer_token", "")
    assert request_get("/api/v1/meta").status_code == 200



def test_admin_login_endpoint_remains_behind_api_perimeter_token(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "api_bearer_token", "perimeter-secret")
    response = request_post(
        "/api/v1/admin/login",
        json={"username": "operator", "password": "password"},
    )
    assert response.status_code == 401


def test_admin_session_endpoint_requires_its_own_session_token(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "api_bearer_token", "")
    response = request_get("/api/v1/admin/session")
    assert response.status_code == 401
    assert response.json()["detail"] == "Administrator session required"

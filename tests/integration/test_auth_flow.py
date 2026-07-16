from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "TestPassword123!"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["admin"]["email"] == "admin@example.com"
    assert "csrf_token" in body
    assert "trading_bot_session" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "WrongPassword"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "unknown@example.com", "password": "whatever123"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_authentication(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_admin_after_login(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_logout_revokes_session(authenticated_client: AsyncClient):
    logout_response = await authenticated_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    me_response = await authenticated_client.get("/api/v1/auth/me")
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_access_to_protected_endpoints(client: AsyncClient):
    for path in ["/api/v1/dashboard", "/api/v1/settings", "/api/v1/positions", "/api/v1/bot/status"]:
        response = await client.get(path)
        assert response.status_code == 401, f"{path} kimlik dogrulamasi gerektirmeli"


@pytest.mark.asyncio
async def test_mutating_request_requires_csrf_token(client: AsyncClient):
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "TestPassword123!"}
    )
    assert login_response.status_code == 200
    # CSRF header eklenmeden PUT/POST istegi reddedilmeli
    response = await client.put("/api/v1/settings", json={"leverage": 3})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_rate_limited_after_many_attempts(client: AsyncClient):
    for _ in range(9):
        await client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    response = await client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_binance_secret_never_returned_in_settings(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/settings")
    assert response.status_code == 200
    body_text = response.text
    assert "BINANCE_API_SECRET" not in body_text
    assert "api_secret" not in body_text.lower()


@pytest.mark.asyncio
async def test_binance_status_never_exposes_secret(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/binance/status")
    assert response.status_code == 200
    body_text = response.text.lower()
    assert "secret" not in body_text
    assert "api_key" not in body_text

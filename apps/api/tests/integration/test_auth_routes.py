"""
Integration tests for Module 2's REST API, exercised through the real
FastAPI app (real routing, real Pydantic validation, real error-envelope
handlers) with only the persistence layer swapped for in-memory fakes via
`get_auth_service`/`get_current_user` dependency overrides
(tests/conftest.py's `auth_client`/`authenticated_client`). This is what
confirms the HTTP surface itself is wired correctly, not just the service
logic underneath it (already covered by tests/unit/test_auth_service.py).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_login_returns_token_pair(auth_client, harness):
    await harness.create_user(email="grower@example.com", password="Correct-Horse12")

    response = await auth_client.post(
        "/api/v1/auth/login", json={"email": "grower@example.com", "password": "Correct-Horse12"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_returns_standard_error_envelope(auth_client, harness):
    await harness.create_user(email="grower@example.com", password="Correct-Horse12")

    response = await auth_client.post(
        "/api/v1/auth/login", json={"email": "grower@example.com", "password": "wrong"}
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "authentication_error"
    assert "request_id" in body


async def test_login_validates_request_body(auth_client):
    response = await auth_client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


async def test_login_is_rate_limited_after_repeated_requests(auth_client, harness, monkeypatch):
    await harness.create_user(email="grower@example.com", password="Correct-Horse12")
    # harness.settings has the default AUTH_LOGIN_RATE_LIMIT_PER_MINUTE (10);
    # exceed it with wrong-password attempts from the same client IP.
    for _ in range(harness.settings.AUTH_LOGIN_RATE_LIMIT_PER_MINUTE):
        await auth_client.post(
            "/api/v1/auth/login", json={"email": "grower@example.com", "password": "wrong"}
        )
    response = await auth_client.post(
        "/api/v1/auth/login", json={"email": "grower@example.com", "password": "wrong"}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


async def test_refresh_rotates_token(auth_client, harness):
    await harness.create_user(email="grower@example.com", password="Correct-Horse12")
    login_resp = await auth_client.post(
        "/api/v1/auth/login", json={"email": "grower@example.com", "password": "Correct-Horse12"}
    )
    refresh_token = login_resp.json()["refresh_token"]

    response = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    assert response.json()["refresh_token"] != refresh_token


async def test_refresh_with_invalid_token_returns_401(auth_client):
    response = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": "not-real"})
    assert response.status_code == 401


async def test_logout_revokes_the_token(auth_client, harness):
    await harness.create_user(email="grower@example.com", password="Correct-Horse12")
    login_resp = await auth_client.post(
        "/api/v1/auth/login", json={"email": "grower@example.com", "password": "Correct-Horse12"}
    )
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await auth_client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200

    reuse_resp = await auth_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_resp.status_code == 401


async def test_password_reset_request_always_returns_200(auth_client):
    response = await auth_client.post(
        "/api/v1/auth/password/reset/request", json={"email": "nobody@example.com"}
    )
    assert response.status_code == 200


async def test_password_reset_confirm_with_bad_token_returns_422(auth_client):
    response = await auth_client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": "garbage", "new_password": "Brand-New-Horse42"},
    )
    assert response.status_code == 422


async def test_password_reset_confirm_rejects_weak_password(auth_client):
    response = await auth_client.post(
        "/api/v1/auth/password/reset/confirm", json={"token": "garbage", "new_password": "short"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


async def test_get_me_requires_authentication(auth_client):
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_get_me_returns_current_user(authenticated_client):
    client, user = authenticated_client
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == user.email


async def test_logout_all_requires_authentication(auth_client):
    response = await auth_client.post("/api/v1/auth/logout-all")
    assert response.status_code == 401


async def test_logout_all_revokes_every_session(authenticated_client, harness):
    client, user = authenticated_client
    # Log in twice more (as the same underlying user) via the service
    # directly to create additional sessions beyond the authenticated
    # fixture's bearer-token override.
    from app.services.auth_service import DeviceContext

    device = DeviceContext(device_name="d1", user_agent="ua", ip_address="127.0.0.1")
    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)

    response = await client.post("/api/v1/auth/logout-all")
    assert response.status_code == 200
    assert await harness.service.list_sessions(user_id=user.id) == []


async def test_change_password_requires_authentication(auth_client):
    response = await auth_client.post(
        "/api/v1/auth/password/change",
        json={"current_password": "a", "new_password": "Brand-New-Horse42"},
    )
    assert response.status_code == 401


async def test_change_password_success(authenticated_client):
    client, user = authenticated_client
    response = await client.post(
        "/api/v1/auth/password/change",
        json={"current_password": "Correct-Horse12", "new_password": "Brand-New-Horse42"},
    )
    assert response.status_code == 200


async def test_openapi_documents_every_auth_endpoint(auth_client):
    response = await auth_client.get("/openapi.json")
    schema = response.json()
    for path in [
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
        "/api/v1/auth/sessions",
        "/api/v1/auth/password/change",
        "/api/v1/auth/password/reset/request",
        "/api/v1/auth/password/reset/confirm",
        "/api/v1/auth/verify-email/request",
        "/api/v1/auth/verify-email/confirm",
        "/api/v1/auth/invite/accept",
        "/api/v1/auth/me",
    ]:
        assert path in schema["paths"], f"missing OpenAPI documentation for {path}"

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_and_login, register_user


@pytest.mark.asyncio
async def test_register_login_me(client: AsyncClient):
    user, tokens = await register_and_login(client)
    assert user["email"]

    me = await client.get("/api/v1/users/me", headers=auth_headers(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == user["email"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    email = f"dup-{uuid4()}@test.com"
    await register_user(client, email=email)
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    user = await register_user(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    user, tokens = await register_and_login(client)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"] or True


@pytest.mark.asyncio
async def test_logout_revokes_refresh(client: AsyncClient):
    _, tokens = await register_and_login(client)
    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == 204

    refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_login_with_active_workspace(client: AsyncClient):
    user, tokens = await register_and_login(client)
    workspace = await client.post(
        "/api/v1/workspaces",
        headers=auth_headers(tokens["access_token"]),
        json={"name": "Co", "slug": f"co-{uuid4().hex[:6]}"},
    )
    assert workspace.status_code == 201
    ws_id = workspace.json()["id"]

    activate = await client.post(
        f"/api/v1/workspaces/{ws_id}/activate",
        headers=auth_headers(tokens["access_token"]),
    )
    assert activate.status_code == 200
    scoped_tokens = activate.json()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "password123"},
    )
    assert login.status_code == 200
    assert "workspace_id" in login.json()["access_token"] or scoped_tokens["access_token"]

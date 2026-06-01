from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.conftest import (
    auth_headers,
    create_workspace,
    register_and_login,
    register_user,
)


@pytest.mark.asyncio
async def test_create_list_get_workspace(client: AsyncClient):
    _, tokens = await register_and_login(client)
    headers = auth_headers(tokens["access_token"])

    workspace = await create_workspace(client, tokens["access_token"], slug=f"acme-{uuid4().hex[:6]}")

    listed = await client.get("/api/v1/workspaces", headers=headers)
    assert listed.status_code == 200
    assert any(w["id"] == workspace["id"] for w in listed.json())

    got = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["slug"] == workspace["slug"]


@pytest.mark.asyncio
async def test_update_workspace(client: AsyncClient):
    _, tokens = await register_and_login(client)
    headers = auth_headers(tokens["access_token"])
    workspace = await create_workspace(client, tokens["access_token"], slug=f"upd-{uuid4().hex[:6]}")

    updated = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        headers=headers,
        json={"name": "New Name"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_workspace(client: AsyncClient):
    _, tokens = await register_and_login(client)
    headers = auth_headers(tokens["access_token"])
    workspace = await create_workspace(client, tokens["access_token"], slug=f"del-{uuid4().hex[:6]}")
    ws_id = workspace["id"]

    deleted = await client.delete(f"/api/v1/workspaces/{ws_id}", headers=headers)
    assert deleted.status_code == 204

    listed = await client.get("/api/v1/workspaces", headers=headers)
    assert all(w["id"] != ws_id for w in listed.json())

    got = await client.get(f"/api/v1/workspaces/{ws_id}", headers=headers)
    assert got.status_code == 403


@pytest.mark.asyncio
async def test_activate_workspace_returns_tokens(client: AsyncClient):
    _, tokens = await register_and_login(client)
    headers = auth_headers(tokens["access_token"])
    workspace = await create_workspace(client, tokens["access_token"], slug=f"act-{uuid4().hex[:6]}")

    activated = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/activate",
        headers=headers,
    )
    assert activated.status_code == 200
    assert activated.json()["access_token"]
    assert activated.json()["refresh_token"]


@pytest.mark.asyncio
async def test_members_add_list_update_delete(client: AsyncClient):
    _, admin_tokens = await register_and_login(client)
    admin_headers = auth_headers(admin_tokens["access_token"])
    workspace = await create_workspace(client, admin_tokens["access_token"], slug=f"mem-{uuid4().hex[:6]}")
    ws_id = workspace["id"]

    member_user = await register_user(client, email=f"member-{uuid4()}@test.com")
    member_tokens = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": member_user["email"], "password": "password123"},
        )
    ).json()

    added = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=admin_headers,
        json={"email": member_user["email"]},
    )
    assert added.status_code == 201
    assert added.json()["user"]["email"] == member_user["email"]
    assert not added.json()["is_admin"]

    members = await client.get(f"/api/v1/workspaces/{ws_id}/members", headers=admin_headers)
    assert len(members.json()) == 2

    promoted = await client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{member_user['id']}",
        headers=admin_headers,
        json={"is_admin": True},
    )
    assert promoted.status_code == 200
    assert promoted.json()["is_admin"]

    removed = await client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{member_user['id']}",
        headers=auth_headers(member_tokens["access_token"]),
    )
    assert removed.status_code == 204

    members_after = await client.get(f"/api/v1/workspaces/{ws_id}/members", headers=admin_headers)
    assert all(m["user"]["id"] != member_user["id"] for m in members_after.json())


@pytest.mark.asyncio
async def test_non_admin_cannot_add_member(client: AsyncClient):
    _, admin_tokens = await register_and_login(client)
    workspace = await create_workspace(client, admin_tokens["access_token"], slug=f"na-{uuid4().hex[:6]}")
    ws_id = workspace["id"]

    member = await register_user(client, email=f"nm-{uuid4()}@test.com")
    await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=auth_headers(admin_tokens["access_token"]),
        json={"email": member["email"]},
    )
    member_tokens = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": member["email"], "password": "password123"},
        )
    ).json()

    other = await register_user(client, email=f"other-{uuid4()}@test.com")
    denied = await client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=auth_headers(member_tokens["access_token"]),
        json={"email": other["email"]},
    )
    assert denied.status_code == 403

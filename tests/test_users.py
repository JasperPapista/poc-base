import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_and_login


@pytest.mark.asyncio
async def test_delete_me(client: AsyncClient):
    user, tokens = await register_and_login(client)
    headers = auth_headers(tokens["access_token"])

    deleted = await client.delete("/api/v1/users/me", headers=headers)
    assert deleted.status_code == 204

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "password123"},
    )
    assert login.status_code == 401

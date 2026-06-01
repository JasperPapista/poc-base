import os
from collections.abc import AsyncIterator
from uuid import uuid4

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

# Must be set before app modules load settings / engine
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from app.infrastructure.cache import redis as redis_module
from app.infrastructure.persistence.session import AsyncSessionLocal, engine
from app.main import app


@pytest.fixture
async def fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.aioredis.FakeRedis:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_module, "_client", client)

    async def get_redis() -> fakeredis.aioredis.FakeRedis:
        return client

    monkeypatch.setattr(redis_module, "get_redis", get_redis)
    return client


@pytest.fixture
async def db_session() -> AsyncIterator:
    """Async DB session against the in-memory SQLite test database (real ORM, not mocked)."""
    from app.infrastructure.persistence.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(fake_redis: fakeredis.aioredis.FakeRedis) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def register_user(
    client: AsyncClient,
    *,
    email: str | None = None,
    password: str = "password123",
    full_name: str = "Test User",
) -> dict:
    email = email or f"user-{uuid4()}@test.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login_user(
    client: AsyncClient,
    email: str,
    password: str = "password123",
) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def register_and_login(
    client: AsyncClient,
    *,
    email: str | None = None,
    password: str = "password123",
) -> tuple[dict, dict]:
    user = await register_user(client, email=email, password=password)
    tokens = await login_user(client, user["email"], password)
    return user, tokens


async def create_workspace(
    client: AsyncClient,
    access_token: str,
    *,
    name: str = "Acme",
    slug: str | None = None,
) -> dict:
    slug = slug or f"ws-{uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/workspaces",
        headers=auth_headers(access_token),
        json={"name": name, "slug": slug},
    )
    assert response.status_code == 201, response.text
    return response.json()

from redis.asyncio import Redis

from app.config import settings

_client: Redis | None = None


async def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def refresh_revocation_key(jti: str) -> str:
    return f"auth:revoked_refresh:{jti}"


async def revoke_refresh(jti: str, expires_in_seconds: int) -> None:
    redis = await get_redis()
    await redis.set(refresh_revocation_key(jti), "1", ex=max(expires_in_seconds, 1))


async def is_refresh_revoked(jti: str) -> bool:
    redis = await get_redis()
    return await redis.exists(refresh_revocation_key(jti)) == 1

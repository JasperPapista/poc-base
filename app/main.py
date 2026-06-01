from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import auth, users, workspaces
from app.config import settings
from app.infrastructure.cache.redis import close_redis
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}

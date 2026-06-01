import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from app.config import settings


def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["jti"] = str(uuid.uuid4())
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str, workspace_id: str | None = None) -> str:
    data: dict[str, Any] = {"sub": user_id, "type": "access"}
    if workspace_id:
        data["workspace_id"] = workspace_id
    return _create_token(data, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: str, workspace_id: str | None = None) -> str:
    data: dict[str, Any] = {"sub": user_id, "type": "refresh"}
    if workspace_id:
        data["workspace_id"] = workspace_id
    return _create_token(data, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def token_workspace_id(data: dict[str, Any]) -> str | None:
    return data.get("workspace_id")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

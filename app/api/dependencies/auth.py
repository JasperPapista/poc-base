from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models import User
from app.infrastructure.persistence.session import get_db
from app.infrastructure.security import decode_token, token_workspace_id

bearer_scheme = HTTPBearer(auto_error=False)


def _decode_access_credentials(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = decode_token(credentials.credentials)
        if data.get("type") != "access":
            raise ValueError
        return data
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")


async def get_authenticated_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    data = _decode_access_credentials(credentials)
    user_id = UUID(data["sub"])
    result = await db.execute(
        select(User)
        .options(selectinload(User.active_workspace))
        .where(
            User.id == user_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    data = _decode_access_credentials(credentials)
    try:
        user_id = UUID(data["sub"])
        token_workspace = token_workspace_id(data)
        if not token_workspace:
            raise ValueError
        workspace_id = UUID(token_workspace)
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    result = await db.execute(
        select(User)
        .options(selectinload(User.active_workspace))
        .where(
            User.id == user_id,
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    if user.active_workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token workspace does not match user's active workspace",
        )

    return user

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models import User, WorkspaceMember
from app.infrastructure.cache.redis import is_refresh_revoked, revoke_refresh
from app.application.dto import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.infrastructure.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_workspace_id,
    verify_password,
)


def _tokens_for_user(user: User) -> TokenResponse:
    workspace_id = str(user.active_workspace_id) if user.active_workspace_id else None
    return TokenResponse(
        access_token=create_access_token(str(user.id), workspace_id),
        refresh_token=create_refresh_token(str(user.id), workspace_id),
    )


async def _resolve_active_workspace(user: User, db: AsyncSession) -> str:
    if not user.active_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active workspace set for this user",
        )

    member_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.workspace_id == user.active_workspace_id,
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of the active workspace",
        )

    return str(user.active_workspace_id)


async def register(payload: RegisterRequest, db: AsyncSession) -> UserResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    await db.refresh(user)
    return UserResponse.model_validate(user)


async def login(payload: LoginRequest, db: AsyncSession) -> TokenResponse:
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.active_workspace))
        .where(
            User.email == payload.email,
            User.is_active.is_(True),
        )
    )
    user = user_result.scalar_one_or_none()
    if not user or not verify_password(payload.password, str(user.hashed_password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.active_workspace_id:
        await _resolve_active_workspace(user, db)

    return _tokens_for_user(user)


async def refresh(payload: RefreshRequest, db: AsyncSession) -> TokenResponse:
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError
        jti = data.get("jti")
        if not jti:
            raise ValueError
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if await is_refresh_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    user_id = UUID(data["sub"])
    token_workspace = token_workspace_id(data)

    user_result = await db.execute(
        select(User)
        .options(selectinload(User.active_workspace))
        .where(
            User.id == user_id,
            User.is_active.is_(True),
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    if token_workspace:
        workspace_id = UUID(token_workspace)
        if user.active_workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token workspace does not match user's active workspace",
            )
        member_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Membership revoked")

    return _tokens_for_user(user)


async def logout(payload: LogoutRequest) -> None:
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError
        jti = data.get("jti")
        if not jti:
            raise ValueError
        exp = data.get("exp")
        if not exp:
            raise ValueError
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if isinstance(exp, datetime):
        expires_at = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
        expires_in = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    else:
        expires_in = int(exp) - int(datetime.now(timezone.utc).timestamp())

    await revoke_refresh(jti, expires_in)

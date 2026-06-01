from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import service as auth_service
from app.application.dto import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.infrastructure.persistence.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register with email and password (no workspace)."""
    return await auth_service.register(payload, db)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Login with email and password. Tokens include workspace scope when an active workspace is set."""
    return await auth_service.login(payload, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Exchange a refresh token for a new token pair."""
    return await auth_service.refresh(payload, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest):
    """Revoke the refresh token. Access tokens remain valid until they expire."""
    await auth_service.logout(payload)

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_authenticated_user
from app.infrastructure.persistence.models import User
from app.application.dto import (
    AddMemberRequest,
    MemberResponse,
    TokenResponse,
    UpdateMemberRequest,
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from app.application.workspaces import service as workspace_service
from app.infrastructure.persistence.session import get_db

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Create a workspace; the creator becomes a workspace admin."""
    return await workspace_service.create_workspace(payload, current_user, db)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """List workspaces the current user belongs to."""
    return await workspace_service.list_workspaces(current_user, db)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    return await workspace_service.get_workspace(workspace_id, current_user, db)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    return await workspace_service.update_workspace(workspace_id, payload, current_user, db)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Permanently delete a workspace."""
    await workspace_service.delete_workspace(workspace_id, current_user, db)


@router.post("/{workspace_id}/activate", response_model=TokenResponse)
async def activate_workspace(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Set this workspace as active and return scoped tokens."""
    return await workspace_service.activate_workspace(workspace_id, current_user, db)


@router.get("/{workspace_id}/members", response_model=list[MemberResponse])
async def list_members(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    return await workspace_service.list_members(workspace_id, current_user, db)


@router.post("/{workspace_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    workspace_id: UUID,
    payload: AddMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Add an existing user to the workspace by email."""
    return await workspace_service.add_member(workspace_id, payload, current_user, db)


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    workspace_id: UUID,
    user_id: UUID,
    payload: UpdateMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Grant or revoke workspace admin (admins only)."""
    return await workspace_service.update_member(workspace_id, user_id, payload, current_user, db)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    workspace_id: UUID,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Remove a user from the workspace."""
    await workspace_service.delete_member(workspace_id, user_id, current_user, db)

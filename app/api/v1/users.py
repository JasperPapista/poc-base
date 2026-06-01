from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_authenticated_user
from app.application.dto import ActiveWorkspaceRequest, TokenResponse, UserResponse
from app.application.users import service as user_service
from app.application.workspaces import service as workspace_service
from app.infrastructure.persistence.models import User
from app.infrastructure.persistence.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def me(current_user: Annotated[User, Depends(get_authenticated_user)]):
    """Return the authenticated user and their active workspace."""
    return await user_service.get_me(current_user)


@router.put("/me/active-workspace", response_model=TokenResponse)
async def set_active_workspace(
    payload: ActiveWorkspaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Set the active workspace and return scoped tokens."""
    return await workspace_service.activate_workspace(payload.workspace_id, current_user, db)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_authenticated_user)],
):
    """Permanently delete the current user account."""
    await user_service.delete_me(current_user, db)

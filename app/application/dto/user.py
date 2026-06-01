from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.application.dto.workspace import WorkspaceResponse


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    active_workspace: WorkspaceResponse | None
    created_at: datetime


class ActiveWorkspaceRequest(BaseModel):
    workspace_id: UUID = Field(description="Workspace to set as active for the current user")

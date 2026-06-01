from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class WorkspaceCreateRequest(BaseModel):
    name: str
    slug: str

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = None
    slug: str | None = None

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v


class WorkspaceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    slug: str
    created_at: datetime


class MemberUserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    email: EmailStr
    full_name: str | None


class MemberResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    joined_at: datetime
    is_admin: bool
    user: MemberUserResponse


class AddMemberRequest(BaseModel):
    email: EmailStr


class UpdateMemberRequest(BaseModel):
    is_admin: bool

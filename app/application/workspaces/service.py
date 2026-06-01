from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.persistence.models import User, Workspace, WorkspaceMember
from app.application.dto import (
    AddMemberRequest,
    MemberResponse,
    TokenResponse,
    UpdateMemberRequest,
    WorkspaceCreateRequest,
    WorkspaceResponse,
    WorkspaceUpdateRequest,
)
from app.infrastructure.security import create_access_token, create_refresh_token


async def _get_membership(db: AsyncSession, user_id: UUID, workspace_id: UUID) -> WorkspaceMember:
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user), selectinload(WorkspaceMember.workspace))
        .where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace")
    return member


async def _require_membership(db: AsyncSession, user_id: UUID, workspace_id: UUID) -> WorkspaceMember:
    return await _get_membership(db, user_id, workspace_id)


async def _require_admin(db: AsyncSession, user_id: UUID, workspace_id: UUID) -> WorkspaceMember:
    member = await _require_membership(db, user_id, workspace_id)
    if not member.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace admin required")
    return member


async def _admin_count(db: AsyncSession, workspace_id: UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.is_admin.is_(True),
        )
    )
    return result.scalar_one()


async def _ensure_not_last_admin(db: AsyncSession, workspace_id: UUID, member: WorkspaceMember) -> None:
    if member.is_admin and await _admin_count(db, workspace_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove or demote the last workspace admin",
        )


async def _get_workspace(db: AsyncSession, workspace_id: UUID) -> Workspace:
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


async def _load_member(db: AsyncSession, workspace_id: UUID, user_id: UUID) -> WorkspaceMember:
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


async def _clear_active_workspace_for_workspace(db: AsyncSession, workspace_id: UUID) -> None:
    users_with_active = await db.execute(select(User).where(User.active_workspace_id == workspace_id))
    for u in users_with_active.scalars().all():
        u.active_workspace_id = None


async def create_workspace(
    payload: WorkspaceCreateRequest, user: User, db: AsyncSession
) -> WorkspaceResponse:
    slug_taken = await db.execute(select(Workspace).where(Workspace.slug == payload.slug))
    if slug_taken.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace slug already taken")

    workspace = Workspace(name=payload.name, slug=payload.slug)
    db.add(workspace)
    await db.flush()

    db.add(WorkspaceMember(user_id=user.id, workspace_id=workspace.id, is_admin=True))

    if not user.active_workspace_id:
        user.active_workspace_id = workspace.id

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace slug already taken")

    await db.refresh(workspace)
    return WorkspaceResponse.model_validate(workspace)


async def list_workspaces(user: User, db: AsyncSession) -> list[WorkspaceResponse]:
    result = await db.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.name)
    )
    return [WorkspaceResponse.model_validate(ws) for ws in result.scalars().all()]


async def get_workspace(workspace_id: UUID, user: User, db: AsyncSession) -> WorkspaceResponse:
    await _require_membership(db, user.id, workspace_id)
    workspace = await _get_workspace(db, workspace_id)
    return WorkspaceResponse.model_validate(workspace)


async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceUpdateRequest,
    user: User,
    db: AsyncSession,
) -> WorkspaceResponse:
    await _require_admin(db, user.id, workspace_id)
    workspace = await _get_workspace(db, workspace_id)

    if payload.name is not None:
        workspace.name = payload.name
    if payload.slug is not None:
        if payload.slug != workspace.slug:
            slug_taken = await db.execute(
                select(Workspace).where(
                    Workspace.slug == payload.slug,
                    Workspace.id != workspace_id,
                )
            )
            if slug_taken.scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace slug already taken")
        workspace.slug = payload.slug

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace slug already taken")

    await db.refresh(workspace)
    return WorkspaceResponse.model_validate(workspace)


async def delete_workspace(workspace_id: UUID, user: User, db: AsyncSession) -> None:
    await _require_admin(db, user.id, workspace_id)
    workspace = await _get_workspace(db, workspace_id)
    await _clear_active_workspace_for_workspace(db, workspace_id)
    await db.delete(workspace)
    await db.commit()


async def list_members(workspace_id: UUID, user: User, db: AsyncSession) -> list[MemberResponse]:
    await _require_membership(db, user.id, workspace_id)
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.joined_at)
    )
    return [MemberResponse.model_validate(m) for m in result.scalars().all()]


async def add_member(
    workspace_id: UUID, payload: AddMemberRequest, user: User, db: AsyncSession
) -> MemberResponse:
    await _require_admin(db, user.id, workspace_id)
    await _get_workspace(db, workspace_id)

    target_result = await db.execute(
        select(User).where(
            User.email == payload.email,
            User.is_active.is_(True),
        )
    )
    target_user = target_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == target_user.id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    member = WorkspaceMember(user_id=target_user.id, workspace_id=workspace_id, is_admin=False)
    db.add(member)
    await db.commit()

    return MemberResponse.model_validate(await _load_member(db, workspace_id, target_user.id))


async def update_member(
    workspace_id: UUID,
    member_user_id: UUID,
    payload: UpdateMemberRequest,
    user: User,
    db: AsyncSession,
) -> MemberResponse:
    await _require_admin(db, user.id, workspace_id)
    member = await _load_member(db, workspace_id, member_user_id)

    if member.is_admin and not payload.is_admin:
        await _ensure_not_last_admin(db, workspace_id, member)

    member.is_admin = payload.is_admin
    await db.commit()

    return MemberResponse.model_validate(await _load_member(db, workspace_id, member_user_id))


async def delete_member(
    workspace_id: UUID, member_user_id: UUID, user: User, db: AsyncSession
) -> None:
    actor = await _require_membership(db, user.id, workspace_id)
    member = await _load_member(db, workspace_id, member_user_id)

    if member_user_id != user.id and not actor.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace admin required")

    await _ensure_not_last_admin(db, workspace_id, member)

    if member.user.active_workspace_id == workspace_id:
        member.user.active_workspace_id = None

    await db.delete(member)
    await db.commit()


async def activate_workspace(workspace_id: UUID, user: User, db: AsyncSession) -> TokenResponse:
    await _require_membership(db, user.id, workspace_id)
    await _get_workspace(db, workspace_id)

    user.active_workspace_id = workspace_id
    await db.commit()

    workspace_id_str = str(workspace_id)
    return TokenResponse(
        access_token=create_access_token(str(user.id), workspace_id_str),
        refresh_token=create_refresh_token(str(user.id), workspace_id_str),
    )

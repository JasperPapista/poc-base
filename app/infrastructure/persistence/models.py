import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    memberships = relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")
    active_workspace = relationship("Workspace", foreign_keys=[active_workspace_id])


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_user_workspace"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="memberships")
    workspace = relationship("Workspace", back_populates="members")

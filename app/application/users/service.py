from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models import User
from app.application.dto import UserResponse


async def get_me(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


async def delete_me(user: User, db: AsyncSession) -> None:
    await db.delete(user)
    await db.commit()

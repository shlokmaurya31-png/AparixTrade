import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.domains.audit.service import log_action
from app.models.user import User, UserPreferences


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.preferences)).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, *, email: str, password: str, full_name: str) -> User:
    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise EmailAlreadyRegisteredError(email)

    user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
    db.add(user)
    await db.flush()  # populate user.id before creating the FK'd row below

    user.preferences = UserPreferences(user_id=user.id)
    db.add(user.preferences)

    await log_action(db, user_id=user.id, action="user.register", input_data={"email": email})
    await db.commit()
    await db.refresh(user, attribute_names=["preferences"])
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()

    await log_action(db, user_id=user.id, action="user.login")
    await db.commit()
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).options(selectinload(User.preferences)).where(User.id == user_id))
    return result.scalar_one_or_none()

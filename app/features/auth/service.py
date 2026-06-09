from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.features.auth import repository
from app.features.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from app.features.auth.models import User, UserRole
from app.features.auth.schemas import PasswordChange, UserCreate


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await repository.get_user_by_email(session, email)
    if not user:
        raise InvalidCredentialsError()
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError()
    if not user.is_active:
        raise InactiveUserError()
    return user


async def register_user(session: AsyncSession, data: UserCreate) -> User:
    existing = await repository.get_user_by_email(session, data.email)
    if existing:
        raise EmailAlreadyRegisteredError()
    hashed = hash_password(data.password)
    return await repository.create_user(
        session,
        email=data.email,
        hashed_password=hashed,
        role=data.role,
    )


async def get_user_or_404(session: AsyncSession, user_id: int) -> User:
    user = await repository.get_user_by_id(session, user_id)
    if not user:
        raise UserNotFoundError(user_id)
    return user


async def list_users(session: AsyncSession, offset: int, limit: int) -> list[User]:
    return await repository.list_users(session, offset, limit)


async def change_password(
    session: AsyncSession, user: User, data: PasswordChange
) -> User:
    if not verify_password(data.current_password, user.hashed_password):
        raise InvalidCredentialsError()
    hashed = hash_password(data.new_password)
    return await repository.update_user(session, user, hashed_password=hashed)


async def set_user_active(
    session: AsyncSession, user_id: int, active: bool
) -> User:
    user = await get_user_or_404(session, user_id)
    return await repository.update_user(session, user, is_active=active)


async def change_user_role(
    session: AsyncSession, user_id: int, role: UserRole
) -> User:
    user = await get_user_or_404(session, user_id)
    return await repository.update_user(session, user, role=role)

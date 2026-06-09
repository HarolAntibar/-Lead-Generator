from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.features.auth import repository
from app.features.auth.constants import SESSION_USER_ID_KEY
from app.features.auth.exceptions import NotAuthenticatedException, PermissionDeniedError
from app.features.auth.models import User, UserRole


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        raise NotAuthenticatedException()
    user = await repository.get_user_by_id(session, int(user_id))
    if not user or not user.is_active:
        request.session.clear()
        raise NotAuthenticatedException()
    # Store on request.state so templates can access it via request.state.user
    request.state.user = user
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise PermissionDeniedError()
    return current_user

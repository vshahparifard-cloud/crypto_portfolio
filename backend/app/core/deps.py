"""Request-scoped dependencies. Handlers get a session and a user, nothing else."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Unauthorized
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("برای این کار باید وارد شوید")
    user = await session.get(User, decode_access_token(authorization.split(" ", 1)[1].strip()))
    if user is None or not user.is_active:
        raise Unauthorized("حساب در دسترس نیست")
    return user


UserDep = Annotated[User, Depends(current_user)]

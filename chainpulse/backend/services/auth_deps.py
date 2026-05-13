"""FastAPI dependencies — current_user via bearer token, WS token validator."""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.db.postgres import get_session
from chainpulse.backend.models import User
from chainpulse.backend.services.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def _user_from_token(token: str, session: AsyncSession) -> User:
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


async def current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    return await _user_from_token(token, session)


async def ws_user_from_token(token: str, session: AsyncSession) -> User:
    """Called inside websocket handler — JWT comes from query param."""
    return await _user_from_token(token, session)

"""/auth/register, /auth/login — JWT issue. Login rate-limited 5/min/IP."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.db.postgres import get_session
from chainpulse.backend.models import User
from chainpulse.backend.schemas.user import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from chainpulse.backend.services.ratelimit import limiter
from chainpulse.backend.services.security import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        company=body.company,
        role=body.role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: UserLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    token, ttl = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=ttl)

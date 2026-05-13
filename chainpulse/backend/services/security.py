"""JWT issue + verify, password hash + verify."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from chainpulse.backend.config.settings import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID, extra: dict[str, Any] | None = None) -> tuple[str, int]:
    s = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=s.jwt_expiry_hours)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, s.jwt_expiry_hours * 3600


def decode_token(token: str) -> dict[str, Any]:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as e:
        raise ValueError(f"invalid token: {e}") from e

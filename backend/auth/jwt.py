"""
SELLO — Authentication Service
JWT-based auth with refresh tokens, RBAC, and password hashing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from core.config import get_settings

settings = get_settings()

# ── Password Hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT Tokens ────────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    token_type: str = "access"


def create_token(
    user_id: uuid.UUID,
    email: str,
    role: str,
    token_type: str = "access",
    expires_delta: Optional[timedelta] = None,
) -> str:
    if expires_delta is None:
        if token_type == "access":
            expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        else:
            expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenData(
            user_id=uuid.UUID(payload["sub"]),
            email=payload["email"],
            role=payload["role"],
            token_type=payload.get("type", "access"),
        )
    except JWTError:
        return None


def create_token_pair(user_id: uuid.UUID, email: str, role: str) -> dict:
    """Returns both access and refresh tokens."""
    return {
        "access_token": create_token(user_id, email, role, "access"),
        "refresh_token": create_token(user_id, email, role, "refresh"),
        "token_type": "bearer",
    }

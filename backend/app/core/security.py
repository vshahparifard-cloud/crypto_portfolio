"""Password hashing, JWT access tokens, opaque refresh/email tokens (D5, D10)."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings
from app.core.errors import Unauthorized

_hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, ValueError):
        return False


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Returns (jwt, expires_in_seconds)."""
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("نشست منقضی شده است") from exc
    except jwt.InvalidTokenError as exc:
        raise Unauthorized("توکن نامعتبر است") from exc
    if payload.get("typ") != "access":
        raise Unauthorized("نوع توکن نامعتبر است")
    return uuid.UUID(str(payload["sub"]))


def new_opaque_token() -> tuple[str, str]:
    """Returns (plaintext, sha256) — only the digest is ever stored."""
    raw = secrets.token_urlsafe(32)
    return raw, token_digest(raw)


def token_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

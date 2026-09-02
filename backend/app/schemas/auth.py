from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import Schema


class RegisterIn(Schema):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginIn(Schema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailIn(Schema):
    email: EmailStr


class ResetIn(Schema):
    token: str = Field(min_length=10)
    password: str = Field(min_length=10, max_length=128)


class TokenOut(Schema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(Schema):
    id: str
    email: EmailStr
    is_verified: bool
    telegram_connected: bool
    telegram_linked_at: datetime | None
    timezone: str
    quiet_from_hour: int | None
    quiet_to_hour: int | None
    created_at: datetime


class SettingsIn(Schema):
    timezone: str | None = Field(default=None, max_length=64)
    quiet_from_hour: int | None = Field(default=None, ge=0, le=23)
    quiet_to_hour: int | None = Field(default=None, ge=0, le=23)

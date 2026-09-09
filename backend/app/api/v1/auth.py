"""Auth endpoints. Validate, call the service, map the schema — no logic here."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Response, status

from app.core.config import settings
from app.core.deps import SessionDep, UserDep
from app.db.models import User
from app.schemas.auth import (
    EmailIn,
    LoginIn,
    RegisterIn,
    RegisterOut,
    ResetIn,
    SettingsIn,
    TokenOut,
    UserOut,
)
from app.schemas.common import Message
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "cp_refresh"


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        is_verified=user.is_verified,
        telegram_connected=user.telegram_chat_id is not None,
        telegram_linked_at=user.telegram_linked_at,
        timezone=user.timezone,
        quiet_from_hour=user.quiet_from_hour,
        quiet_to_hour=user.quiet_to_hour,
        created_at=user.created_at,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        samesite="lax",
        secure=not settings.is_dev,
        path="/api/v1/auth",
    )


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, response: Response, session: SessionDep) -> RegisterOut:
    user = await auth_service.register(session, payload.email, payload.password)
    if settings.require_email_verification:
        return RegisterOut(
            message="ایمیل تایید برای شما ارسال شد. تا تایید نشود ورود ممکن نیست.",
            verification_required=True,
        )
    # gate off: hand back a session so registration lands the user inside the app
    access, expires_in, refresh = await auth_service.issue_tokens(session, user)
    _set_refresh_cookie(response, refresh)
    return RegisterOut(
        message="حساب شما ساخته و وارد شدید.",
        verification_required=False,
        access_token=access,
        expires_in=expires_in,
    )


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, response: Response, session: SessionDep) -> TokenOut:
    user = await auth_service.authenticate(session, payload.email, payload.password)
    access, expires_in, refresh = await auth_service.issue_tokens(session, user)
    _set_refresh_cookie(response, refresh)
    return TokenOut(access_token=access, expires_in=expires_in)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    response: Response,
    session: SessionDep,
    cp_refresh: str | None = Cookie(default=None),
) -> TokenOut:
    access, expires_in, rotated = await auth_service.rotate_refresh(session, cp_refresh or "")
    _set_refresh_cookie(response, rotated)
    return TokenOut(access_token=access, expires_in=expires_in)


@router.post("/logout", response_model=Message)
async def logout(
    response: Response,
    session: SessionDep,
    cp_refresh: str | None = Cookie(default=None),
) -> Message:
    await auth_service.revoke_refresh(session, cp_refresh)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    return Message(message="از حساب خارج شدید")


@router.post("/verify/{token}", response_model=Message)
async def verify_email(token: str, session: SessionDep) -> Message:
    await auth_service.verify_email(session, token)
    return Message(message="ایمیل شما تایید شد؛ حالا می‌توانید وارد شوید")


@router.post("/verify/resend", response_model=Message)
async def resend_verification(payload: EmailIn, session: SessionDep) -> Message:
    await auth_service.resend_verification(session, payload.email)
    return Message(message="اگر این حساب تاییدنشده باشد، ایمیل تایید دوباره ارسال شد")


@router.post("/password/forgot", response_model=Message)
async def forgot_password(payload: EmailIn, session: SessionDep) -> Message:
    await auth_service.request_password_reset(session, payload.email)
    # identical response for known and unknown addresses (no account enumeration)
    return Message(message="اگر این ایمیل ثبت شده باشد، لینک بازیابی ارسال شد")


@router.post("/password/reset", response_model=Message)
async def reset_password(payload: ResetIn, session: SessionDep) -> Message:
    await auth_service.reset_password(session, payload.token, payload.password)
    return Message(message="رمز عبور تغییر کرد و همه نشست‌های قبلی بسته شد")


@router.get("/me", response_model=UserOut)
async def me(user: UserDep) -> UserOut:
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
async def update_settings(payload: SettingsIn, user: UserDep, session: SessionDep) -> UserOut:
    if payload.timezone is not None:
        user.timezone = payload.timezone
    if payload.quiet_from_hour is not None:
        user.quiet_from_hour = payload.quiet_from_hour
    if payload.quiet_to_hour is not None:
        user.quiet_to_hour = payload.quiet_to_hour
    await session.commit()
    return _user_out(user)

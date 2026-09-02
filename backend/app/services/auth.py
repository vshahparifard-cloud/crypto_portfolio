"""Registration, login, email verification and password reset (D5, D10).

Two rules shape this module: the API never learns whether an email exists
(no account enumeration), and no route blocks on SMTP — mail goes to the outbox.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import Conflict, EmailNotVerified, NotFound, Unauthorized
from app.core.security import (
    create_access_token,
    hash_password,
    new_opaque_token,
    token_digest,
    verify_password,
)
from app.db.models import EmailToken, Portfolio, RefreshToken, User
from app.domain.enums import EmailPurpose
from app.services import email as email_service
from app.services.ratelimit import enforce

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(hours=2)


async def _by_email(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()


async def _issue_email_token(
    session: AsyncSession, user: User, purpose: EmailPurpose, ttl: timedelta
) -> str:
    raw, digest = new_opaque_token()
    session.add(
        EmailToken(
            token_hash=digest,
            user_id=user.id,
            purpose=purpose,
            expires_at=datetime.now(UTC) + ttl,
        )
    )
    await email_service.enqueue(
        session, user_id=user.id, to_email=user.email, purpose=purpose, token=raw
    )
    return raw


async def register(session: AsyncSession, email: str, password: str) -> User:
    normalized = email.strip().lower()
    user = User(email=normalized, password_hash=hash_password(password), is_verified=False)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("این ایمیل قبلاً ثبت شده است") from exc

    session.add(Portfolio(user_id=user.id, name="سبد من", is_default=True))
    await _issue_email_token(session, user, EmailPurpose.verify, VERIFY_TTL)
    await session.commit()
    return user


async def resend_verification(session: AsyncSession, email: str) -> None:
    await enforce(
        f"resend:{email.strip().lower()}", 3, 3600, "بیش از حد درخواست ارسال دوباره داده‌اید"
    )
    user = await _by_email(session, email)
    # deliberately silent for unknown or already verified accounts
    if user is not None and not user.is_verified:
        await _issue_email_token(session, user, EmailPurpose.verify, VERIFY_TTL)
        await session.commit()


async def _consume_token(
    session: AsyncSession, raw_token: str, purpose: EmailPurpose
) -> EmailToken:
    row = (
        await session.execute(
            select(EmailToken).where(
                EmailToken.token_hash == token_digest(raw_token),
                EmailToken.purpose == purpose,
            )
        )
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at < datetime.now(UTC):
        raise NotFound("این لینک نامعتبر یا منقضی است")
    row.used_at = datetime.now(UTC)
    return row


async def verify_email(session: AsyncSession, raw_token: str) -> User:
    row = await _consume_token(session, raw_token, EmailPurpose.verify)
    user = await session.get(User, row.user_id)
    if user is None:
        raise NotFound("کاربر یافت نشد")
    user.is_verified = True
    await session.commit()
    return user


async def request_password_reset(session: AsyncSession, email: str) -> None:
    await enforce(
        f"forgot:{email.strip().lower()}", 3, 3600, "بیش از حد درخواست بازیابی داده‌اید"
    )
    user = await _by_email(session, email)
    if user is not None:
        await _issue_email_token(session, user, EmailPurpose.reset, RESET_TTL)
        await session.commit()


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> None:
    row = await _consume_token(session, raw_token, EmailPurpose.reset)
    user = await session.get(User, row.user_id)
    if user is None:
        raise NotFound("کاربر یافت نشد")
    user.password_hash = hash_password(new_password)
    user.is_verified = True  # reaching the mailbox proves ownership
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    await enforce(f"login:{email.strip().lower()}", 5, 60, "تلاش‌های ورود بیش از حد مجاز است")
    user = await _by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise Unauthorized("ایمیل یا رمز عبور نادرست است")
    if not user.is_active:
        raise Unauthorized("این حساب غیرفعال شده است")
    if not user.is_verified:
        raise EmailNotVerified(
            "ابتدا ایمیل خود را تایید کنید", {"email": user.email, "action": "resend_verification"}
        )
    return user


async def issue_tokens(session: AsyncSession, user: User) -> tuple[str, int, str]:
    """Returns (access_token, expires_in, refresh_token_plaintext)."""
    access, expires_in = create_access_token(user.id)
    raw, digest = new_opaque_token()
    session.add(
        RefreshToken(
            token_hash=digest,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    await session.commit()
    return access, expires_in, raw


async def rotate_refresh(session: AsyncSession, raw_refresh: str) -> tuple[str, int, str]:
    row = await session.get(RefreshToken, token_digest(raw_refresh))
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or row.expires_at < now:
        raise Unauthorized("نشست منقضی شده است؛ دوباره وارد شوید")
    row.revoked_at = now
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("حساب در دسترس نیست")
    return await issue_tokens(session, user)


async def revoke_refresh(session: AsyncSession, raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    row = await session.get(RefreshToken, token_digest(raw_refresh))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await session.commit()


async def default_portfolio_id(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    row = (
        await session.execute(
            select(Portfolio.id)
            .where(Portfolio.user_id == user_id)
            .order_by(Portfolio.is_default.desc(), Portfolio.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        portfolio = Portfolio(user_id=user_id, name="سبد من", is_default=True)
        session.add(portfolio)
        await session.commit()
        return portfolio.id
    return row

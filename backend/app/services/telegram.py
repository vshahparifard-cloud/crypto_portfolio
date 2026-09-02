"""Telegram: account linking and outbound alert messages.

Sending happens only from the worker (D6). This module builds the payloads and
owns the wire call, so the retry policy has exactly one place to live.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, NotFound, UpstreamUnavailable
from app.db.models import AlertEvent, Holding, Portfolio, TelegramLinkToken, User
from app.domain.enums import AlertKind

log = logging.getLogger(__name__)
LINK_TTL = timedelta(minutes=10)
API_ROOT = "https://api.telegram.org"

KIND_TITLES = {
    AlertKind.price_above: "حد سود",
    AlertKind.price_below: "حد ضرر",
    AlertKind.pct_up: "جهش ناگهانی",
    AlertKind.pct_down: "ریزش ناگهانی",
}


def _fmt(value: Decimal | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    quantized = round(value, digits)
    return f"{quantized:,}"


async def create_link_token(session: AsyncSession, user_id: uuid.UUID) -> dict[str, str]:
    token = secrets.token_urlsafe(24)
    session.add(
        TelegramLinkToken(
            token=token, user_id=user_id, expires_at=datetime.now(UTC) + LINK_TTL
        )
    )
    await session.commit()
    return {
        "token": token,
        "deep_link": f"https://t.me/{settings.telegram_bot_username}?start={token}",
        "expires_in_seconds": str(int(LINK_TTL.total_seconds())),
    }


async def consume_link_token(session: AsyncSession, token: str, chat_id: int) -> User:
    row = await session.get(TelegramLinkToken, token)
    if row is None or row.used_at is not None or row.expires_at < datetime.now(UTC):
        raise NotFound("این لینک نامعتبر یا منقضی است")
    user = await session.get(User, row.user_id)
    if user is None:
        raise NotFound("کاربر یافت نشد")

    other = (
        await session.execute(select(User).where(User.telegram_chat_id == chat_id))
    ).scalar_one_or_none()
    if other is not None and other.id != user.id:
        other.telegram_chat_id = None
        other.telegram_linked_at = None

    row.used_at = datetime.now(UTC)
    user.telegram_chat_id = chat_id
    user.telegram_linked_at = datetime.now(UTC)
    await session.commit()
    return user


async def unlink(session: AsyncSession, user: User) -> None:
    user.telegram_chat_id = None
    user.telegram_linked_at = None
    await session.commit()


async def holding_line(
    session: AsyncSession, user_id: uuid.UUID, coin_id: str, price: Decimal
) -> str:
    holding = (
        await session.execute(
            select(Holding)
            .join(Portfolio, Portfolio.id == Holding.portfolio_id)
            .where(Portfolio.user_id == user_id, Holding.coin_id == coin_id)
        )
    ).scalar_one_or_none()
    if holding is None:
        return ""
    value = holding.quantity * price
    cost = holding.quantity * holding.avg_buy_price
    pnl = value - cost
    sign = "+" if pnl >= 0 else "−"
    return (
        f"\nدارایی شما: {_fmt(holding.quantity, 8)} — ${_fmt(value)}"
        f"\nسود/زیان: {sign}${_fmt(abs(pnl))}"
    )


async def render_alert_message(session: AsyncSession, event: AlertEvent) -> str:
    alert = event.alert
    title = KIND_TITLES[alert.kind]
    symbol = alert.coin.symbol
    price = event.price_at_trigger
    sampled = event.sampled_at.astimezone(UTC).strftime("%H:%M UTC")

    if alert.kind in (AlertKind.pct_up, AlertKind.pct_down):
        direction = "رشد" if alert.kind is AlertKind.pct_up else "افت"
        head = (
            f"{alert.coin.name} در {alert.window_minutes} دقیقه "
            f"{_fmt(alert.threshold)}% {direction} کرد."
        )
    else:
        relation = "عبور کرد" if alert.kind is AlertKind.price_above else "پایین آمد"
        head = f"{alert.coin.name} از ${_fmt(alert.threshold)} {relation}."

    body = (
        f"🔔 {title} — {symbol}\n{head}"
        f"\nقیمت: ${_fmt(price)}"
        f"\nزمان نمونه‌گیری: {sampled}"
    )
    body += await holding_line(session, alert.user_id, alert.coin_id, price)
    body += "\n\nداده هر ۵ دقیقه از CoinGecko نمونه‌گیری می‌شود."
    return body


def alert_keyboard(coin_id: str, alert_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "مشاهده نمودار",
                    "url": f"{settings.public_base_url.rstrip('/')}/coin/{coin_id}",
                },
                {"text": "غیرفعال کردن هشدار", "callback_data": f"mute:{alert_id}"},
            ]
        ]
    }


async def send_message(
    chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
) -> int:
    if not settings.telegram_bot_token:
        raise AppError("توکن ربات تلگرام تنظیم نشده است")
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    url = f"{API_ROOT}/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable("ارسال به تلگرام ممکن نشد") from exc
    if response.status_code == 429:
        retry_after = response.json().get("parameters", {}).get("retry_after", 5)
        raise UpstreamUnavailable(f"سقف نرخ تلگرام؛ {retry_after} ثانیه بعد")
    if response.status_code >= 400:
        raise UpstreamUnavailable(f"تلگرام پاسخ {response.status_code} داد: {response.text[:200]}")
    return int(response.json()["result"]["message_id"])

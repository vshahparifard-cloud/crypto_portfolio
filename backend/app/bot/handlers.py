"""Bot handlers (aiogram v3). One handler set, two transports.

Long polling is used in development (`python -m app.bot.runner`) and the webhook
route feeds the very same dispatcher in production, so behaviour cannot drift
between environments.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, Update
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import AppError
from app.db.models import Alert, User
from app.db.session import SessionFactory
from app.domain.enums import AlertStatus
from app.services import telegram as telegram_service

log = logging.getLogger(__name__)
router = Router(name="coinpulse")

WELCOME = (
    "سلام 👋\nمن ربات هشدار کوین‌پالس هستم.\n\n"
    "برای وصل شدن، از صفحه تنظیمات سایت روی «باز کردن ربات» بزنید تا لینک اختصاصی‌تان "
    "ساخته شود. همان لینک حساب شما را به این گفتگو وصل می‌کند.\n\n"
    "دستورها:\n/status وضعیت اتصال\n/alerts هشدارهای فعال"
)


@router.message(CommandStart(deep_link=True))
async def start_with_token(message: Message, command: CommandObject) -> None:
    token = (command.args or "").strip()
    chat_id = message.chat.id
    async with SessionFactory() as session:
        try:
            user = await telegram_service.consume_link_token(session, token, chat_id)
        except AppError as exc:
            await message.answer(f"❌ {exc.message}\nلینک تازه‌ای از سایت بگیرید.")
            return
    await message.answer(
        f"✅ حساب {user.email} وصل شد.\nاز این پس هشدارهای قیمتی‌تان همین‌جا می‌رسد."
    )


@router.message(CommandStart(deep_link=False))
async def start_plain(message: Message) -> None:
    await message.answer(WELCOME)


@router.message(Command("status"))
async def status(message: Message) -> None:
    async with SessionFactory() as session:
        user = (
            await session.execute(select(User).where(User.telegram_chat_id == message.chat.id))
        ).scalar_one_or_none()
    if user is None:
        await message.answer("این گفتگو به هیچ حسابی وصل نیست. از سایت لینک اتصال بگیرید.")
        return
    await message.answer(f"وصل به {user.email} ✅")


@router.message(Command("alerts"))
async def list_alerts(message: Message) -> None:
    async with SessionFactory() as session:
        user = (
            await session.execute(select(User).where(User.telegram_chat_id == message.chat.id))
        ).scalar_one_or_none()
        if user is None:
            await message.answer("این گفتگو به هیچ حسابی وصل نیست.")
            return
        alerts = (
            await session.execute(
                select(Alert)
                .where(Alert.user_id == user.id, Alert.status != AlertStatus.expired)
                .order_by(Alert.created_at.desc())
                .limit(10)
            )
        ).scalars().all()
    if not alerts:
        await message.answer("هشدار فعالی ندارید.")
        return
    lines = [
        f"• {alert.coin.symbol} — {telegram_service.KIND_TITLES[alert.kind]} "
        f"{alert.threshold} ({alert.status.value})"
        for alert in alerts
    ]
    await message.answer("هشدارهای شما:\n" + "\n".join(lines))


@router.callback_query()
async def on_callback(callback: Any) -> None:
    """Only one action for now: muting the alert a message came from."""
    data = str(callback.data or "")
    if not data.startswith("mute:"):
        await callback.answer("این دکمه دیگر فعال نیست")
        return
    try:
        alert_id = uuid.UUID(data.split(":", 1)[1])
    except ValueError:
        await callback.answer("شناسه هشدار نامعتبر است")
        return
    async with SessionFactory() as session:
        alert = await session.get(Alert, alert_id)
        if alert is None:
            await callback.answer("این هشدار حذف شده است")
            return
        alert.status = AlertStatus.paused
        await session.commit()
    await callback.answer("هشدار متوقف شد ✅")


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


_dispatcher: Dispatcher | None = None
_bot: Bot | None = None


def bot_instance() -> Bot:
    global _bot
    if _bot is None:
        if not settings.telegram_bot_token:
            raise AppError("توکن ربات تلگرام تنظیم نشده است")
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def handle_update(payload: dict[str, Any]) -> None:
    """Webhook entry point: feed the same dispatcher the poller uses."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = build_dispatcher()
    bot = bot_instance()
    await _dispatcher.feed_webhook_update(bot, Update.model_validate(payload, context={"bot": bot}))

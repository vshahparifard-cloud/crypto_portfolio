from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.deps import SessionDep, UserDep
from app.core.errors import AppError, NotFound
from app.schemas.common import Message
from app.schemas.telegram import LinkOut, TelegramStatusOut
from app.services import telegram as telegram_service

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.get("/status", response_model=TelegramStatusOut)
async def status(user: UserDep) -> TelegramStatusOut:
    return TelegramStatusOut(
        connected=user.telegram_chat_id is not None, chat_id=user.telegram_chat_id
    )


@router.post("/link", response_model=LinkOut)
async def create_link(user: UserDep, session: SessionDep) -> LinkOut:
    return LinkOut.model_validate(await telegram_service.create_link_token(session, user.id))


@router.post("/test", response_model=Message)
async def send_test(user: UserDep) -> Message:
    if user.telegram_chat_id is None:
        raise AppError("ابتدا حساب تلگرام را وصل کنید")
    await telegram_service.send_message(
        user.telegram_chat_id,
        "🔔 پیام آزمایشی کوین‌پالس\nمسیر اطلاع‌رسانی سالم است؛ هشدارهای شما از همین‌جا می‌آیند.",
    )
    return Message(message="پیام آزمایشی ارسال شد")


@router.delete("/link", response_model=Message)
async def unlink(user: UserDep, session: SessionDep) -> Message:
    await telegram_service.unlink(session, user)
    return Message(message="اتصال تلگرام قطع شد")


@router.post("/webhook/{secret}", response_model=Message)
async def webhook(secret: str, request: Request) -> Message:
    """Production path for bot updates. Dev uses long polling (app.bot.runner)."""
    if secret != settings.telegram_webhook_secret:
        raise NotFound("مسیر نامعتبر")
    update: dict[str, Any] = await request.json()
    from app.bot.handlers import handle_update

    await handle_update(update)
    return Message(message="ok")

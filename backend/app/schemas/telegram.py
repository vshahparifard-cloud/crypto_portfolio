from __future__ import annotations

from app.schemas.common import Schema


class LinkOut(Schema):
    token: str
    deep_link: str
    expires_in_seconds: str


class TelegramStatusOut(Schema):
    connected: bool
    chat_id: int | None = None

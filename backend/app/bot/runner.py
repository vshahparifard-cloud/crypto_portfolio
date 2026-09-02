"""Development transport: long polling, so no public URL is needed locally."""
from __future__ import annotations

import asyncio
import logging

from app.bot.handlers import bot_instance, build_dispatcher
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
)
log = logging.getLogger(__name__)


async def main() -> None:
    if not settings.telegram_bot_token:
        log.warning("TELEGRAM_BOT_TOKEN is empty — bot disabled, sleeping")
        while True:
            await asyncio.sleep(3600)
    bot = bot_instance()
    dispatcher = build_dispatcher()
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("bot polling as @%s", settings.telegram_bot_username)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

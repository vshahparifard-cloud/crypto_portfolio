"""Manual triggers for the same jobs: python -m app.workers.oneshot <name>

Used by `make seed` on a fresh database and when debugging the price pipeline
without waiting for the next cron tick.
"""
from __future__ import annotations

import asyncio
import sys

from app.core.config import settings
from app.db.session import SessionFactory, engine
from app.services import alerts as alert_service
from app.services import market as market_service
from app.services.cache import close_redis
from app.services.price_source.coingecko import CoinGeckoSource

COMMANDS = ("sync_coins", "poll", "evaluate", "backfill")


async def _run(command: str, argument: str | None) -> None:
    source = CoinGeckoSource()
    try:
        async with SessionFactory() as session:
            if command == "sync_coins":
                count = await market_service.sync_top_list(session, source, settings.top_n_coins)
                print(f"tracked coins: {count}")
            elif command == "poll":
                count = await market_service.poll_prices(session, source, settings.top_n_coins)
                await market_service.aggregate_candles(session)
                print(f"sampled coins: {count}")
            elif command == "evaluate":
                fired = await alert_service.evaluate_active_alerts(session)
                print(f"alerts fired: {fired}")
            elif command == "backfill":
                if not argument:
                    raise SystemExit("usage: backfill <coin_id>")
                written = await market_service.backfill_coin(session, source, argument)
                print(f"candles written: {written}")
            else:
                raise SystemExit(f"unknown command; expected one of {COMMANDS}")
    finally:
        await source.aclose()
        await close_redis()
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(f"usage: python -m app.workers.oneshot {'|'.join(COMMANDS)}")
    asyncio.run(_run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))

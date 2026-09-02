"""ARQ worker definition (D2). Run with: arq app.workers.settings.WorkerSettings"""
from __future__ import annotations

import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.services.price_source.coingecko import CoinGeckoSource
from app.workers import tasks

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
)


def _poll_minutes() -> set[int]:
    """Cron minutes derived from POLL_INTERVAL_SECONDS so the budget stays honest."""
    step = max(settings.poll_interval_seconds // 60, 1)
    return {minute for minute in range(60) if minute % step == 0}


async def startup(ctx: dict[str, Any]) -> None:
    ctx["price_source"] = CoinGeckoSource()


async def shutdown(ctx: dict[str, Any]) -> None:
    source: CoinGeckoSource = ctx["price_source"]
    await source.aclose()


class WorkerSettings:
    functions = [
        tasks.poll_prices,
        tasks.dispatch_alerts,
        tasks.dispatch_emails,
        tasks.sync_coin_list,
        tasks.backfill_coin,
        tasks.prune_old_data,
    ]
    cron_jobs = [
        # the single upstream call, then aggregate + evaluate (D13)
        cron(tasks.poll_prices, minute=_poll_minutes(), second=5, timeout=120),
        # retry sweeps: anything the fast path could not deliver
        cron(tasks.dispatch_alerts, second={0, 30}, timeout=120),
        cron(tasks.dispatch_emails, second={10, 40}, timeout=120),
        cron(tasks.sync_coin_list, hour={0}, minute={5}, timeout=300),
        cron(tasks.prune_old_data, hour={3}, minute={30}, timeout=600),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 1  # retries are our own bookkeeping, not arq's
    job_timeout = 300

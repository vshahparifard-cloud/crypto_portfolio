"""Background jobs. The only writers of prices and the only senders of messages.

Delivery follows the outbox pattern (D6/D12): a job claims rows whose retry time
has come, tries once, and writes down what happened. Nothing is ever lost by a
crash — the row is still pending on the next run.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AlertEvent, Coin, EmailOutbox, User
from app.db.session import SessionFactory
from app.domain.enums import DeliveryState
from app.services import alerts as alert_service
from app.services import cache
from app.services import email as email_service
from app.services import market as market_service
from app.services import telegram as telegram_service
from app.services.price_source.coingecko import CoinGeckoSource

log = logging.getLogger(__name__)

TELEGRAM_RETRY = (
    timedelta(seconds=5),
    timedelta(seconds=30),
    timedelta(minutes=5),
    timedelta(minutes=30),
)
BATCH = 50


def _schedule_retry(attempts: int, plan: tuple[timedelta, ...]) -> datetime | None:
    """Next attempt time, or None when the row has exhausted its plan."""
    if attempts > len(plan):
        return None
    return datetime.now(UTC) + plan[attempts - 1]


async def poll_prices(ctx: dict[str, Any]) -> dict[str, int]:
    """One CoinGecko request, then everything that follows from a fresh sample."""
    source: CoinGeckoSource = ctx["price_source"]
    async with SessionFactory() as session:
        stored = await market_service.poll_prices(session, source, settings.top_n_coins)
        if stored:
            await market_service.aggregate_candles(session)
            fired = await alert_service.evaluate_active_alerts(session)
        else:
            fired = 0
    if fired:
        await ctx["redis"].enqueue_job("dispatch_alerts")
    return {"coins": stored, "alerts_fired": fired}


async def dispatch_alerts(ctx: dict[str, Any]) -> int:
    """Send pending alert messages to telegram, one attempt per row per run."""
    sent = 0
    async with SessionFactory() as session:
        for event in await _claim(session, AlertEvent):
            user = await session.get(User, event.alert.user_id)
            if user is None or user.telegram_chat_id is None:
                event.delivery_state = DeliveryState.dead
                event.error = "کاربر حساب تلگرام وصل نکرده است"
                continue
            try:
                text = await telegram_service.render_alert_message(session, event)
                message_id = await telegram_service.send_message(
                    user.telegram_chat_id,
                    text,
                    telegram_service.alert_keyboard(event.alert.coin_id, str(event.alert_id)),
                )
            except Exception as exc:  # retry policy owns every failure
                _mark_failed(event, exc, TELEGRAM_RETRY)
                log.warning("telegram delivery failed event=%s: %s", event.id, exc)
                continue
            event.delivery_state = DeliveryState.sent
            event.telegram_message_id = message_id
            event.error = None
            sent += 1
        await session.commit()
    await cache.heartbeat("telegram_sender")
    return sent


async def dispatch_emails(ctx: dict[str, Any]) -> int:
    sent = 0
    async with SessionFactory() as session:
        for row in await _claim(session, EmailOutbox):
            try:
                await email_service.deliver(row)
            except Exception as exc:  # retry policy owns every failure
                _mark_failed(row, exc, email_service.RETRY_SCHEDULE)
                log.warning("email delivery failed row=%s: %s", row.id, exc)
                continue
            row.delivery_state = DeliveryState.sent
            row.sent_at = datetime.now(UTC)
            row.error = None
            sent += 1
        await session.commit()
    await cache.heartbeat("email_sender")
    return sent


async def _claim(session: AsyncSession, model: type[Any]) -> list[Any]:
    """Rows whose retry time has come. `skip_locked` keeps two workers apart."""
    now = datetime.now(UTC)
    return list(
        (
            await session.execute(
                select(model)
                .where(
                    model.delivery_state.in_([DeliveryState.pending, DeliveryState.failed]),
                    (model.next_retry_at.is_(None)) | (model.next_retry_at <= now),
                )
                .order_by(model.next_retry_at.asc().nullsfirst())
                .limit(BATCH)
                # lock the outbox row only: postgres rejects FOR UPDATE that
                # would touch the joined-in alert/coin rows
                .with_for_update(skip_locked=True, of=model)
            )
        )
        .scalars()
        .all()
    )


def _mark_failed(row: Any, exc: Exception, plan: tuple[timedelta, ...]) -> None:
    row.attempts += 1
    row.error = f"{type(exc).__name__}: {exc}"[:500]
    next_at = _schedule_retry(row.attempts, plan)
    if next_at is None:
        row.delivery_state = DeliveryState.dead
        row.next_retry_at = None
    else:
        row.delivery_state = DeliveryState.failed
        row.next_retry_at = next_at


# a fresh database wants history for every tracked coin, but that is two upstream
# calls each; queue them spread out and capped so the first day cannot trip the
# provider's per-minute limit (GOTCHAS)
BACKFILL_PER_RUN = 25
BACKFILL_SPACING = timedelta(seconds=45)


async def sync_coin_list(ctx: dict[str, Any]) -> int:
    """Daily: re-establish the tracked top-N, then backfill anything new."""
    source: CoinGeckoSource = ctx["price_source"]
    async with SessionFactory() as session:
        stored = await market_service.sync_top_list(session, source, settings.top_n_coins)
        pending = (
            await session.execute(
                select(Coin.id)
                .where(Coin.is_tracked.is_(True), Coin.backfilled_at.is_(None))
                .order_by(Coin.market_cap_rank.asc().nullslast())
                .limit(BACKFILL_PER_RUN)
            )
        ).scalars().all()
    for index, coin_id in enumerate(pending, start=1):
        await ctx["redis"].enqueue_job(
            "backfill_coin", coin_id, _defer_by=BACKFILL_SPACING * index
        )
    log.info("coin list synced: %s coins, %s queued for backfill", stored, len(pending))
    return stored


async def backfill_coin(ctx: dict[str, Any], coin_id: str) -> int:
    """Two upstream calls, once per coin, to give its chart a history."""
    source: CoinGeckoSource = ctx["price_source"]
    async with SessionFactory() as session:
        written = await market_service.backfill_coin(session, source, coin_id)
    log.info("backfilled %s candles for %s", written, coin_id)
    return written


async def prune_old_data(ctx: dict[str, Any]) -> None:
    """Retention (PROJECT_STATE > DB): snapshots 90d, hourly candles 2y."""
    async with SessionFactory() as session:
        await session.execute(
            text("delete from price_snapshots where ts < now() - interval '90 days'")
        )
        await session.execute(
            text(
                "delete from ohlc_candles where interval = '1h' "
                "and ts < now() - interval '2 years'"
            )
        )
        await session.execute(
            text(
                "delete from alert_events where triggered_at < now() - interval '180 days' "
                "and delivery_state in ('sent', 'dead')"
            )
        )
        await session.execute(
            text("delete from email_outbox where created_at < now() - interval '30 days'")
        )
        await session.commit()

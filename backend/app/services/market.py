"""Market data: the single write path from CoinGecko, and all read paths from us.

Everything a browser can trigger reads from Redis or PostgreSQL. The only code
that calls the upstream provider is `poll_markets` (scheduled) and
`backfill_coin` (once per coin) — see D1 and the budget line in PROJECT_STATE.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.db.models import Coin, OhlcCandle, PriceSnapshot
from app.domain.enums import CandleInterval
from app.services import cache
from app.services.price_source.base import MarketRow, PriceSource

log = logging.getLogger(__name__)

ChartRange = Literal["24h", "7d", "30d", "90d", "1y"]
RANGE_PLAN: dict[str, tuple[CandleInterval, timedelta]] = {
    "24h": (CandleInterval.h1, timedelta(hours=24)),
    "7d": (CandleInterval.h1, timedelta(days=7)),
    "30d": (CandleInterval.h1, timedelta(days=30)),
    "90d": (CandleInterval.d1, timedelta(days=90)),
    "1y": (CandleInterval.d1, timedelta(days=365)),
}


async def tracked_coin_ids(session: AsyncSession, limit: int) -> list[str]:
    """The id set the price poll must cover: the tracked top-N plus anything a
    user actually references.

    A coin that slips out of the top 50 while someone holds it or watches it
    must keep receiving prices, otherwise their portfolio silently freezes. The
    ids travel in the same single request, so this costs nothing extra.
    """
    tracked = (
        await session.execute(
            select(Coin.id)
            .where(Coin.is_tracked.is_(True))
            .order_by(Coin.market_cap_rank.asc().nullslast())
            .limit(limit)
        )
    ).scalars().all()
    referenced = (
        await session.execute(
            text(
                """
                select coin_id from holdings
                union
                select coin_id from alerts where status <> 'expired'
                """
            )
        )
    ).scalars().all()
    return sorted(set(tracked) | set(referenced))


async def poll_prices(session: AsyncSession, source: PriceSource, limit: int) -> int:
    """The 5-minute path: one request covering every coin we owe a price to."""
    coin_ids = await tracked_coin_ids(session, limit)
    if not coin_ids:
        # cold database (first boot): fall back to the ordered top-N call
        return await sync_top_list(session, source, limit)
    rows = await source.markets_by_ids(coin_ids)
    return await _store_rows(session, rows)


async def sync_top_list(session: AsyncSession, source: PriceSource, limit: int) -> int:
    """The daily ordered call that decides which coins are the top N."""
    rows = await source.top_markets(limit)
    fresh = {row.coin_id for row in rows}
    stored = await _store_rows(session, rows)
    if fresh:
        await session.execute(update(Coin).values(is_tracked=Coin.id.in_(sorted(fresh))))
        await session.commit()
    return stored


async def _store_rows(session: AsyncSession, rows: list[MarketRow]) -> int:
    """Coins, snapshots, cache, pub/sub. Returns how many rows were stored."""
    if not rows:
        log.warning("upstream returned no market rows; keeping previous cache")
        return 0

    await _upsert_coins(session, rows)
    await _insert_snapshots(session, rows)
    await session.commit()

    samples = [(row.coin_id, row.price_usd, row.sampled_at) for row in rows]
    await cache.store_samples(samples)
    ranked = [row for row in rows if row.market_cap_rank is not None]
    ranked.sort(key=lambda row: row.market_cap_rank or 0)
    await cache.set_market_page([_market_row_payload(row) for row in ranked])
    await cache.publish_prices(samples)
    await cache.heartbeat("market_poll")
    return len(rows)


def _market_row_payload(row: MarketRow) -> dict[str, Any]:
    return {
        "coin_id": row.coin_id,
        "symbol": row.symbol,
        "name": row.name,
        "image_url": row.image_url,
        "market_cap_rank": row.market_cap_rank,
        "price_usd": str(row.price_usd),
        "market_cap": str(row.market_cap) if row.market_cap is not None else None,
        "volume_24h": str(row.volume_24h) if row.volume_24h is not None else None,
        "pct_change_24h": str(row.pct_change_24h) if row.pct_change_24h is not None else None,
        "sparkline_7d": row.sparkline_7d,
        "sampled_at": row.sampled_at.isoformat(),
    }


async def _upsert_coins(session: AsyncSession, rows: list[MarketRow]) -> None:
    payload = [
        {
            "id": row.coin_id,
            "symbol": row.symbol,
            "name": row.name,
            "image_url": row.image_url,
            "market_cap_rank": row.market_cap_rank,
            "sparkline_7d": row.sparkline_7d,
            "is_tracked": True,
            "updated_at": row.sampled_at,
        }
        for row in rows
    ]
    statement = pg_insert(Coin).values(payload)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[Coin.id],
            set_={
                "symbol": statement.excluded.symbol,
                "name": statement.excluded.name,
                "image_url": statement.excluded.image_url,
                "market_cap_rank": statement.excluded.market_cap_rank,
                "sparkline_7d": statement.excluded.sparkline_7d,
                "updated_at": statement.excluded.updated_at,
            },
        )
    )


async def _insert_snapshots(session: AsyncSession, rows: list[MarketRow]) -> None:
    payload = [
        {
            "coin_id": row.coin_id,
            "ts": row.sampled_at.replace(second=0, microsecond=0),
            "price_usd": row.price_usd,
            "volume_24h": row.volume_24h,
            "market_cap": row.market_cap,
            "pct_change_24h": row.pct_change_24h,
        }
        for row in rows
    ]
    statement = pg_insert(PriceSnapshot).values(payload)
    await session.execute(statement.on_conflict_do_nothing(index_elements=["coin_id", "ts"]))


AGGREGATE_SQL = text(
    """
    insert into ohlc_candles (coin_id, interval, ts, open, high, low, close, is_partial)
    select
        coin_id,
        cast(:interval as candle_interval),
        date_trunc(:unit, ts) as bucket,
        (array_agg(price_usd order by ts asc))[1],
        max(price_usd),
        min(price_usd),
        (array_agg(price_usd order by ts desc))[1],
        date_trunc(:unit, ts) = date_trunc(:unit, now())
    from price_snapshots
    where ts >= :since
    group by coin_id, bucket
    on conflict (coin_id, interval, ts) do update set
        high = greatest(ohlc_candles.high, excluded.high),
        low = least(ohlc_candles.low, excluded.low),
        close = excluded.close,
        is_partial = excluded.is_partial
    """
)


async def aggregate_candles(session: AsyncSession) -> None:
    """Turn the 5-minute snapshots into 1h and 1d candles (D3).

    Only the buckets that can still change are recomputed, so this stays cheap
    no matter how much history has piled up. Gaps caused by a failed poll are
    left as gaps — the candle is simply built from fewer samples and stays
    marked partial while its bucket is the current one.
    """
    now = datetime.now(UTC)
    await session.execute(
        AGGREGATE_SQL,
        {"interval": "1h", "unit": "hour", "since": now - timedelta(hours=3)},
    )
    await session.execute(
        AGGREGATE_SQL,
        {"interval": "1d", "unit": "day", "since": now - timedelta(days=2)},
    )
    await session.commit()
    await cache.heartbeat("candle_aggregator")


async def backfill_coin(session: AsyncSession, source: PriceSource, coin_id: str) -> int:
    """Two upstream calls, once in a coin's lifetime, to fill the chart history."""
    written = 0
    for days, interval, unit in ((365, CandleInterval.d1, "day"), (7, CandleInterval.h1, "hour")):
        points = await source.history(coin_id, days)
        if not points:
            continue
        buckets: dict[datetime, list[Decimal]] = {}
        for point in points:
            bucket = (
                point.ts.replace(minute=0, second=0, microsecond=0)
                if unit == "hour"
                else point.ts.replace(hour=0, minute=0, second=0, microsecond=0)
            )
            buckets.setdefault(bucket, []).append(point.price)
        payload = [
            {
                "coin_id": coin_id,
                "interval": interval,
                "ts": bucket,
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
                "is_partial": False,
            }
            for bucket, prices in sorted(buckets.items())
        ]
        statement = pg_insert(OhlcCandle).values(payload)
        await session.execute(
            statement.on_conflict_do_nothing(index_elements=["coin_id", "interval", "ts"])
        )
        written += len(payload)

    await session.execute(
        text("update coins set backfilled_at = now() where id = :cid"), {"cid": coin_id}
    )
    await session.commit()
    return written


async def market_page(session: AsyncSession, limit: int) -> list[dict[str, Any]]:
    """Served from Redis; falls back to the database so a cold cache is not a 503."""
    cached = await cache.get_market_page()
    if cached:
        return cached[:limit]

    latest = (
        select(
            PriceSnapshot.coin_id,
            func.max(PriceSnapshot.ts).label("ts"),
        )
        .group_by(PriceSnapshot.coin_id)
        .subquery()
    )
    query = (
        select(Coin, PriceSnapshot)
        .join(latest, latest.c.coin_id == Coin.id)
        .join(
            PriceSnapshot,
            (PriceSnapshot.coin_id == latest.c.coin_id) & (PriceSnapshot.ts == latest.c.ts),
        )
        .where(Coin.is_tracked.is_(True))
        .order_by(Coin.market_cap_rank.asc().nullslast())
        .limit(limit)
    )
    rows = (await session.execute(query)).all()
    return [
        {
            "coin_id": coin.id,
            "symbol": coin.symbol,
            "name": coin.name,
            "image_url": coin.image_url,
            "market_cap_rank": coin.market_cap_rank,
            "price_usd": str(snapshot.price_usd),
            "market_cap": str(snapshot.market_cap) if snapshot.market_cap is not None else None,
            "volume_24h": str(snapshot.volume_24h) if snapshot.volume_24h is not None else None,
            "pct_change_24h": (
                str(snapshot.pct_change_24h) if snapshot.pct_change_24h is not None else None
            ),
            "sparkline_7d": coin.sparkline_7d,
            "sampled_at": snapshot.ts.isoformat(),
        }
        for coin, snapshot in rows
    ]


async def get_coin(session: AsyncSession, coin_id: str) -> Coin:
    coin = await session.get(Coin, coin_id)
    if coin is None:
        raise NotFound("این ارز در فهرست پایش‌شده نیست")
    return coin


async def coin_detail(session: AsyncSession, coin_id: str) -> dict[str, Any]:
    coin = await get_coin(session, coin_id)
    snapshot = (
        await session.execute(
            select(PriceSnapshot)
            .where(PriceSnapshot.coin_id == coin_id)
            .order_by(PriceSnapshot.ts.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    live = await cache.latest_price(coin_id)

    price = live[0] if live else (snapshot.price_usd if snapshot else None)
    sampled_at = live[1] if live else (snapshot.ts if snapshot else None)
    return {
        "coin_id": coin.id,
        "symbol": coin.symbol,
        "name": coin.name,
        "image_url": coin.image_url,
        "market_cap_rank": coin.market_cap_rank,
        "price_usd": str(price) if price is not None else None,
        "market_cap": str(snapshot.market_cap) if snapshot and snapshot.market_cap else None,
        "volume_24h": str(snapshot.volume_24h) if snapshot and snapshot.volume_24h else None,
        "pct_change_24h": (
            str(snapshot.pct_change_24h) if snapshot and snapshot.pct_change_24h else None
        ),
        "sparkline_7d": coin.sparkline_7d,
        "sampled_at": sampled_at.isoformat() if sampled_at else None,
    }


async def chart_series(
    session: AsyncSession, coin_id: str, chart_range: ChartRange
) -> dict[str, Any]:
    await get_coin(session, coin_id)
    interval, span = RANGE_PLAN[chart_range]
    since = datetime.now(UTC) - span
    rows = (
        await session.execute(
            select(OhlcCandle)
            .where(
                OhlcCandle.coin_id == coin_id,
                OhlcCandle.interval == interval,
                OhlcCandle.ts >= since,
            )
            .order_by(OhlcCandle.ts.asc())
        )
    ).scalars()
    points = [
        {
            "ts": candle.ts.isoformat(),
            "open": str(candle.open),
            "high": str(candle.high),
            "low": str(candle.low),
            "close": str(candle.close),
        }
        for candle in rows
    ]
    return {"coin_id": coin_id, "range": chart_range, "interval": interval.value, "points": points}


async def search_coins(session: AsyncSession, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Local search only — searching upstream would burn the request budget."""
    pattern = f"%{query.strip().lower()}%"
    rows = (
        await session.execute(
            select(Coin)
            .where(func.lower(Coin.name).like(pattern) | func.lower(Coin.symbol).like(pattern))
            .order_by(Coin.market_cap_rank.asc().nullslast())
            .limit(limit)
        )
    ).scalars()
    return [
        {
            "coin_id": coin.id,
            "symbol": coin.symbol,
            "name": coin.name,
            "image_url": coin.image_url,
            "market_cap_rank": coin.market_cap_rank,
        }
        for coin in rows
    ]

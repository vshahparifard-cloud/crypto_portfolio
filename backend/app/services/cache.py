"""Redis layout. The API never talks to CoinGecko; it reads what lives here.

keys
    price:{coin_id}      json {"p": "104318.42", "ts": "...isoformat"} — latest sample
    hist:{coin_id}       zset score=epoch member="epoch:price" — last ~24h of samples,
                         serves both crossing detection and percentage windows
    market:top50         json list of market rows for the market page
    hb:{worker}          iso timestamp of a worker's last successful run
channel
    ch:prices            json list of {"coin_id","price","ts"} published on each poll
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings

PRICES_CHANNEL = "ch:prices"
HISTORY_RETENTION = timedelta(hours=25)

_client: Redis | None = None


def redis_client() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def _price_key(coin_id: str) -> str:
    return f"price:{coin_id}"


def _hist_key(coin_id: str) -> str:
    return f"hist:{coin_id}"


async def store_samples(samples: list[tuple[str, Decimal, datetime]]) -> None:
    """Write the latest price and append to the rolling history, in one round trip."""
    redis = redis_client()
    cutoff = (datetime.now(UTC) - HISTORY_RETENTION).timestamp()
    async with redis.pipeline(transaction=False) as pipe:
        for coin_id, price, ts in samples:
            epoch = ts.timestamp()
            pipe.set(_price_key(coin_id), json.dumps({"p": str(price), "ts": ts.isoformat()}))
            pipe.zadd(_hist_key(coin_id), {f"{epoch:.0f}:{price}": epoch})
            pipe.zremrangebyscore(_hist_key(coin_id), "-inf", cutoff)
        await pipe.execute()


async def latest_price(coin_id: str) -> tuple[Decimal, datetime] | None:
    raw = await redis_client().get(_price_key(coin_id))
    if not raw:
        return None
    payload = json.loads(raw)
    return Decimal(payload["p"]), datetime.fromisoformat(payload["ts"])


async def latest_prices(coin_ids: list[str]) -> dict[str, tuple[Decimal, datetime]]:
    if not coin_ids:
        return {}
    values = await redis_client().mget([_price_key(cid) for cid in coin_ids])
    out: dict[str, tuple[Decimal, datetime]] = {}
    for coin_id, raw in zip(coin_ids, values, strict=True):
        if raw:
            payload = json.loads(raw)
            out[coin_id] = (Decimal(payload["p"]), datetime.fromisoformat(payload["ts"]))
    return out


async def previous_price(coin_id: str) -> Decimal | None:
    """The sample before the latest one — the other half of a crossing (D8)."""
    entries = await redis_client().zrevrange(_hist_key(coin_id), 1, 1)
    if not entries:
        return None
    return Decimal(entries[0].split(":", 1)[1])


async def price_at_or_before(coin_id: str, moment: datetime) -> Decimal | None:
    """Oldest-newest scan for percentage windows; returns the closest earlier sample."""
    entries = await redis_client().zrevrangebyscore(
        _hist_key(coin_id), max=moment.timestamp(), min="-inf", start=0, num=1
    )
    if not entries:
        return None
    return Decimal(entries[0].split(":", 1)[1])


async def set_market_page(rows: list[dict[str, Any]]) -> None:
    await redis_client().set(
        "market:top50", json.dumps(rows, default=str), ex=settings.poll_interval_seconds * 3
    )


async def get_market_page() -> list[dict[str, Any]] | None:
    raw = await redis_client().get("market:top50")
    return json.loads(raw) if raw else None


async def publish_prices(samples: list[tuple[str, Decimal, datetime]]) -> None:
    payload = [
        {"coin_id": coin_id, "price": str(price), "ts": ts.isoformat()}
        for coin_id, price, ts in samples
    ]
    await redis_client().publish(PRICES_CHANNEL, json.dumps(payload))


async def heartbeat(worker: str) -> None:
    await redis_client().set(f"hb:{worker}", datetime.now(UTC).isoformat())


async def heartbeats() -> dict[str, str | None]:
    redis = redis_client()
    names = ["market_poll", "alert_evaluator", "telegram_sender", "email_sender"]
    values = await redis.mget([f"hb:{name}" for name in names])
    return dict(zip(names, values, strict=True))

from __future__ import annotations

from app.schemas.common import Schema


class MarketRowOut(Schema):
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    market_cap_rank: int | None = None
    price_usd: str | None = None
    market_cap: str | None = None
    volume_24h: str | None = None
    pct_change_24h: str | None = None
    sparkline_7d: list[float] | None = None
    sampled_at: str | None = None


class CoinSearchOut(Schema):
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    market_cap_rank: int | None = None


class CandleOut(Schema):
    ts: str
    open: str
    high: str
    low: str
    close: str


class ChartOut(Schema):
    coin_id: str
    range: str
    interval: str
    points: list[CandleOut]

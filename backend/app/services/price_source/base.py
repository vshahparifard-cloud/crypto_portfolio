"""The seam that keeps D1 reversible: swapping the price provider is one class."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MarketRow:
    coin_id: str
    symbol: str
    name: str
    image_url: str | None
    market_cap_rank: int | None
    price_usd: Decimal
    market_cap: Decimal | None
    volume_24h: Decimal | None
    pct_change_24h: Decimal | None
    sparkline_7d: list[float] | None
    sampled_at: datetime


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    ts: datetime
    price: Decimal


class PriceSource(Protocol):
    async def top_markets(self, limit: int) -> list[MarketRow]:
        """The ordered top-N call. Used daily to establish the tracked set."""

    async def markets_by_ids(self, coin_ids: list[str]) -> list[MarketRow]:
        """One call for an explicit id set — the 5-minute price path.

        Must stay a single request no matter how many ids: looping per coin is
        what blows the monthly budget (GOTCHAS).
        """

    async def history(self, coin_id: str, days: int) -> list[HistoryPoint]:
        """One-time backfill of a coin's chart history."""

"""CoinGecko client (D1).

Budget discipline lives here: `top_markets` is a single request that carries the
whole top-N table, and `history` is only ever called by chart_backfill for a coin
that has no candles yet. Anything that would issue one request per coin belongs
nowhere in this file.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import UpstreamUnavailable
from app.services.price_source.base import HistoryPoint, MarketRow

log = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None


class CoinGeckoSource:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        headers = {"accept": "application/json"}
        if settings.coingecko_demo_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_demo_key
        self._client = client or httpx.AsyncClient(
            base_url=settings.coingecko_base_url, headers=headers, timeout=TIMEOUT
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise UpstreamUnavailable("دسترسی به CoinGecko ممکن نشد") from exc
        if response.status_code == 429:
            raise UpstreamUnavailable("سقف نرخ CoinGecko پر شده است")
        if response.status_code >= 500:
            raise UpstreamUnavailable(f"CoinGecko پاسخ {response.status_code} داد")
        response.raise_for_status()
        return response.json()

    async def top_markets(self, limit: int) -> list[MarketRow]:
        payload = await self._get(
            "/coins/markets",
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": limit,
                "page": 1,
                "sparkline": "true",
                "price_change_percentage": "24h",
            },
        )
        return self._parse_markets(payload)

    async def markets_by_ids(self, coin_ids: list[str]) -> list[MarketRow]:
        """Prices for an explicit set — still exactly one HTTP request."""
        if not coin_ids:
            return []
        payload = await self._get(
            "/coins/markets",
            {
                "vs_currency": "usd",
                "ids": ",".join(sorted(coin_ids)),
                "order": "market_cap_desc",
                "per_page": min(len(coin_ids), 250),
                "page": 1,
                "sparkline": "true",
                "price_change_percentage": "24h",
            },
        )
        return self._parse_markets(payload)

    def _parse_markets(self, payload: Any) -> list[MarketRow]:
        sampled_at = datetime.now(UTC)
        rows: list[MarketRow] = []
        for item in payload:
            price = _decimal(item.get("current_price"))
            if price is None or price <= 0:
                log.warning("skipping coin without a usable price: %s", item.get("id"))
                continue
            sparkline = (item.get("sparkline_in_7d") or {}).get("price")
            rows.append(
                MarketRow(
                    coin_id=str(item["id"]),
                    symbol=str(item.get("symbol", "")).upper(),
                    name=str(item.get("name", "")),
                    image_url=item.get("image"),
                    market_cap_rank=item.get("market_cap_rank"),
                    price_usd=price,
                    market_cap=_decimal(item.get("market_cap")),
                    volume_24h=_decimal(item.get("total_volume")),
                    pct_change_24h=_decimal(item.get("price_change_percentage_24h")),
                    sparkline_7d=[float(p) for p in sparkline[-56:]] if sparkline else None,
                    sampled_at=sampled_at,
                )
            )
        return rows

    async def history(self, coin_id: str, days: int) -> list[HistoryPoint]:
        payload = await self._get(
            f"/coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": days, "interval": "daily" if days > 90 else ""},
        )
        points: list[HistoryPoint] = []
        for epoch_ms, price in payload.get("prices", []):
            value = _decimal(price)
            if value is None:
                continue
            points.append(
                HistoryPoint(ts=datetime.fromtimestamp(epoch_ms / 1000, tz=UTC), price=value)
            )
        return points

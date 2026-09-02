from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.schemas.common import Schema


class HoldingIn(Schema):
    coin_id: str = Field(min_length=1, max_length=80)
    quantity: Decimal = Field(gt=0, max_digits=36, decimal_places=18)
    avg_buy_price: Decimal = Field(ge=0, max_digits=24, decimal_places=8)
    note: str | None = Field(default=None, max_length=200)


class HoldingPatch(Schema):
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=36, decimal_places=18)
    avg_buy_price: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=8)
    note: str | None = Field(default=None, max_length=200)


class HoldingOut(Schema):
    id: str
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    quantity: str
    avg_buy_price: str
    price_usd: str | None = None
    sampled_at: str | None = None
    value_usd: str | None = None
    cost_usd: str
    pnl_usd: str | None = None
    pnl_pct: str | None = None
    pct_change_24h: str | None = None
    note: str | None = None


class AllocationOut(Schema):
    coin_id: str
    symbol: str
    share_pct: str


class SummaryOut(Schema):
    total_value_usd: str
    total_cost_usd: str
    pnl_usd: str
    pnl_pct: str | None = None
    change_24h_usd: str
    holdings_count: int
    allocation: list[AllocationOut]

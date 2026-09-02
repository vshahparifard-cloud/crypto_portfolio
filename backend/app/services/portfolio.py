"""Portfolio valuation. Quantities and prices stay Decimal end to end (D9)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound
from app.db.models import Coin, Holding, Portfolio, PriceSnapshot
from app.services import cache

ZERO = Decimal(0)


async def _owned_holding(
    session: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID
) -> Holding:
    holding = (
        await session.execute(
            select(Holding)
            .join(Portfolio, Portfolio.id == Holding.portfolio_id)
            .where(Holding.id == holding_id, Portfolio.user_id == user_id)
        )
    ).scalar_one_or_none()
    if holding is None:
        raise NotFound("این دارایی در سبد شما نیست")
    return holding


async def _priced_rows(session: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    holdings = (
        await session.execute(
            select(Holding)
            .join(Portfolio, Portfolio.id == Holding.portfolio_id)
            .where(Portfolio.user_id == user_id)
            .order_by(Holding.created_at.asc())
        )
    ).scalars().all()
    if not holdings:
        return []

    coin_ids = [holding.coin_id for holding in holdings]
    live = await cache.latest_prices(coin_ids)
    change_rows = (
        await session.execute(
            select(PriceSnapshot.coin_id, PriceSnapshot.pct_change_24h)
            .where(PriceSnapshot.coin_id.in_(coin_ids))
            .order_by(PriceSnapshot.coin_id, PriceSnapshot.ts.desc())
            .distinct(PriceSnapshot.coin_id)
        )
    ).all()
    changes: dict[str, Decimal | None] = {row[0]: row[1] for row in change_rows}

    rows: list[dict[str, Any]] = []
    for holding in holdings:
        sample = live.get(holding.coin_id)
        price = sample[0] if sample else None
        value = holding.quantity * price if price is not None else None
        cost = holding.quantity * holding.avg_buy_price
        pnl = value - cost if value is not None else None
        rows.append(
            {
                "id": str(holding.id),
                "coin_id": holding.coin_id,
                "symbol": holding.coin.symbol,
                "name": holding.coin.name,
                "image_url": holding.coin.image_url,
                "quantity": str(holding.quantity),
                "avg_buy_price": str(holding.avg_buy_price),
                "price_usd": str(price) if price is not None else None,
                "sampled_at": sample[1].isoformat() if sample else None,
                "value_usd": str(value) if value is not None else None,
                "cost_usd": str(cost),
                "pnl_usd": str(pnl) if pnl is not None else None,
                "pnl_pct": str(pnl / cost * 100) if pnl is not None and cost > 0 else None,
                "pct_change_24h": (
                    str(changes[holding.coin_id]) if changes.get(holding.coin_id) else None
                ),
                "note": holding.note,
            }
        )
    return rows


async def holdings(session: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    return await _priced_rows(session, user_id)


async def summary(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    rows = await _priced_rows(session, user_id)
    total_value = sum((Decimal(r["value_usd"]) for r in rows if r["value_usd"]), ZERO)
    total_cost = sum((Decimal(r["cost_usd"]) for r in rows), ZERO)
    change_24h = ZERO
    for row in rows:
        if row["value_usd"] and row["pct_change_24h"]:
            value = Decimal(row["value_usd"])
            pct = Decimal(row["pct_change_24h"])
            previous = value / (1 + pct / 100) if pct != -100 else ZERO
            change_24h += value - previous

    allocation = [
        {
            "coin_id": row["coin_id"],
            "symbol": row["symbol"],
            "share_pct": str(Decimal(row["value_usd"]) / total_value * 100),
        }
        for row in rows
        if row["value_usd"] and total_value > 0
    ]
    pnl = total_value - total_cost
    return {
        "total_value_usd": str(total_value),
        "total_cost_usd": str(total_cost),
        "pnl_usd": str(pnl),
        "pnl_pct": str(pnl / total_cost * 100) if total_cost > 0 else None,
        "change_24h_usd": str(change_24h),
        "holdings_count": len(rows),
        "allocation": sorted(allocation, key=lambda item: Decimal(item["share_pct"]), reverse=True),
    }


async def add_holding(
    session: AsyncSession,
    user_id: uuid.UUID,
    portfolio_id: uuid.UUID,
    coin_id: str,
    quantity: Decimal,
    avg_buy_price: Decimal,
    note: str | None,
) -> dict[str, Any]:
    if await session.get(Coin, coin_id) is None:
        raise NotFound("این ارز در فهرست پایش‌شده نیست")
    session.add(
        Holding(
            portfolio_id=portfolio_id,
            coin_id=coin_id,
            quantity=quantity,
            avg_buy_price=avg_buy_price,
            note=note,
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("این ارز از قبل در سبد شماست؛ همان ردیف را ویرایش کنید") from exc
    rows = await _priced_rows(session, user_id)
    return next(row for row in rows if row["coin_id"] == coin_id)


async def update_holding(
    session: AsyncSession,
    user_id: uuid.UUID,
    holding_id: uuid.UUID,
    quantity: Decimal | None,
    avg_buy_price: Decimal | None,
    note: str | None,
) -> dict[str, Any]:
    holding = await _owned_holding(session, user_id, holding_id)
    if quantity is not None:
        holding.quantity = quantity
    if avg_buy_price is not None:
        holding.avg_buy_price = avg_buy_price
    if note is not None:
        holding.note = note
    await session.commit()
    rows = await _priced_rows(session, user_id)
    return next(row for row in rows if row["id"] == str(holding_id))


async def delete_holding(session: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID) -> None:
    holding = await _owned_holding(session, user_id, holding_id)
    await session.delete(holding)
    await session.commit()

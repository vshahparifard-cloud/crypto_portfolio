"""Market endpoints. Every read is served from our cache or database (D1)."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.deps import SessionDep
from app.schemas.market import ChartOut, CoinSearchOut, MarketRowOut
from app.services import cache, market

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/coins", response_model=list[MarketRowOut])
async def list_coins(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=250)] = 50,
) -> list[MarketRowOut]:
    rows = await market.market_page(session, limit)
    return [MarketRowOut.model_validate(row) for row in rows]


@router.get("/search", response_model=list[CoinSearchOut])
async def search(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=40)],
) -> list[CoinSearchOut]:
    return [CoinSearchOut.model_validate(row) for row in await market.search_coins(session, q)]


@router.get("/coins/{coin_id}", response_model=MarketRowOut)
async def coin_detail(coin_id: str, session: SessionDep) -> MarketRowOut:
    return MarketRowOut.model_validate(await market.coin_detail(session, coin_id))


@router.get("/coins/{coin_id}/chart", response_model=ChartOut)
async def coin_chart(
    coin_id: str,
    session: SessionDep,
    range: Literal["24h", "7d", "30d", "90d", "1y"] = "7d",
) -> ChartOut:
    return ChartOut.model_validate(await market.chart_series(session, coin_id, range))


@router.get("/stream")
async def price_stream() -> StreamingResponse:
    """Server-sent events fed by the poll worker through Redis pub/sub (D4).

    A heartbeat comment every 15s keeps proxies from closing an idle stream —
    with a 5-minute sampling interval, idle is the normal state.
    """

    async def event_source() -> AsyncIterator[bytes]:
        pubsub = cache.redis_client().pubsub()
        await pubsub.subscribe(cache.PRICES_CHANNEL)
        yield f": interval={settings.poll_interval_seconds}\n\n".encode()
        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0),
                        timeout=20.0,
                    )
                except TimeoutError:
                    message = None
                if message and message.get("data"):
                    payload = json.loads(message["data"])
                    yield f"event: prices\ndata: {json.dumps(payload)}\n\n".encode()
                else:
                    yield b": keep-alive\n\n"
        except asyncio.CancelledError:  # client went away
            raise
        finally:
            await pubsub.unsubscribe(cache.PRICES_CHANNEL)
            await pubsub.close()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

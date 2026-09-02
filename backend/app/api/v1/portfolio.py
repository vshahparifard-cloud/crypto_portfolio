from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import SessionDep, UserDep
from app.schemas.common import Message
from app.schemas.portfolio import HoldingIn, HoldingOut, HoldingPatch, SummaryOut
from app.services import auth as auth_service
from app.services import portfolio as portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=SummaryOut)
async def summary(user: UserDep, session: SessionDep) -> SummaryOut:
    return SummaryOut.model_validate(await portfolio_service.summary(session, user.id))


@router.get("/holdings", response_model=list[HoldingOut])
async def list_holdings(user: UserDep, session: SessionDep) -> list[HoldingOut]:
    rows = await portfolio_service.holdings(session, user.id)
    return [HoldingOut.model_validate(row) for row in rows]


@router.post("/holdings", response_model=HoldingOut, status_code=status.HTTP_201_CREATED)
async def add_holding(payload: HoldingIn, user: UserDep, session: SessionDep) -> HoldingOut:
    portfolio_id = await auth_service.default_portfolio_id(session, user.id)
    row = await portfolio_service.add_holding(
        session,
        user.id,
        portfolio_id,
        payload.coin_id,
        payload.quantity,
        payload.avg_buy_price,
        payload.note,
    )
    return HoldingOut.model_validate(row)


@router.patch("/holdings/{holding_id}", response_model=HoldingOut)
async def update_holding(
    holding_id: uuid.UUID, payload: HoldingPatch, user: UserDep, session: SessionDep
) -> HoldingOut:
    row = await portfolio_service.update_holding(
        session, user.id, holding_id, payload.quantity, payload.avg_buy_price, payload.note
    )
    return HoldingOut.model_validate(row)


@router.delete("/holdings/{holding_id}", response_model=Message)
async def delete_holding(
    holding_id: uuid.UUID, user: UserDep, session: SessionDep
) -> Message:
    await portfolio_service.delete_holding(session, user.id, holding_id)
    return Message(message="دارایی از سبد حذف شد")

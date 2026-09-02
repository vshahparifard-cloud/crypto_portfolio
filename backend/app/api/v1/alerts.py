from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import SessionDep, UserDep
from app.domain.enums import AlertStatus
from app.schemas.alerts import AlertEventOut, AlertIn, AlertOut, AlertPatch
from app.schemas.common import Message
from app.services import alerts as alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    user: UserDep, session: SessionDep, status_filter: AlertStatus | None = None
) -> list[AlertOut]:
    rows = await alert_service.list_alerts(session, user.id, status_filter)
    return [AlertOut.model_validate(row) for row in rows]


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(payload: AlertIn, user: UserDep, session: SessionDep) -> AlertOut:
    row = await alert_service.create_alert(
        session,
        user.id,
        payload.coin_id,
        payload.kind,
        payload.threshold,
        payload.window_minutes,
        payload.cooldown_minutes,
        payload.is_one_shot,
    )
    return AlertOut.model_validate(row)


@router.get("/events", response_model=list[AlertEventOut])
async def list_events(
    user: UserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AlertEventOut]:
    rows = await alert_service.list_events(session, user.id, limit)
    return [AlertEventOut.model_validate(row) for row in rows]


@router.patch("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: uuid.UUID, payload: AlertPatch, user: UserDep, session: SessionDep
) -> AlertOut:
    row = await alert_service.update_alert(
        session,
        user.id,
        alert_id,
        threshold=payload.threshold,
        cooldown_minutes=payload.cooldown_minutes,
        status=payload.status,
        is_one_shot=payload.is_one_shot,
    )
    return AlertOut.model_validate(row)


@router.delete("/{alert_id}", response_model=Message)
async def delete_alert(alert_id: uuid.UUID, user: UserDep, session: SessionDep) -> Message:
    await alert_service.delete_alert(session, user.id, alert_id)
    return Message(message="هشدار حذف شد")

"""Alert CRUD and the evaluator loop that turns price samples into outbox rows.

The decision logic itself lives in `alert_engine` (pure, unit tested). This
module only supplies it with values and writes down what it decided.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, Conflict, NotFound
from app.db.models import Alert, AlertEvent, Coin, User
from app.domain.enums import ALLOWED_PCT_WINDOWS, AlertKind, AlertStatus, DeliveryState
from app.services import cache
from app.services.alert_engine import (
    AlertSpec,
    dedupe_bucket,
    in_quiet_hours,
    is_cooling,
    should_fire,
)

log = logging.getLogger(__name__)
PCT_KINDS = (AlertKind.pct_up, AlertKind.pct_down)


async def _owned(session: AsyncSession, user_id: uuid.UUID, alert_id: uuid.UUID) -> Alert:
    alert = (
        await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        )
    ).scalar_one_or_none()
    if alert is None:
        raise NotFound("این هشدار یافت نشد")
    return alert


def _serialize(alert: Alert, current_price: Decimal | None) -> dict[str, Any]:
    return {
        "id": str(alert.id),
        "coin_id": alert.coin_id,
        "symbol": alert.coin.symbol,
        "name": alert.coin.name,
        "image_url": alert.coin.image_url,
        "kind": alert.kind.value,
        "threshold": str(alert.threshold),
        "window_minutes": alert.window_minutes,
        "status": alert.status.value,
        "cooldown_minutes": alert.cooldown_minutes,
        "is_one_shot": alert.is_one_shot,
        "last_triggered_at": (
            alert.last_triggered_at.isoformat() if alert.last_triggered_at else None
        ),
        "current_price": str(current_price) if current_price is not None else None,
        "created_at": alert.created_at.isoformat(),
    }


async def _decorate(session: AsyncSession, alerts: list[Alert]) -> list[dict[str, Any]]:
    prices = await cache.latest_prices([alert.coin_id for alert in alerts])
    return [
        _serialize(alert, prices.get(alert.coin_id, (None, None))[0])  # type: ignore[arg-type]
        for alert in alerts
    ]


async def list_alerts(
    session: AsyncSession, user_id: uuid.UUID, status: AlertStatus | None = None
) -> list[dict[str, Any]]:
    query = select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.desc())
    if status is not None:
        query = query.where(Alert.status == status)
    alerts = list((await session.execute(query)).scalars().all())
    return await _decorate(session, alerts)


async def create_alert(
    session: AsyncSession,
    user_id: uuid.UUID,
    coin_id: str,
    kind: AlertKind,
    threshold: Decimal,
    window_minutes: int | None,
    cooldown_minutes: int,
    is_one_shot: bool,
) -> dict[str, Any]:
    if await session.get(Coin, coin_id) is None:
        raise NotFound("این ارز در فهرست پایش‌شده نیست")

    active = (
        await session.execute(
            select(func.count())
            .select_from(Alert)
            .where(Alert.user_id == user_id, Alert.status == AlertStatus.active)
        )
    ).scalar_one()
    if active >= settings.max_active_alerts:
        raise Conflict(
            f"سقف {settings.max_active_alerts} هشدار فعال پر است؛ یکی را حذف یا متوقف کنید"
        )

    if kind in PCT_KINDS:
        if window_minutes not in ALLOWED_PCT_WINDOWS:
            raise AppError(
                "پنجره هشدار درصدی باید ۱۵، ۳۰ یا ۶۰ دقیقه باشد",
                {"allowed": list(ALLOWED_PCT_WINDOWS)},
            )
        if threshold <= 0 or threshold > 100:
            raise AppError("درصد باید بین ۰ و ۱۰۰ باشد")
    else:
        window_minutes = None
        sample = await cache.latest_price(coin_id)
        if sample is not None:
            price = sample[0]
            if kind is AlertKind.price_above and threshold <= price:
                raise AppError(
                    "حد بالا باید بیشتر از قیمت فعلی باشد، وگرنه هرگز عبوری رخ نمی‌دهد",
                    {"current_price": str(price)},
                )
            if kind is AlertKind.price_below and threshold >= price:
                raise AppError(
                    "حد پایین باید کمتر از قیمت فعلی باشد، وگرنه هرگز عبوری رخ نمی‌دهد",
                    {"current_price": str(price)},
                )

    alert = Alert(
        user_id=user_id,
        coin_id=coin_id,
        kind=kind,
        threshold=threshold,
        window_minutes=window_minutes,
        cooldown_minutes=cooldown_minutes,
        is_one_shot=is_one_shot,
        status=AlertStatus.active,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert, attribute_names=["coin", "created_at"])
    return (await _decorate(session, [alert]))[0]


async def update_alert(
    session: AsyncSession,
    user_id: uuid.UUID,
    alert_id: uuid.UUID,
    *,
    threshold: Decimal | None = None,
    cooldown_minutes: int | None = None,
    status: AlertStatus | None = None,
    is_one_shot: bool | None = None,
) -> dict[str, Any]:
    alert = await _owned(session, user_id, alert_id)
    if threshold is not None:
        alert.threshold = threshold
    if cooldown_minutes is not None:
        alert.cooldown_minutes = cooldown_minutes
    if is_one_shot is not None:
        alert.is_one_shot = is_one_shot
    if status is not None:
        if status is AlertStatus.active:
            alert.last_triggered_at = None  # a re-armed alert starts clean
        alert.status = status
    await session.commit()
    return (await _decorate(session, [alert]))[0]


async def delete_alert(session: AsyncSession, user_id: uuid.UUID, alert_id: uuid.UUID) -> None:
    alert = await _owned(session, user_id, alert_id)
    await session.delete(alert)
    await session.commit()


async def list_events(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(AlertEvent)
            .join(Alert, Alert.id == AlertEvent.alert_id)
            .where(Alert.user_id == user_id)
            .order_by(AlertEvent.triggered_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(event.id),
            "alert_id": str(event.alert_id),
            "coin_id": event.alert.coin_id,
            "symbol": event.alert.coin.symbol,
            "kind": event.alert.kind.value,
            "threshold": str(event.alert.threshold),
            "price_at_trigger": str(event.price_at_trigger),
            "triggered_at": event.triggered_at.isoformat(),
            "sampled_at": event.sampled_at.isoformat(),
            "delivery_state": event.delivery_state.value,
            "attempts": event.attempts,
        }
        for event in rows
    ]


def _quiet_delay(user: User, now: datetime) -> datetime:
    """Delivery time that respects the user's quiet hours; the event is recorded now."""
    try:
        local = now.astimezone(ZoneInfo(user.timezone))
    except (ZoneInfoNotFoundError, ValueError):
        return now
    if not in_quiet_hours(local.hour, user.quiet_from_hour, user.quiet_to_hour):
        return now
    target = local.replace(minute=0, second=0, microsecond=0)
    while in_quiet_hours(target.hour, user.quiet_from_hour, user.quiet_to_hour):
        target += timedelta(hours=1)
    return target.astimezone(UTC)


async def evaluate_active_alerts(session: AsyncSession) -> int:
    """Compare the newest sample against every active alert. Returns events created."""
    now = datetime.now(UTC)
    alerts = (
        await session.execute(
            select(Alert, User)
            .join(User, User.id == Alert.user_id)
            .where(Alert.status == AlertStatus.active, User.is_active.is_(True))
        )
    ).all()
    if not alerts:
        await cache.heartbeat("alert_evaluator")
        return 0

    coin_ids = sorted({alert.coin_id for alert, _ in alerts})
    latest = await cache.latest_prices(coin_ids)
    previous = {coin_id: await cache.previous_price(coin_id) for coin_id in coin_ids}

    created = 0
    for alert, user in alerts:
        sample = latest.get(alert.coin_id)
        if sample is None:
            continue
        current_price, sampled_at = sample

        if alert.expires_at is not None and alert.expires_at < now:
            alert.status = AlertStatus.expired
            continue
        if is_cooling(alert.last_triggered_at, alert.cooldown_minutes, now):
            continue

        window_base: Decimal | None = None
        if alert.kind in PCT_KINDS and alert.window_minutes:
            window_base = await cache.price_at_or_before(
                alert.coin_id, sampled_at - timedelta(minutes=alert.window_minutes)
            )

        spec = AlertSpec(
            kind=alert.kind, threshold=alert.threshold, window_minutes=alert.window_minutes
        )
        if not should_fire(spec, previous.get(alert.coin_id), current_price, window_base):
            continue

        statement = pg_insert(AlertEvent).values(
            id=uuid.uuid4(),
            alert_id=alert.id,
            dedupe_bucket=dedupe_bucket(sampled_at, alert.cooldown_minutes),
            triggered_at=now,
            sampled_at=sampled_at,
            price_at_trigger=current_price,
            delivery_state=DeliveryState.pending,
            attempts=0,
            next_retry_at=_quiet_delay(user, now),
        )
        result = await session.execute(
            statement.on_conflict_do_nothing(constraint="uq_alert_events_dedupe").returning(
                AlertEvent.id
            )
        )
        if result.scalar_one_or_none() is None:
            continue  # another evaluator already recorded this crossing

        created += 1
        alert.last_triggered_at = now
        alert.status = AlertStatus.paused if alert.is_one_shot else AlertStatus.cooling
        log.info(
            "alert fired id=%s coin=%s kind=%s price=%s",
            alert.id,
            alert.coin_id,
            alert.kind.value,
            current_price,
        )

    await session.commit()
    await _reactivate_cooled(session, now)
    await cache.heartbeat("alert_evaluator")
    return created


async def _reactivate_cooled(session: AsyncSession, now: datetime) -> None:
    cooling = (
        await session.execute(select(Alert).where(Alert.status == AlertStatus.cooling))
    ).scalars().all()
    for alert in cooling:
        if not is_cooling(alert.last_triggered_at, alert.cooldown_minutes, now):
            alert.status = AlertStatus.active
    if cooling:
        await session.commit()

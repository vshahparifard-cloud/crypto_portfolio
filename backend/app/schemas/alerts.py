from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.domain.enums import AlertKind, AlertStatus
from app.schemas.common import Schema


class AlertIn(Schema):
    coin_id: str = Field(min_length=1, max_length=80)
    kind: AlertKind
    threshold: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    window_minutes: int | None = None
    cooldown_minutes: int = Field(default=60, ge=5, le=1440)
    is_one_shot: bool = False


class AlertPatch(Schema):
    threshold: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8)
    cooldown_minutes: int | None = Field(default=None, ge=5, le=1440)
    status: AlertStatus | None = None
    is_one_shot: bool | None = None


class AlertOut(Schema):
    id: str
    coin_id: str
    symbol: str
    name: str
    image_url: str | None = None
    kind: str
    threshold: str
    window_minutes: int | None = None
    status: str
    cooldown_minutes: int
    is_one_shot: bool
    last_triggered_at: str | None = None
    current_price: str | None = None
    created_at: str


class AlertEventOut(Schema):
    id: str
    alert_id: str
    coin_id: str
    symbol: str
    kind: str
    threshold: str
    price_at_trigger: str
    triggered_at: str
    sampled_at: str
    delivery_state: str
    attempts: int

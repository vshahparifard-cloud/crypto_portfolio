"""Domain vocabulary, deliberately free of any framework import.

Keeping the enums here is what lets `app.services.alert_engine` — the riskiest
logic in the product — be imported and unit-tested without SQLAlchemy, a
database, or a running stack.
"""
from __future__ import annotations

from enum import StrEnum


class AlertKind(StrEnum):
    price_above = "price_above"
    price_below = "price_below"
    pct_up = "pct_up"
    pct_down = "pct_down"


class AlertStatus(StrEnum):
    active = "active"
    cooling = "cooling"
    paused = "paused"
    expired = "expired"


class DeliveryState(StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    dead = "dead"


class EmailPurpose(StrEnum):
    verify = "verify"
    reset = "reset"


class CandleInterval(StrEnum):
    h1 = "1h"
    d1 = "1d"


ALLOWED_PCT_WINDOWS = (15, 30, 60)

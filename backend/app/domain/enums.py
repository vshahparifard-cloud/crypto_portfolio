"""Domain vocabulary, deliberately free of any framework import.

Keeping the enums here is what lets `app.services.alert_engine` — the riskiest
logic in the product — be imported and unit-tested without SQLAlchemy, a
database, or a running stack.
"""
from __future__ import annotations

import enum


class AlertKind(str, enum.Enum):
    price_above = "price_above"
    price_below = "price_below"
    pct_up = "pct_up"
    pct_down = "pct_down"


class AlertStatus(str, enum.Enum):
    active = "active"
    cooling = "cooling"
    paused = "paused"
    expired = "expired"


class DeliveryState(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    dead = "dead"


class EmailPurpose(str, enum.Enum):
    verify = "verify"
    reset = "reset"


class CandleInterval(str, enum.Enum):
    h1 = "1h"
    d1 = "1d"


ALLOWED_PCT_WINDOWS = (15, 30, 60)

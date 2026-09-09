"""Pure alert logic — no database, no network, no clock of its own.

This module is the highest-bug-risk part of the product, so it is written as
plain functions over values and covered by unit tests (tests/test_alert_engine.py).

The rule that keeps users from being spammed (D8): an alert fires on the
*crossing* of a threshold, never on the mere fact that the price sits beyond it.
Sitting in the target zone produces exactly one alert, on entry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.enums import AlertKind

HUNDRED = Decimal(100)


@dataclass(frozen=True, slots=True)
class AlertSpec:
    kind: AlertKind
    threshold: Decimal
    window_minutes: int | None = None


def pct_change(base: Decimal, current: Decimal) -> Decimal:
    """Percentage move from `base` to `current`. `base` must be positive."""
    if base <= 0:
        raise ValueError("base price must be positive")
    return (current - base) / base * HUNDRED


def crosses_up(threshold: Decimal, previous: Decimal, current: Decimal) -> bool:
    return previous < threshold <= current


def crosses_down(threshold: Decimal, previous: Decimal, current: Decimal) -> bool:
    return previous > threshold >= current


def should_fire(
    spec: AlertSpec,
    previous_price: Decimal | None,
    current_price: Decimal,
    window_base_price: Decimal | None = None,
) -> bool:
    """Decide whether this sample crosses the alert's threshold.

    `previous_price` is the sample before `current_price`. Without it there is no
    crossing to observe yet, so a fresh alert stays quiet until it has seen two
    samples — that is deliberate: it stops an alert created below its own target
    from firing immediately.

    For percentage alerts, `window_base_price` is the price one window ago. The
    same base is used for both ends of the comparison; it drifts by a single
    sample, which is irrelevant next to the 5-minute sampling interval itself.
    """
    if previous_price is None or previous_price <= 0 or current_price <= 0:
        return False

    if spec.kind is AlertKind.price_above:
        return crosses_up(spec.threshold, previous_price, current_price)
    if spec.kind is AlertKind.price_below:
        return crosses_down(spec.threshold, previous_price, current_price)

    if window_base_price is None or window_base_price <= 0:
        return False
    previous_pct = pct_change(window_base_price, previous_price)
    current_pct = pct_change(window_base_price, current_price)

    if spec.kind is AlertKind.pct_up:
        return crosses_up(spec.threshold, previous_pct, current_pct)
    if spec.kind is AlertKind.pct_down:
        return crosses_down(-spec.threshold, previous_pct, current_pct)
    return False


def holds_now(
    spec: AlertSpec,
    current_price: Decimal,
    window_base_price: Decimal | None = None,
) -> bool:
    """Is the condition already true at this instant, crossing or not?

    `should_fire` deliberately needs two samples so a price sitting inside the
    target zone cannot re-alert. That is right for the steady state and wrong at
    the moment an alert is armed: an alert created while its condition is
    already satisfied should say so immediately instead of waiting for the price
    to leave and come back. This predicate answers that one question.
    """
    if current_price <= 0:
        return False
    if spec.kind is AlertKind.price_above:
        return current_price >= spec.threshold
    if spec.kind is AlertKind.price_below:
        return current_price <= spec.threshold
    if window_base_price is None or window_base_price <= 0:
        return False
    move = pct_change(window_base_price, current_price)
    if spec.kind is AlertKind.pct_up:
        return move >= spec.threshold
    if spec.kind is AlertKind.pct_down:
        return move <= -spec.threshold
    return False


def is_cooling(last_triggered_at: datetime | None, cooldown_minutes: int, now: datetime) -> bool:
    if last_triggered_at is None:
        return False
    return now < last_triggered_at + timedelta(minutes=cooldown_minutes)


def in_quiet_hours(local_hour: int, quiet_from: int | None, quiet_to: int | None) -> bool:
    """Quiet hours may wrap midnight (23 -> 7). Delivery waits; the event is still recorded."""
    if quiet_from is None or quiet_to is None or quiet_from == quiet_to:
        return False
    if quiet_from < quiet_to:
        return quiet_from <= local_hour < quiet_to
    return local_hour >= quiet_from or local_hour < quiet_to


def dedupe_bucket(sampled_at: datetime, cooldown_minutes: int) -> str:
    """Two evaluator runs inside one cooldown window produce the same bucket.

    Combined with the unique index on (alert_id, dedupe_bucket) this makes a
    duplicate telegram message impossible even if two evaluators race.
    """
    window = max(cooldown_minutes, 1) * 60
    return str(int(sampled_at.timestamp() // window))

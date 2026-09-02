from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.enums import AlertKind
from app.services.alert_engine import (
    AlertSpec,
    dedupe_bucket,
    in_quiet_hours,
    is_cooling,
    pct_change,
    should_fire,
)

D = Decimal


def spec(kind: AlertKind, threshold: str, window: int | None = None) -> AlertSpec:
    return AlertSpec(kind=kind, threshold=D(threshold), window_minutes=window)


class TestPriceCrossing:
    def test_fires_when_price_crosses_up_through_target(self):
        assert should_fire(spec(AlertKind.price_above, "110000"), D("109000"), D("110500"))

    def test_exact_threshold_counts_as_crossed(self):
        assert should_fire(spec(AlertKind.price_above, "110000"), D("109000"), D("110000"))

    def test_silent_while_price_stays_above_target(self):
        # the crash of every naive implementation: this must NOT fire again
        assert not should_fire(spec(AlertKind.price_above, "110000"), D("111000"), D("112000"))

    def test_silent_when_price_never_reaches_target(self):
        assert not should_fire(spec(AlertKind.price_above, "110000"), D("104000"), D("105000"))

    def test_fires_when_price_falls_through_stop(self):
        assert should_fire(spec(AlertKind.price_below, "95000"), D("96000"), D("94500"))

    def test_silent_while_price_stays_below_stop(self):
        assert not should_fire(spec(AlertKind.price_below, "95000"), D("94000"), D("93000"))

    def test_first_ever_sample_is_quiet(self):
        assert not should_fire(spec(AlertKind.price_above, "110000"), None, D("120000"))

    def test_non_positive_prices_are_ignored(self):
        assert not should_fire(spec(AlertKind.price_below, "95000"), D("0"), D("0"))


class TestPercentageWindow:
    def test_fires_on_sudden_drop_through_threshold(self):
        # base 200 -> -5% target; 192 is -4%, 188 is -6%
        assert should_fire(
            spec(AlertKind.pct_down, "5", 15), D("192"), D("188"), window_base_price=D("200")
        )

    def test_silent_while_drop_persists(self):
        assert not should_fire(
            spec(AlertKind.pct_down, "5", 15), D("188"), D("186"), window_base_price=D("200")
        )

    def test_fires_on_sudden_pump_through_threshold(self):
        assert should_fire(
            spec(AlertKind.pct_up, "5", 15), D("204"), D("212"), window_base_price=D("200")
        )

    def test_without_a_window_base_nothing_fires(self):
        assert not should_fire(spec(AlertKind.pct_down, "5", 15), D("192"), D("100"))

    def test_pct_change_math(self):
        assert pct_change(D("200"), D("188")) == D("-6")
        assert pct_change(D("100"), D("125")) == D("25")

    def test_pct_change_rejects_zero_base(self):
        with pytest.raises(ValueError):
            pct_change(D("0"), D("1"))


class TestCooldownAndQuietHours:
    def test_inside_cooldown(self):
        now = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        assert is_cooling(now - timedelta(minutes=30), 60, now)

    def test_cooldown_expired(self):
        now = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        assert not is_cooling(now - timedelta(minutes=61), 60, now)

    def test_never_triggered_is_not_cooling(self):
        assert not is_cooling(None, 60, datetime(2026, 9, 2, 12, 0, tzinfo=UTC))

    def test_quiet_hours_within_a_day(self):
        assert in_quiet_hours(2, 1, 7)
        assert not in_quiet_hours(9, 1, 7)

    def test_quiet_hours_wrapping_midnight(self):
        assert in_quiet_hours(23, 23, 7)
        assert in_quiet_hours(3, 23, 7)
        assert not in_quiet_hours(12, 23, 7)

    def test_quiet_hours_unset(self):
        assert not in_quiet_hours(3, None, None)


class TestDedupeBucket:
    def test_same_bucket_inside_one_cooldown_window(self):
        first = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        second = datetime(2026, 9, 2, 12, 5, tzinfo=UTC)
        assert dedupe_bucket(first, 60) == dedupe_bucket(second, 60)

    def test_different_bucket_after_the_window(self):
        first = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        later = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)
        assert dedupe_bucket(first, 60) != dedupe_bucket(later, 60)

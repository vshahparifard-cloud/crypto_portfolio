"""End-to-end probe over a live stack: price pipeline -> alert -> outbox delivery.

Run it against a running compose stack (`make e2e`). Unlike the unit tests it
talks to the real database, Redis, SMTP and CoinGecko, so it proves the wiring
that pure tests cannot: enum round-trips, the aggregation SQL, the outbox
bookkeeping and the email link.

It writes to the database (one throwaway user per run) — development only.
CoinGecko will rate-limit repeated runs without a demo key; that surfaces as
UpstreamUnavailable, which is the client behaving correctly.
"""
import asyncio
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.db.models import Alert, AlertEvent, Coin, EmailOutbox, EmailToken, OhlcCandle, User
from app.db.session import SessionFactory, engine
from app.domain.enums import AlertKind, DeliveryState
from app.services import alerts as alert_service
from app.services import auth as auth_service
from app.services import cache
from app.services import market as market_service
from app.services import portfolio as portfolio_service
from app.services.price_source.coingecko import CoinGeckoSource
from app.workers import tasks

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


async def main() -> int:
    source = CoinGeckoSource()
    email = f"probe+{int(datetime.now(UTC).timestamp())}@example.com"
    password = "correct-horse-battery"

    async with SessionFactory() as session:
        # --- market pipeline -------------------------------------------------
        tracked = await market_service.sync_top_list(session, source, 50)
        check("sync_top_list stores the tracked top-50", tracked >= 40, f"{tracked} coins")

        sampled = await market_service.poll_prices(session, source, 50)
        check("poll_prices samples every tracked coin", sampled >= 40, f"{sampled} coins")

        await market_service.aggregate_candles(session)
        candles = (await session.execute(select(func.count()).select_from(OhlcCandle))).scalar_one()
        check("candles aggregated from our own snapshots", candles > 0, f"{candles} candles")

        page = await market_service.market_page(session, 5)
        check("market page has priced rows", len(page) == 5 and page[0]["price_usd"], page[0]["symbol"])

        coin_id = page[0]["coin_id"]
        chart = await market_service.chart_series(session, coin_id, "24h")
        check("chart endpoint returns points", len(chart["points"]) > 0, f"{len(chart['points'])} points")

        found = await market_service.search_coins(session, "bit")
        check("local search works without an upstream call", len(found) > 0, f"{len(found)} hits")

        written = await market_service.backfill_coin(session, source, coin_id)
        history = (
            await session.execute(
                select(func.count()).select_from(OhlcCandle).where(OhlcCandle.coin_id == coin_id)
            )
        ).scalar_one()
        check("chart_backfill fills a real history", written > 300 and history > 300, f"{history} candles")
        year = await market_service.chart_series(session, coin_id, "1y")
        check("1y chart is served from candles", len(year["points"]) > 300, f"{len(year['points'])} points")

        # --- registration + email verification -------------------------------
        user = await auth_service.register(session, email, password)
        outbox = (
            await session.execute(select(EmailOutbox).where(EmailOutbox.user_id == user.id))
        ).scalar_one()
        check("registration queues a verification email", outbox.delivery_state == DeliveryState.pending)
        check("user starts unverified", user.is_verified is False)

        try:
            await auth_service.authenticate(session, email, password)
            check("login is blocked before verification", False, "login succeeded")
        except Exception as exc:
            check("login is blocked before verification", type(exc).__name__ == "EmailNotVerified", type(exc).__name__)

        sent = await tasks.dispatch_emails({})
        await session.refresh(outbox)
        check("email_sender delivers to smtp", sent == 1 and outbox.delivery_state == DeliveryState.sent, outbox.error or "")

        token = re.search(r'token=([A-Za-z0-9_\-]+)', outbox.body_html)
        check("verification link carries a token", token is not None)
        await auth_service.verify_email(session, token.group(1))
        await session.refresh(user)
        check("token verifies the account", user.is_verified is True)
        used = (await session.execute(select(EmailToken).where(EmailToken.user_id == user.id))).scalar_one()
        check("verification token is single use", used.used_at is not None)

        logged_in = await auth_service.authenticate(session, email, password)
        access, expires_in, refresh = await auth_service.issue_tokens(session, logged_in)
        check("login issues tokens after verification", bool(access) and expires_in > 0)
        rotated = await auth_service.rotate_refresh(session, refresh)
        check("refresh token rotates to a new value", rotated[2] != refresh)
        try:
            await auth_service.rotate_refresh(session, refresh)
            check("the used refresh token is dead", False, "replay accepted")
        except Exception as exc:
            check("the used refresh token is dead", type(exc).__name__ == "Unauthorized", type(exc).__name__)

        # --- portfolio -------------------------------------------------------
        portfolio_id = await auth_service.default_portfolio_id(session, user.id)
        price = Decimal(page[0]["price_usd"])
        await portfolio_service.add_holding(
            session, user.id, portfolio_id, coin_id, Decimal("2.5"), price / 2, None
        )
        summary = await portfolio_service.summary(session, user.id)
        check(
            "portfolio values the holding and shows profit",
            Decimal(summary["total_value_usd"]) > 0 and Decimal(summary["pnl_usd"]) > 0,
            f"value={summary['total_value_usd'][:12]} pnl%={str(summary['pnl_pct'])[:6]}",
        )

        # --- alert engine over the real database ------------------------------
        threshold = (price * Decimal("1.02")).quantize(Decimal("0.00000001"))
        created = await alert_service.create_alert(
            session, user.id, coin_id, AlertKind.price_above, threshold, None, 60, False
        )
        check("alert created", created["status"] == "active", f"threshold={created['threshold'][:12]}")

        try:
            await alert_service.create_alert(
                session, user.id, coin_id, AlertKind.price_above, price / 2, None, 60, False
            )
            check("threshold below current price is rejected", False, "accepted")
        except Exception as exc:
            check("threshold below current price is rejected", type(exc).__name__ == "AppError", type(exc).__name__)

        now = datetime.now(UTC)
        await cache.store_samples([(coin_id, threshold - Decimal("1"), now - timedelta(minutes=5))])
        await cache.store_samples([(coin_id, threshold + Decimal("1"), now)])
        fired = await alert_service.evaluate_active_alerts(session)
        check("crossing the threshold fires exactly one alert", fired == 1, f"fired={fired}")

        again = await alert_service.evaluate_active_alerts(session)
        check("staying above the threshold fires nothing more", again == 0, f"fired={again}")

        event = (
            await session.execute(
                select(AlertEvent).join(Alert).where(Alert.user_id == user.id)
            )
        ).scalar_one()
        check("event recorded with the sampled price", event.price_at_trigger > threshold)

        delivered = await tasks.dispatch_alerts({})
        await session.refresh(event)
        check(
            "unlinked telegram marks the event dead instead of retrying forever",
            delivered == 0 and event.delivery_state == DeliveryState.dead,
            (event.error or "")[:60],
        )

        alert_row = await session.get(Alert, created["id"])
        check("alert moved to cooling after firing", alert_row.status.value == "cooling", alert_row.status.value)

        events = await alert_service.list_events(session, user.id)
        check("event history is readable", len(events) == 1, events[0]["delivery_state"])

        # --- retention -------------------------------------------------------
        await tasks.prune_old_data({})
        check("retention job runs", True)

        coins = (await session.execute(select(func.count()).select_from(Coin))).scalar_one()
        users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        print(f"\ndatabase now holds {coins} coins, {users} user(s), {candles} candles")

    await source.aclose()
    await cache.close_redis()
    await engine.dispose()

    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

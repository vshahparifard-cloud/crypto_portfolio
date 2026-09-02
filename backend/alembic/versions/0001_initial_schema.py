"""initial schema: users, auth/email tokens, coins, prices, portfolio, alerts

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels = None
depends_on = None

PRICE = sa.Numeric(24, 8)
QTY = sa.Numeric(36, 18)

alert_kind = postgresql.ENUM(
    "price_above", "price_below", "pct_up", "pct_down", name="alert_kind", create_type=False
)
alert_status = postgresql.ENUM(
    "active", "cooling", "paused", "expired", name="alert_status", create_type=False
)
delivery_state = postgresql.ENUM(
    "pending", "sent", "failed", "dead", name="delivery_state", create_type=False
)
email_purpose = postgresql.ENUM("verify", "reset", name="email_purpose", create_type=False)
candle_interval = postgresql.ENUM("1h", "1d", name="candle_interval", create_type=False)


def upgrade() -> None:
    op.execute("create type alert_kind as enum ('price_above','price_below','pct_up','pct_down')")
    op.execute("create type alert_status as enum ('active','cooling','paused','expired')")
    op.execute("create type delivery_state as enum ('pending','sent','failed','dead')")
    op.execute("create type email_purpose as enum ('verify','reset')")
    op.execute("create type candle_interval as enum ('1h','1d')")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("telegram_linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Tehran"),
        sa.Column("quiet_from_hour", sa.Integer(), nullable=True),
        sa.Column("quiet_to_hour", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "refresh_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "email_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purpose", email_purpose, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("to_email", sa.String(320), nullable=False),
        sa.Column("kind", email_purpose, nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("delivery_state", delivery_state, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_email_outbox_user_id", "email_outbox", ["user_id"])
    op.create_index(
        "ix_email_outbox_undelivered",
        "email_outbox",
        ["next_retry_at"],
        postgresql_where=sa.text("delivery_state in ('pending','failed')"),
    )

    op.create_table(
        "telegram_link_tokens",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"])

    op.create_table(
        "coins",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("symbol", sa.String(24), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("market_cap_rank", sa.Integer(), nullable=True),
        sa.Column("sparkline_7d", postgresql.JSONB(), nullable=True),
        sa.Column("is_tracked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("backfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_coins_symbol", "coins", ["symbol"])
    op.create_index("ix_coins_rank", "coins", ["market_cap_rank"])
    op.create_index("ix_coins_tracked", "coins", ["is_tracked"])

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])

    op.create_table(
        "holdings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "portfolio_id",
            sa.Uuid(),
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("coin_id", sa.String(80), sa.ForeignKey("coins.id"), nullable=False),
        sa.Column("quantity", QTY, nullable=False),
        sa.Column("avg_buy_price", PRICE, nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("portfolio_id", "coin_id", name="uq_holdings_portfolio_coin"),
        sa.CheckConstraint("quantity > 0", name="ck_holdings_qty_positive"),
        sa.CheckConstraint("avg_buy_price >= 0", name="ck_holdings_price_non_negative"),
    )
    op.create_index("ix_holdings_portfolio_id", "holdings", ["portfolio_id"])
    op.create_index("ix_holdings_coin_id", "holdings", ["coin_id"])

    op.create_table(
        "price_snapshots",
        sa.Column("coin_id", sa.String(80), sa.ForeignKey("coins.id"), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("price_usd", PRICE, nullable=False),
        sa.Column("volume_24h", sa.Numeric(30, 2), nullable=True),
        sa.Column("market_cap", sa.Numeric(30, 2), nullable=True),
        sa.Column("pct_change_24h", sa.Numeric(12, 4), nullable=True),
    )
    op.create_index("ix_snapshots_coin_ts", "price_snapshots", ["coin_id", "ts"])

    op.create_table(
        "ohlc_candles",
        sa.Column("coin_id", sa.String(80), sa.ForeignKey("coins.id"), primary_key=True),
        sa.Column("interval", candle_interval, primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("open", PRICE, nullable=False),
        sa.Column("high", PRICE, nullable=False),
        sa.Column("low", PRICE, nullable=False),
        sa.Column("close", PRICE, nullable=False),
        sa.Column("is_partial", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_candles_lookup", "ohlc_candles", ["coin_id", "interval", "ts"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("coin_id", sa.String(80), sa.ForeignKey("coins.id"), nullable=False),
        sa.Column("kind", alert_kind, nullable=False),
        sa.Column("threshold", PRICE, nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=True),
        sa.Column("status", alert_status, nullable=False, server_default="active"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_one_shot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("threshold > 0", name="ck_alerts_threshold_positive"),
        sa.CheckConstraint(
            "window_minutes is null or window_minutes in (15, 30, 60)",
            name="ck_alerts_window_allowed",
        ),
    )
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
    op.create_index("ix_alerts_coin_id", "alerts", ["coin_id"])
    op.create_index("ix_alerts_status_coin", "alerts", ["status", "coin_id"])

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "alert_id", sa.Uuid(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("dedupe_bucket", sa.String(40), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_at_trigger", PRICE, nullable=False),
        sa.Column("delivery_state", delivery_state, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("alert_id", "dedupe_bucket", name="uq_alert_events_dedupe"),
    )
    op.create_index("ix_alert_events_alert_id", "alert_events", ["alert_id"])
    op.create_index(
        "ix_alert_events_undelivered",
        "alert_events",
        ["next_retry_at"],
        postgresql_where=sa.text("delivery_state in ('pending','failed')"),
    )


def downgrade() -> None:
    for table in (
        "alert_events",
        "alerts",
        "ohlc_candles",
        "price_snapshots",
        "holdings",
        "portfolios",
        "coins",
        "telegram_link_tokens",
        "email_outbox",
        "email_tokens",
        "refresh_tokens",
        "users",
    ):
        op.drop_table(table)
    for enum_name in (
        "candle_interval",
        "email_purpose",
        "delivery_state",
        "alert_status",
        "alert_kind",
    ):
        op.execute(f"drop type if exists {enum_name}")

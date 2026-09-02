"""Every table in the system. Schema of record: docs/PROJECT_STATE.md > DB.

Money and quantities are Numeric, never float (D9). Timestamps are timezone
aware and stored in UTC.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import (
    AlertKind,
    AlertStatus,
    CandleInterval,
    DeliveryState,
    EmailPurpose,
)

__all__ = [
    "Alert",
    "AlertEvent",
    "AlertKind",
    "AlertStatus",
    "CandleInterval",
    "Coin",
    "DeliveryState",
    "EmailOutbox",
    "EmailPurpose",
    "EmailToken",
    "Holding",
    "OhlcCandle",
    "Portfolio",
    "PriceSnapshot",
    "RefreshToken",
    "TelegramLinkToken",
    "User",
]

PRICE = Numeric(24, 8)
QTY = Numeric(36, 18)


def enum_column(python_enum: type[enum.Enum], name: str) -> Enum:
    """Store enum *values*, not member names.

    SQLAlchemy defaults to the member name, which silently diverges whenever the
    two differ (CandleInterval.h1 -> "h1" while the postgres type holds "1h").
    """
    return Enum(
        python_enum,
        name=name,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, default=None)
    telegram_linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tehran")
    quiet_from_hour: Mapped[int | None] = mapped_column(Integer, default=None)
    quiet_to_hour: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    portfolios: Mapped[list[Portfolio]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EmailToken(Base):
    """Verification and password-reset tokens. Only the digest is stored (D10)."""

    __tablename__ = "email_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[EmailPurpose] = mapped_column(enum_column(EmailPurpose, "email_purpose"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EmailOutbox(Base):
    """Outbox for transactional mail (D12) — same retry mechanics as alerts."""

    __tablename__ = "email_outbox"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    to_email: Mapped[str] = mapped_column(String(320))
    kind: Mapped[EmailPurpose] = mapped_column(enum_column(EmailPurpose, "email_purpose"))
    subject: Mapped[str] = mapped_column(String(200))
    body_html: Mapped[str] = mapped_column(Text)
    delivery_state: Mapped[DeliveryState] = mapped_column(
        enum_column(DeliveryState, "delivery_state"), default=DeliveryState.pending
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_email_outbox_undelivered",
            "next_retry_at",
            postgresql_where="delivery_state in ('pending', 'failed')",
        ),
    )


class TelegramLinkToken(Base):
    __tablename__ = "telegram_link_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Coin(Base):
    __tablename__ = "coins"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # coingecko id
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    name: Mapped[str] = mapped_column(String(120))
    image_url: Mapped[str | None] = mapped_column(Text)
    market_cap_rank: Mapped[int | None] = mapped_column(Integer, index=True)
    sparkline_7d: Mapped[list[float] | None] = mapped_column(JSONB)
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), default="سبد من")
    base_currency: Mapped[str] = mapped_column(String(8), default="USD")
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="portfolios")
    holdings: Mapped[list[Holding]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    coin_id: Mapped[str] = mapped_column(ForeignKey("coins.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(QTY)
    avg_buy_price: Mapped[Decimal] = mapped_column(PRICE)
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")
    coin: Mapped[Coin] = relationship(lazy="joined", innerjoin=True)

    __table_args__ = (
        UniqueConstraint("portfolio_id", "coin_id", name="uq_holdings_portfolio_coin"),
        CheckConstraint("quantity > 0", name="ck_holdings_qty_positive"),
        CheckConstraint("avg_buy_price >= 0", name="ck_holdings_price_non_negative"),
    )


class PriceSnapshot(Base):
    """One row per coin per poll (5 min). Source of the in-house candles (D3)."""

    __tablename__ = "price_snapshots"

    coin_id: Mapped[str] = mapped_column(ForeignKey("coins.id"), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    price_usd: Mapped[Decimal] = mapped_column(PRICE)
    volume_24h: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(30, 2))
    pct_change_24h: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    __table_args__ = (Index("ix_snapshots_coin_ts", "coin_id", "ts"),)


class OhlcCandle(Base):
    __tablename__ = "ohlc_candles"

    coin_id: Mapped[str] = mapped_column(ForeignKey("coins.id"), primary_key=True)
    interval: Mapped[CandleInterval] = mapped_column(
        enum_column(CandleInterval, "candle_interval"), primary_key=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(PRICE)
    high: Mapped[Decimal] = mapped_column(PRICE)
    low: Mapped[Decimal] = mapped_column(PRICE)
    close: Mapped[Decimal] = mapped_column(PRICE)
    is_partial: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_candles_lookup", "coin_id", "interval", "ts"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    coin_id: Mapped[str] = mapped_column(ForeignKey("coins.id"), index=True)
    kind: Mapped[AlertKind] = mapped_column(enum_column(AlertKind, "alert_kind"))
    threshold: Mapped[Decimal] = mapped_column(PRICE)
    window_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[AlertStatus] = mapped_column(
        enum_column(AlertStatus, "alert_status"), default=AlertStatus.active
    )
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    is_one_shot: Mapped[bool] = mapped_column(Boolean, default=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="alerts")
    coin: Mapped[Coin] = relationship(lazy="joined", innerjoin=True)

    __table_args__ = (
        Index("ix_alerts_status_coin", "status", "coin_id"),
        CheckConstraint("threshold > 0", name="ck_alerts_threshold_positive"),
        CheckConstraint(
            "window_minutes is null or window_minutes in (15, 30, 60)",
            name="ck_alerts_window_allowed",
        ),
    )


class AlertEvent(Base):
    """Outbox row for a fired alert (D6). Never send from the evaluator."""

    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True
    )
    dedupe_bucket: Mapped[str] = mapped_column(String(40))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price_at_trigger: Mapped[Decimal] = mapped_column(PRICE)
    delivery_state: Mapped[DeliveryState] = mapped_column(
        enum_column(DeliveryState, "delivery_state"), default=DeliveryState.pending
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)

    alert: Mapped[Alert] = relationship(lazy="joined", innerjoin=True)

    __table_args__ = (
        UniqueConstraint("alert_id", "dedupe_bucket", name="uq_alert_events_dedupe"),
        Index(
            "ix_alert_events_undelivered",
            "next_retry_at",
            postgresql_where="delivery_state in ('pending', 'failed')",
        ),
    )

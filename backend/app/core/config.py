"""Typed settings. Everything that differs between machines lives in .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    secret_key: str = "dev-only-secret-change-me-please-32b"
    public_base_url: str = "http://localhost:5173"
    # kept as a plain string: pydantic-settings json-decodes list fields from the
    # environment before any validator runs, so a comma separated value fails
    cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+asyncpg://coinpulse:coinpulse@postgres:5432/coinpulse"
    redis_url: str = "redis://redis:6379/0"

    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_demo_key: str = ""
    # D1: one /coins/markets call per interval returns every tracked coin.
    # 300s => ~8,640 calls/month against a ~10,000 call monthly cap.
    poll_interval_seconds: int = 300
    top_n_coins: int = 50

    telegram_bot_token: str = ""
    telegram_bot_username: str = "CoinPulseBot"
    telegram_webhook_secret: str = "change-me-too"

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "CoinPulse <no-reply@coinpulse.local>"
    smtp_starttls: bool = False

    # D10 amended by the owner (2026-09-09): the verification gate can be turned
    # off while real SMTP is not wired up. Default stays on.
    require_email_verification: bool = True

    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    max_active_alerts: int = 50

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

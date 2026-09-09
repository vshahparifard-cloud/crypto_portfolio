from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.deps import SessionDep
from app.core.urls import is_public_http_url
from app.services import cache

router = APIRouter(tags=["ops"])

STALE_FACTOR = 3
MAIL_CATCHERS = {"mailhog", "localhost", "127.0.0.1", "maildev", "mailpit"}


def config_warnings() -> list[str]:
    """Configuration that is fine in development but silently drops mail or
    hands out dead links anywhere else.

    Delivery of a captured email is recorded as a success everywhere in the
    system — correctly, because SMTP accepted it — so without this the only
    symptom is a user who never receives anything.
    """
    warnings: list[str] = []
    if settings.smtp_host.lower() in MAIL_CATCHERS:
        warnings.append(
            f"smtp_host is '{settings.smtp_host}': mail is captured by a local catcher, "
            "not delivered to real inboxes"
        )
    if not is_public_http_url(settings.public_base_url):
        warnings.append(
            f"public_base_url is '{settings.public_base_url}': verification links and "
            "telegram buttons will not open for anyone but this machine"
        )
    if not settings.telegram_bot_token:
        warnings.append("telegram_bot_token is empty: alerts cannot be delivered")
    return warnings


@router.get("/health")
async def health(session: SessionDep) -> dict[str, Any]:
    """Reports staleness, not just liveness: a silent price pipeline is an outage."""
    checks: dict[str, Any] = {"database": "down", "redis": "down"}
    try:
        await session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:  # health must never raise
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        await cache.redis_client().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # health must never raise
        checks["redis"] = f"error: {type(exc).__name__}"

    now = datetime.now(UTC)
    workers: dict[str, Any] = {}
    try:
        beats = await cache.heartbeats()
    except Exception:  # health must never raise
        beats = {}
    for name, stamp in beats.items():
        if not stamp:
            workers[name] = "never ran"
            continue
        age = (now - datetime.fromisoformat(stamp)).total_seconds()
        limit = settings.poll_interval_seconds * STALE_FACTOR
        workers[name] = {
            "last_run": stamp,
            "age_seconds": int(age),
            "state": "ok" if age < limit else "stale",
        }

    warnings = config_warnings()
    degraded = (
        any(value != "ok" for value in checks.values())
        or any(isinstance(value, dict) and value["state"] == "stale" for value in workers.values())
        # a mail catcher or a localhost base url is expected in dev and broken anywhere else
        or (not settings.is_dev and bool(warnings))
    )
    return {
        "status": "degraded" if degraded else "ok",
        "env": settings.app_env,
        "poll_interval_seconds": settings.poll_interval_seconds,
        "checks": checks,
        "workers": workers,
        "config_warnings": warnings,
    }

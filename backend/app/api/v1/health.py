from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.deps import SessionDep
from app.services import cache

router = APIRouter(tags=["ops"])

STALE_FACTOR = 3


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

    degraded = any(value != "ok" for value in checks.values()) or any(
        isinstance(value, dict) and value["state"] == "stale" for value in workers.values()
    )
    return {
        "status": "degraded" if degraded else "ok",
        "env": settings.app_env,
        "poll_interval_seconds": settings.poll_interval_seconds,
        "checks": checks,
        "workers": workers,
    }

"""Fixed-window counters in Redis. Used for login, resend and forgot-password."""
from __future__ import annotations

from app.core.errors import TooManyRequests
from app.services.cache import redis_client


async def enforce(key: str, limit: int, window_seconds: int, message: str) -> None:
    redis = redis_client()
    counter_key = f"rl:{key}"
    current = await redis.incr(counter_key)
    if current == 1:
        await redis.expire(counter_key, window_seconds)
    if current > limit:
        raise TooManyRequests(message, {"retry_after_seconds": await redis.ttl(counter_key)})

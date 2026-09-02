"""Per-user rate limiting for browser-facing endpoints (e.g. the chat API)."""

from __future__ import annotations

import time

from fastapi import Depends, HTTPException, status
from redis import RedisError
from tessera_sdk.infra.cache import Cache
from tessera_sdk.server.dependencies.auth import get_current_user

from app.config import get_settings
from app.infra.logging_config import get_logger

logger = get_logger("rate_limit")

RATE_LIMIT_NAMESPACE = "rate_limit"
WINDOW_SECONDS = 60


def _rate_limit_cache() -> Cache:
    return Cache(namespace=RATE_LIMIT_NAMESPACE)


def enforce_user_rate_limit(scope: str):
    """Build a FastAPI dependency enforcing conversa_rate_limit_per_user_per_minute
    for the given scope (e.g. "chat"), keyed per authenticated user.

    A fixed 60s window counter in Redis. If the limit setting is unset,
    this is a no-op — rate limiting stays opt-in via that existing config.
    """

    async def _dependency(current_user=Depends(get_current_user)) -> None:
        limit = get_settings().conversa_rate_limit_per_user_per_minute
        if not limit:
            return

        cache = _rate_limit_cache()
        window = int(time.time() // WINDOW_SECONDS)
        key = f"{scope}:{current_user.id}:{window}"
        redis_key = f"{cache.namespace}:{key}"

        try:
            count = cache.redis_client.incr(redis_key)
            if count == 1:
                cache.redis_client.expire(redis_key, WINDOW_SECONDS)
        except RedisError as e:
            # Fail open: an unreachable rate limiter shouldn't take down the
            # endpoint it's protecting.
            logger.warning("Rate limit check failed, allowing request: %s", e)
            return

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again shortly.",
            )

    return _dependency

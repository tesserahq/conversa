"""
Optional rate limiting for Conversa (per platform and user).

Uses Redis when CONVERSA_RATE_LIMIT_PER_USER_PER_MINUTE is set.
If not set or Redis unavailable, no limit is applied.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def check_conversa_rate_limit(
    channel: str,
    external_user_id: str,
    redis_client: Optional[object],
    limit_per_minute: Optional[int],
) -> bool:
    """
    Check if the (channel, external_user_id) is within rate limit.
    Returns True if allowed, False if rate limited.
    If redis_client or limit_per_minute is None, always returns True.
    """
    if redis_client is None or limit_per_minute is None or limit_per_minute <= 0:
        return True
    key = f"conversa:ratelimit:{channel}:{external_user_id}"
    try:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 60)
        results = pipe.execute()
        count = results[0] if results else 0
        return count <= limit_per_minute
    except Exception as e:
        logger.warning("Rate limit check failed, allowing request: %s", e)
        return True

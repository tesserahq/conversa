"""Tests for the per-user rate limit dependency."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from redis import RedisError

import app.core.rate_limit as rate_limit


class _FakeRedisClient:
    def __init__(self, incr_side_effect=None):
        self.counts: dict[str, int] = {}
        self.expired_keys: list[str] = []
        self._incr_side_effect = incr_side_effect

    def incr(self, key: str) -> int:
        if self._incr_side_effect is not None:
            raise self._incr_side_effect
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, ttl: int) -> None:
        self.expired_keys.append(key)


def _fake_settings(limit):
    return SimpleNamespace(conversa_rate_limit_per_user_per_minute=limit)


@pytest.mark.asyncio
async def test_no_op_when_limit_unset(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", lambda: _fake_settings(None))
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(
        rate_limit,
        "_rate_limit_cache",
        lambda: SimpleNamespace(namespace="rate_limit", redis_client=fake_redis),
    )

    dependency = rate_limit.enforce_user_rate_limit("chat")
    await dependency(current_user=SimpleNamespace(id=uuid4()))

    assert fake_redis.counts == {}


@pytest.mark.asyncio
async def test_allows_requests_under_the_limit(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", lambda: _fake_settings(5))
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(
        rate_limit,
        "_rate_limit_cache",
        lambda: SimpleNamespace(namespace="rate_limit", redis_client=fake_redis),
    )

    dependency = rate_limit.enforce_user_rate_limit("chat")
    user = SimpleNamespace(id=uuid4())

    for _ in range(5):
        await dependency(current_user=user)  # should not raise


@pytest.mark.asyncio
async def test_rejects_requests_over_the_limit(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", lambda: _fake_settings(2))
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(
        rate_limit,
        "_rate_limit_cache",
        lambda: SimpleNamespace(namespace="rate_limit", redis_client=fake_redis),
    )

    dependency = rate_limit.enforce_user_rate_limit("chat")
    user = SimpleNamespace(id=uuid4())

    await dependency(current_user=user)
    await dependency(current_user=user)
    with pytest.raises(HTTPException) as exc_info:
        await dependency(current_user=user)

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_limits_are_scoped_per_user(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", lambda: _fake_settings(1))
    fake_redis = _FakeRedisClient()
    monkeypatch.setattr(
        rate_limit,
        "_rate_limit_cache",
        lambda: SimpleNamespace(namespace="rate_limit", redis_client=fake_redis),
    )

    dependency = rate_limit.enforce_user_rate_limit("chat")
    user_a = SimpleNamespace(id=uuid4())
    user_b = SimpleNamespace(id=uuid4())

    await dependency(current_user=user_a)  # user_a at their limit
    await dependency(current_user=user_b)  # different user, should not raise


@pytest.mark.asyncio
async def test_fails_open_on_redis_error(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", lambda: _fake_settings(1))
    fake_redis = _FakeRedisClient(incr_side_effect=RedisError("connection refused"))
    monkeypatch.setattr(
        rate_limit,
        "_rate_limit_cache",
        lambda: SimpleNamespace(namespace="rate_limit", redis_client=fake_redis),
    )

    dependency = rate_limit.enforce_user_rate_limit("chat")
    await dependency(current_user=SimpleNamespace(id=uuid4()))  # should not raise

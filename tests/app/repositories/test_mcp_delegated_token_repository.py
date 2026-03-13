"""Tests for MCPDelegatedTokenService."""

from types import SimpleNamespace
from uuid import uuid4

from app.repositories.mcp_delegated_token_repository import MCPDelegatedTokenRepository


class _FakeCache:
    def __init__(self) -> None:
        self.data: dict[str, dict] = {}

    def read(self, key):
        return self.data.get(key)

    def write(self, key, value, ttl):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


def test_get_access_token_returns_cached_token(monkeypatch):
    """Cached delegated token is returned when still valid."""
    calls = {"count": 0}

    class _FailingIdentiesClient:
        def __init__(self, api_token):
            pass

        def exchange_token(self, **kwargs):
            calls["count"] += 1
            raise AssertionError("exchange_token should not be called on cache hit")

    monkeypatch.setattr(
        "app.repositories.mcp_delegated_token_repository.IdentiesClient",
        _FailingIdentiesClient,
    )

    service = MCPDelegatedTokenRepository(m2m_token_provider=lambda: "m2m")
    service._cache = _FakeCache()
    user_id = uuid4()
    key = service._cache_key(user_id, "linden", "mcp:tools:execute")
    service._cache.write(
        key,
        {
            "access_token": "cached-token",
            "expires_at": 9_999_999_999,
        },
        ttl=300,
    )

    token = service.get_access_token(
        user_id=user_id,
        audience="linden",
        scopes="mcp:tools:execute",
    )
    assert token == "cached-token"
    assert calls["count"] == 0


def test_get_access_token_miss_calls_exchange(monkeypatch):
    """Cache miss triggers token exchange and token caching."""
    calls = {"count": 0}

    class _FakeIdentiesClient:
        def __init__(self, api_token):
            assert api_token == "m2m-token"

        def exchange_token(self, **kwargs):
            calls["count"] += 1
            return SimpleNamespace(
                access_token="exchanged-token",
                expires_in=120,
            )

    monkeypatch.setattr(
        "app.repositories.mcp_delegated_token_repository.IdentiesClient",
        _FakeIdentiesClient,
    )

    service = MCPDelegatedTokenRepository(m2m_token_provider=lambda: "m2m-token")
    service._cache = _FakeCache()
    user_id = uuid4()

    token = service.get_access_token(
        user_id=user_id,
        audience="linden",
        scopes=["mcp:tools:read", "mcp:tools:execute"],
    )
    assert token == "exchanged-token"
    assert calls["count"] == 1


def test_get_access_token_force_refresh_bypasses_cache(monkeypatch):
    """Force refresh ignores valid cache and exchanges again."""
    calls = {"count": 0}

    class _FakeIdentiesClient:
        def __init__(self, api_token):
            pass

        def exchange_token(self, **kwargs):
            calls["count"] += 1
            return SimpleNamespace(
                access_token=f"token-{calls['count']}",
                expires_in=120,
            )

    monkeypatch.setattr(
        "app.repositories.mcp_delegated_token_repository.IdentiesClient",
        _FakeIdentiesClient,
    )

    service = MCPDelegatedTokenRepository(m2m_token_provider=lambda: "m2m-token")
    service._cache = _FakeCache()
    user_id = uuid4()

    first = service.get_access_token(
        user_id=user_id,
        audience="linden",
        scopes="mcp:tools:execute",
    )
    second = service.get_access_token(
        user_id=user_id,
        audience="linden",
        scopes="mcp:tools:execute",
        force_refresh=True,
    )
    assert first == "token-1"
    assert second == "token-2"
    assert calls["count"] == 2

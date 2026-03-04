"""Delegated token exchange helper for MCP auth."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable, Optional
from uuid import UUID

from tessera_sdk.identies import IdentiesClient  # type: ignore[import-untyped]
from tessera_sdk.utils.cache import Cache  # type: ignore[import-untyped]
from tessera_sdk.utils.m2m_token import M2MTokenClient  # type: ignore[import-untyped]

TOKEN_CACHE_NAMESPACE = "mcp_delegated_tokens"
DEFAULT_TOKEN_CACHE_TTL = 300
DEFAULT_REFRESH_MARGIN_SECONDS = 60


def _default_m2m_token_provider() -> Optional[str]:
    return M2MTokenClient().get_token_sync().access_token


class MCPDelegatedTokenService:
    """Retrieves and caches delegated tokens for MCP requests."""

    def __init__(
        self,
        *,
        m2m_token_provider: Optional[Callable[[], Optional[str]]] = None,
        refresh_margin_seconds: int = DEFAULT_REFRESH_MARGIN_SECONDS,
    ) -> None:
        self._cache: Cache = Cache(namespace=TOKEN_CACHE_NAMESPACE)
        self._m2m_token_provider = m2m_token_provider or _default_m2m_token_provider
        self._refresh_margin_seconds = refresh_margin_seconds

    def get_access_token(
        self,
        *,
        user_id: UUID,
        audience: str,
        scopes: str | list[str],
        context: Optional[dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> str:
        """Get delegated access token from cache or exchange endpoint."""
        normalized_scopes = self._normalize_scopes(scopes)
        cache_key = self._cache_key(user_id, audience, normalized_scopes)

        if not force_refresh:
            cached = self._cache.read(cache_key)
            if cached and self._is_cached_token_valid(cached):
                token = cached.get("access_token")
                if isinstance(token, str) and token:
                    return token

        m2m_token = self._m2m_token_provider()
        if not m2m_token:
            raise ValueError("Delegated token exchange requires an M2M token")

        identies = IdentiesClient(api_token=m2m_token)
        response = identies.exchange_token(
            user_id=str(user_id),
            requested_audience=audience,
            requested_scope=normalized_scopes,
            context=context,
        )
        expires_at = int(time.time()) + int(response.expires_in)
        ttl = max(1, min(int(response.expires_in), DEFAULT_TOKEN_CACHE_TTL))
        self._cache.write(
            cache_key,
            {
                "access_token": response.access_token,
                "expires_at": expires_at,
            },
            ttl=ttl,
        )
        return response.access_token

    def invalidate(
        self,
        *,
        user_id: UUID,
        audience: str,
        scopes: str | list[str],
    ) -> None:
        """Invalidate a cached delegated token."""
        normalized_scopes = self._normalize_scopes(scopes)
        self._cache.delete(self._cache_key(user_id, audience, normalized_scopes))

    def _cache_key(self, user_id: UUID, audience: str, scopes: str) -> str:
        scope_hash = hashlib.sha256(scopes.encode("utf-8")).hexdigest()[:16]
        return f"mcp:token:{user_id}:{audience}:{scope_hash}"

    def _normalize_scopes(self, scopes: str | list[str]) -> str:
        if isinstance(scopes, list):
            normalized = [scope.strip() for scope in scopes if scope.strip()]
            return " ".join(sorted(normalized))
        return " ".join(part for part in scopes.strip().split() if part)

    def _is_cached_token_valid(self, cached: dict[str, Any]) -> bool:
        expires_at = cached.get("expires_at")
        if not isinstance(expires_at, int):
            return False
        return (expires_at - int(time.time())) > self._refresh_margin_seconds

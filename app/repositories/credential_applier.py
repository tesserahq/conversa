"""Applies credentials as HTTP auth headers for outgoing requests."""

from __future__ import annotations

import base64
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.constants.credentials import CredentialType
from app.repositories.credential_repository import CredentialRepository
from app.repositories.mcp_delegated_token_repository import MCPDelegatedTokenRepository


def _default_m2m_token_provider() -> Optional[str]:
    """Fetch M2M token from Tessera SDK. Import is deferred — only runs when called."""
    try:
        from tessera_sdk.infra.m2m_token import M2MTokenClient

        return M2MTokenClient().get_token_sync().access_token
    except Exception:
        return None


class CredentialApplier:
    """
    Resolves auth headers from a credential ID.

    Expensive collaborators (M2M token provider, MCPDelegatedTokenRepository) are
    constructed lazily — only when a credential type that needs them actually executes.

    Two public methods encode the semantic difference between callers:
      apply()          — None credential_id → inject default M2M (sync worker path)
      apply_for_user() — None credential_id → return headers unchanged (MCP path)
    """

    def __init__(
        self,
        db: Session,
        *,
        m2m_token_provider: Optional[Callable[[], Optional[str]]] = None,
        delegated_token_repo: Optional[MCPDelegatedTokenRepository] = None,
    ) -> None:
        self._crud = CredentialRepository(db)
        self._m2m_token_provider_override = m2m_token_provider
        self._delegated_token_repo_override = delegated_token_repo
        # Lazy sentinels — nothing expensive runs at construction time.
        self._m2m_token_provider: Optional[Callable[[], Optional[str]]] = None
        self._delegated_token_repo: Optional[MCPDelegatedTokenRepository] = None

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def apply(
        self,
        credential_id: Optional[UUID],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Inject auth into headers for an outgoing request.

        When credential_id is None, injects a default M2M Bearer token.
        Used by the sync worker (ContextPackFetcher), which owns its own M2M identity.
        """
        result = dict(headers) if headers else {}

        if credential_id is None:
            token = self._get_m2m_token_provider()()
            if not token:
                raise ValueError("Default M2M auth requires an M2M token")
            result["Authorization"] = f"Bearer {token}"
            return result

        return self._apply_by_id(
            credential_id, result, user_id=None, context=None, force_refresh=False
        )

    def apply_for_user(
        self,
        credential_id: Optional[UUID],
        *,
        user_id: Optional[UUID] = None,
        headers: Optional[Dict[str, str]] = None,
        context: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, str]:
        """
        Inject auth into headers using optional user context.

        When credential_id is None, returns headers unchanged (no auth configured).
        Used by MCP tool executor, catalog, and server refresh paths.
        """
        result = dict(headers) if headers else {}
        if credential_id is None:
            return result

        return self._apply_by_id(
            credential_id,
            result,
            user_id=user_id,
            context=context,
            force_refresh=force_refresh,
        )

    # ------------------------------------------------------------------
    # Lazy collaborator accessors
    # ------------------------------------------------------------------

    def _get_m2m_token_provider(self) -> Callable[[], Optional[str]]:
        if self._m2m_token_provider is None:
            self._m2m_token_provider = (
                self._m2m_token_provider_override or _default_m2m_token_provider
            )
        return self._m2m_token_provider

    def _get_delegated_token_repo(self) -> MCPDelegatedTokenRepository:
        if self._delegated_token_repo is None:
            self._delegated_token_repo = (
                self._delegated_token_repo_override
                or MCPDelegatedTokenRepository(
                    m2m_token_provider=self._get_m2m_token_provider()
                )
            )
        return self._delegated_token_repo

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _apply_by_id(
        self,
        credential_id: UUID,
        result: Dict[str, str],
        *,
        user_id: Optional[UUID],
        context: Optional[Dict[str, Any]],
        force_refresh: bool,
    ) -> Dict[str, str]:
        credential = self._crud.get_credential(credential_id)
        if not credential:
            raise ValueError(f"Credential {credential_id} not found")
        fields = self._crud.get_credential_fields(credential_id) or {}
        cred_type = CredentialType(str(credential.type))
        return self._dispatch(
            result,
            cred_type,
            fields,
            user_id=user_id,
            context=context,
            force_refresh=force_refresh,
        )

    def _dispatch(
        self,
        result: Dict[str, str],
        credential_type: CredentialType,
        fields: Dict[str, Any],
        *,
        user_id: Optional[UUID],
        context: Optional[Dict[str, Any]],
        force_refresh: bool,
    ) -> Dict[str, str]:
        if credential_type == CredentialType.BEARER_AUTH:
            token = fields.get("token")
            if not token:
                raise ValueError("Bearer auth requires a token field")
            result["Authorization"] = f"Bearer {token}"
            return result

        if credential_type == CredentialType.BASIC_AUTH:
            username = fields.get("username")
            password = fields.get("password")
            if not username or not password:
                raise ValueError("Basic auth requires username and password")
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            result["Authorization"] = f"Basic {encoded}"
            return result

        if credential_type == CredentialType.API_KEY:
            header_name = fields.get("header_name", "X-Api-Key")
            api_key = fields.get("api_key")
            if not api_key:
                raise ValueError("API key auth requires api_key field")
            result[header_name] = api_key
            return result

        if credential_type == CredentialType.M2M_IDENTIES:
            token = self._get_m2m_token_provider()()
            if not token:
                raise ValueError("M2M Identies auth requires an M2M token")
            result["Authorization"] = f"Bearer {token}"
            return result

        if credential_type == CredentialType.DELEGATED_IDENTIES_EXCHANGE:
            if user_id is None:
                raise ValueError(
                    "Delegated Identies exchange requires user_id in execution context"
                )
            audience = fields.get("audience")
            scopes = fields.get("scopes")
            if not audience or not scopes:
                raise ValueError(
                    "Delegated Identies exchange requires audience and scopes fields"
                )
            token = self._get_delegated_token_repo().get_access_token(
                user_id=user_id,
                audience=audience,
                scopes=scopes,
                context=context,
                force_refresh=force_refresh,
            )
            result["Authorization"] = f"Bearer {token}"
            return result

        raise ValueError(f"Unsupported credential type: {credential_type}")

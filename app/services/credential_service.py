"""Service for credential CRUD and auth application."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy.orm import Query, Session

from app.core.credentials import (
    decrypt_credential_fields,
    encrypt_credential_fields,
    redact_credential_fields,
    validate_credential_fields,
)
from app.constants.credentials import CredentialType
from app.models.credential import Credential
from app.schemas.credential import CredentialCreate, CredentialRead, CredentialUpdate
from app.services.mcp_delegated_token_service import MCPDelegatedTokenService
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters


def _get_default_m2m_token() -> Optional[str]:
    """Fetch default M2M token from Tessera SDK. Returns None if unavailable."""
    try:
        from tessera_sdk.utils.m2m_token import M2MTokenClient  # type: ignore[import-untyped]

        return M2MTokenClient().get_token_sync().access_token
    except Exception:
        return None


class CredentialService(SoftDeleteService[Credential]):
    """Manages credentials for context source auth."""

    def __init__(
        self,
        db: Session,
        *,
        m2m_token_provider: Optional[Callable[[], Optional[str]]] = None,
        delegated_token_service: Optional[MCPDelegatedTokenService] = None,
    ) -> None:
        super().__init__(db, Credential)
        self._m2m_token_provider = m2m_token_provider or _get_default_m2m_token
        self._delegated_token_service = (
            delegated_token_service
            or MCPDelegatedTokenService(m2m_token_provider=self._m2m_token_provider)
        )

    def get_credential(self, credential_id: UUID) -> Optional[Credential]:
        """Fetch a credential by ID."""
        return self.db.query(Credential).filter(Credential.id == credential_id).first()

    def get_credentials(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Credential]:
        """List credentials with pagination."""
        return (
            self.db.query(Credential)
            .order_by(Credential.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_credentials_query(self) -> Query[Credential]:
        """Get a query for credentials (for pagination)."""
        return self.db.query(Credential).order_by(Credential.created_at.desc())

    def create_credential(
        self,
        data: CredentialCreate,
        created_by_id: Optional[UUID] = None,
    ) -> Credential:
        """Create a credential; validate and encrypt fields."""
        validate_credential_fields(data.type, data.fields or {})
        encrypted_data = encrypt_credential_fields(data.fields or {})

        credential = Credential(
            name=data.name,
            type=data.type,
            encrypted_data=encrypted_data,
            created_by_id=created_by_id,
        )
        self.db.add(credential)
        self.db.commit()
        self.db.refresh(credential)
        return credential

    def update_credential(
        self,
        credential_id: UUID,
        data: CredentialUpdate,
    ) -> Optional[Credential]:
        """Update a credential; re-encrypt if fields change."""
        credential = self.get_credential(credential_id)
        if not credential:
            return None

        if data.name is not None:
            credential.name = cast(Any, data.name)
        if data.fields is not None:
            validate_credential_fields(cast(str, credential.type), data.fields)
            credential.encrypted_data = cast(
                Any, encrypt_credential_fields(data.fields)
            )

        self.db.commit()
        self.db.refresh(credential)
        return credential

    def delete_credential(self, credential_id: UUID) -> bool:
        """Soft delete a credential."""
        return self.delete_record(credential_id)

    def get_credential_fields(self, credential_id: UUID) -> Optional[Dict[str, Any]]:
        """Decrypt and return credential fields. Internal use only."""
        credential = self.get_credential(credential_id)
        if not credential:
            return None
        try:
            return decrypt_credential_fields(cast(bytes, credential.encrypted_data))
        except Exception:
            return None

    def to_credential_read(self, credential: Credential) -> CredentialRead:
        """Build CredentialRead from a Credential with redacted fields (no secrets in response)."""
        fields = self.get_credential_fields(credential.id) or {}
        redacted = redact_credential_fields(fields)
        return CredentialRead(
            id=credential.id,
            name=credential.name,
            type=credential.type,
            created_by_id=credential.created_by_id,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
            extended_info=None,
            fields=redacted,
        )

    def search(self, filters: Dict[str, Any]) -> List[Credential]:
        """Search credentials by filters."""
        query = self.db.query(Credential)
        query = apply_filters(query, Credential, filters)
        return query.all()

    def apply_credentials(
        self,
        credential_id: Optional[UUID] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Apply credential to headers for HTTP requests. Used by sync worker.

        When credential_id is None, uses default M2M auth. Otherwise applies
        the credential by type; for M2M_IDENTIES, uses the default M2M token.
        """
        result = dict(headers) if headers else {}

        if credential_id is None:
            token = self._m2m_token_provider()
            if not token:
                raise ValueError("Default M2M auth requires an M2M token")
            result["Authorization"] = f"Bearer {token}"
            return result

        credential = self._get_credential_or_raise(credential_id)
        fields = self.get_credential_fields(credential_id) or {}
        cred_type = CredentialType(cast(str, credential.type))
        return self._apply_credential_type(
            result=result,
            credential_type=cred_type,
            fields=fields,
            force_refresh=False,
        )

    def apply_credentials_with_context(
        self,
        *,
        credential_id: Optional[UUID],
        headers: Optional[Dict[str, str]] = None,
        user_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, str]:
        """
        Apply credentials using optional runtime context.

        Contextual behavior differs from apply_credentials():
        when credential_id is None, no auth headers are applied.
        """
        result = dict(headers) if headers else {}
        if credential_id is None:
            return result

        credential = self._get_credential_or_raise(credential_id)
        fields = self.get_credential_fields(credential_id) or {}
        cred_type = CredentialType(cast(str, credential.type))
        return self._apply_credential_type(
            result=result,
            credential_type=cred_type,
            fields=fields,
            user_id=user_id,
            context=context,
            force_refresh=force_refresh,
        )

    def _get_credential_or_raise(self, credential_id: UUID) -> Credential:
        credential = self.get_credential(credential_id)
        if not credential:
            raise ValueError(f"Credential {credential_id} not found")
        return credential

    def _apply_credential_type(
        self,
        *,
        result: Dict[str, str],
        credential_type: CredentialType,
        fields: Dict[str, Any],
        user_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
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
            import base64

            auth_str = f"{username}:{password}"
            result["Authorization"] = (
                f"Basic {base64.b64encode(auth_str.encode()).decode()}"
            )
            return result

        if credential_type == CredentialType.API_KEY:
            header_name = fields.get("header_name", "X-Api-Key")
            api_key = fields.get("api_key")
            if not api_key:
                raise ValueError("API key auth requires api_key field")
            result[header_name] = api_key
            return result

        if credential_type == CredentialType.M2M_IDENTIES:
            token = self._m2m_token_provider()
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
            token = self._delegated_token_service.get_access_token(
                user_id=user_id,
                audience=audience,
                scopes=scopes,
                context=context,
                force_refresh=force_refresh,
            )
            result["Authorization"] = f"Bearer {token}"
            return result

        raise ValueError(f"Unsupported credential type: {credential_type}")

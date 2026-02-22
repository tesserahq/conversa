"""Service for credential CRUD and auth application."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Query, Session

from app.core.credentials import (
    decrypt_credential_fields,
    encrypt_credential_fields,
    validate_credential_fields,
)
from app.constants.credentials import CredentialType
from app.models.credential import Credential
from app.schemas.credential import CredentialCreate, CredentialUpdate
from app.services.soft_delete_service import SoftDeleteService
from app.utils.db.filtering import apply_filters


def _get_default_m2m_token() -> Optional[str]:
    """Fetch default M2M token from Tessera SDK. Returns None if unavailable."""
    try:
        from tessera_sdk.utils.m2m_token import M2MTokenClient

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
    ) -> None:
        super().__init__(db, Credential)
        self._m2m_token_provider = m2m_token_provider or _get_default_m2m_token

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
            credential.name = data.name
        if data.fields is not None:
            validate_credential_fields(credential.type, data.fields)
            credential.encrypted_data = encrypt_credential_fields(data.fields)

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
            return decrypt_credential_fields(credential.encrypted_data)
        except Exception:
            return None

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

        credential = self.get_credential(credential_id)
        if not credential:
            raise ValueError(f"Credential {credential_id} not found")

        fields = self.get_credential_fields(credential_id) or {}
        cred_type = CredentialType(credential.type)

        if cred_type == CredentialType.BEARER_AUTH:
            token = fields.get("token")
            if not token:
                raise ValueError("Bearer auth requires a token field")
            result["Authorization"] = f"Bearer {token}"

        elif cred_type == CredentialType.BASIC_AUTH:
            username = fields.get("username")
            password = fields.get("password")
            if not username or not password:
                raise ValueError("Basic auth requires username and password")
            import base64

            auth_str = f"{username}:{password}"
            result["Authorization"] = (
                f"Basic {base64.b64encode(auth_str.encode()).decode()}"
            )

        elif cred_type == CredentialType.API_KEY:
            header_name = fields.get("header_name", "X-Api-Key")
            api_key = fields.get("api_key")
            if not api_key:
                raise ValueError("API key auth requires api_key field")
            result[header_name] = api_key

        elif cred_type == CredentialType.M2M_IDENTIES:
            token = self._m2m_token_provider()
            if not token:
                raise ValueError("M2M Identies auth requires an M2M token")
            result["Authorization"] = f"Bearer {token}"

        return result

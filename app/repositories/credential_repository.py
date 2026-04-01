"""Repository for Credential CRUD operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy.orm import Query, Session

from app.core.credentials import (
    decrypt_credential_fields,
    encrypt_credential_fields,
    redact_credential_fields,
    validate_credential_fields,
)
from app.models.credential import Credential
from app.schemas.credential import CredentialCreate, CredentialRead, CredentialUpdate
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.utils.db.filtering import apply_filters


class CredentialRepository(SoftDeleteRepository[Credential]):
    """DB CRUD for Credential records. No auth logic."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Credential)

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

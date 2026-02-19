"""Pydantic schemas for credentials."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CredentialField(BaseModel):
    """Field definition for a credential type."""

    name: str
    label: str
    type: str = "string"
    input_type: str = "text"
    help: str = ""
    required: bool = True


class CredentialTypeInfo(BaseModel):
    """Metadata for a credential type."""

    type_name: str
    display_name: str
    fields: list[CredentialField]


# Pydantic models for validation per credential type
class BearerAuthModel(BaseModel):
    """Bearer token auth fields."""

    token: str


class BasicAuthModel(BaseModel):
    """Basic auth fields."""

    username: str
    password: str


class ApiKeyModel(BaseModel):
    """API key auth fields (header name + value)."""

    header_name: str = "X-Api-Key"
    api_key: str


class M2mIdentiesModel(BaseModel):
    """M2M Identies auth (no stored secret; uses request token)."""

    pass


class CredentialCreate(BaseModel):
    """Request schema for creating a credential."""

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(
        ...,
        description="Credential type (bearer_auth, basic_auth, api_key, m2m_identies)",
    )
    fields: dict[str, Any] = Field(default_factory=dict)


class CredentialUpdate(BaseModel):
    """Request schema for updating a credential."""

    name: str | None = Field(None, min_length=1, max_length=100)
    fields: dict[str, Any] | None = None


class CredentialRead(BaseModel):
    """Response schema for a credential (no decrypted fields)."""

    id: UUID
    name: str
    type: str
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CredentialInfo(BaseModel):
    """Credential with obfuscated field hints for UI."""

    id: UUID
    name: str
    type: str
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    fields: dict[str, str] = Field(default_factory=dict)

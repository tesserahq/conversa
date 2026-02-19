"""Pydantic schemas for context sources."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContextSourceCapabilities(BaseModel):
    """Capabilities of a context source."""

    supports_etag: bool = False
    supports_since_cursor: bool = False


class ContextSourceBase(BaseModel):
    """Base schema for context source."""

    source_id: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=256)
    base_url: str = Field(..., max_length=512)
    credential_id: UUID | None = None
    capabilities: ContextSourceCapabilities | None = None
    poll_interval_seconds: int = Field(3600, ge=60, le=86400)
    enabled: bool = True

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError("source_id must be alphanumeric with hyphens, 1-64 chars")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must be http:// or https://")
        return v


class ContextSourceCreate(ContextSourceBase):
    """Request schema for creating a context source."""

    pass


class ContextSourceUpdate(BaseModel):
    """Request schema for updating a context source."""

    source_id: str | None = Field(None, min_length=1, max_length=64)
    display_name: str | None = Field(None, min_length=1, max_length=256)
    base_url: str | None = Field(None, max_length=512)
    credential_id: UUID | None = None
    capabilities: ContextSourceCapabilities | None = None
    poll_interval_seconds: int | None = Field(None, ge=60, le=86400)
    enabled: bool | None = None

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError("source_id must be alphanumeric with hyphens, 1-64 chars")
        return v

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("base_url must be http:// or https://")
        return v


class ContextSourceRead(BaseModel):
    """Response schema for a context source."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: str
    display_name: str
    base_url: str
    credential_id: UUID | None
    capabilities: ContextSourceCapabilities | dict | None
    poll_interval_seconds: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

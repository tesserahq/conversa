"""Pydantic schemas for system prompt and version API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SystemPromptRead(BaseModel):
    """Response schema for a system prompt (metadata)."""

    id: UUID
    name: str
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemPromptCreate(BaseModel):
    """Request schema for creating a new system prompt."""

    name: str = Field(..., min_length=1, max_length=64)
    content: str = Field("", description="Initial markdown content")
    note: str | None = Field(None, max_length=512)


class SystemPromptUpdate(BaseModel):
    """Request schema for updating a system prompt (e.g. rename)."""

    name: str = Field(..., min_length=1, max_length=64)


class SystemPromptVersionRead(BaseModel):
    """Response schema for a single system prompt version."""

    id: UUID
    system_prompt_id: UUID
    content: str
    version_number: int
    created_at: datetime
    note: str | None = None

    model_config = {"from_attributes": True}


class SystemPromptVersionCreate(BaseModel):
    """Request schema for creating a new system prompt version."""

    content: str = Field(..., description="Markdown body of the system prompt")
    note: str | None = Field(None, max_length=512, description="Optional change reason")


class SystemPromptCurrentRead(BaseModel):
    """Response schema for the current system prompt (content + version info)."""

    content: str
    version_id: UUID
    version_number: int
    updated_at: datetime

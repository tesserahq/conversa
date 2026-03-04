"""Pydantic schemas for MCP servers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MCPServerBase(BaseModel):
    """Base schema for MCP server registry records."""

    server_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=256)
    url: str = Field(..., max_length=512)
    credential_id: UUID | None = None
    tool_prefix: str | None = Field(None, min_length=1, max_length=64)
    tool_cache_ttl_seconds: int = Field(300, ge=30, le=86400)
    enabled: bool = True
    extended_info: dict[str, Any] | None = None

    @field_validator("server_id")
    @classmethod
    def validate_server_id(cls, value: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", value):
            raise ValueError("server_id must be alphanumeric with hyphens, 1-64 chars")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must be http:// or https://")
        return value

    @field_validator("tool_prefix")
    @classmethod
    def validate_tool_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.match(r"^[a-z0-9][a-z0-9-_]*[a-z0-9]$", value):
            raise ValueError(
                "tool_prefix must be alphanumeric with hyphens or underscores"
            )
        return value


class MCPServerCreate(MCPServerBase):
    """Request schema for creating an MCP server."""

    pass


class MCPServerUpdate(BaseModel):
    """Request schema for updating an MCP server."""

    server_id: str | None = Field(None, min_length=1, max_length=64)
    name: str | None = Field(None, min_length=1, max_length=256)
    url: str | None = Field(None, max_length=512)
    credential_id: UUID | None = None
    tool_prefix: str | None = Field(None, min_length=1, max_length=64)
    tool_cache_ttl_seconds: int | None = Field(None, ge=30, le=86400)
    enabled: bool | None = None
    extended_info: dict[str, Any] | None = None

    @field_validator("server_id")
    @classmethod
    def validate_server_id(cls, value: str | None) -> str | None:
        if value is not None and not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", value):
            raise ValueError("server_id must be alphanumeric with hyphens, 1-64 chars")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("url must be http:// or https://")
        return value

    @field_validator("tool_prefix")
    @classmethod
    def validate_tool_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.match(r"^[a-z0-9][a-z0-9-_]*[a-z0-9]$", value):
            raise ValueError(
                "tool_prefix must be alphanumeric with hyphens or underscores"
            )
        return value


class MCPServerRead(BaseModel):
    """Response schema for an MCP server."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    server_id: str
    name: str
    url: str
    credential_id: UUID | None
    tool_prefix: str | None
    tool_cache_ttl_seconds: int
    enabled: bool
    extended_info: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class MCPToolsRefreshResponse(BaseModel):
    """Response schema for POST /mcp-servers/{id}/refresh-tools."""

    server_id: str
    tools_count: int

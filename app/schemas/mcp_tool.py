"""Pydantic schemas for MCP tool catalog (normalized tool representation)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


def build_qualified_name(prefix: str, original_name: str) -> str:
    """Build qualified tool name: {prefix}__{original_name} (double underscore)."""
    return f"{prefix}__{original_name}"


class MCPCatalogTool(BaseModel):
    """Normalized representation of an MCP tool for catalog and LLM adapter."""

    qualified_name: str = Field(..., description="Prefixed name e.g. linden__tool_name")
    original_name: str = Field(
        ..., description="Tool name as returned by the MCP server"
    )
    description: str | None = Field(None, description="Tool description")
    input_schema: dict[str, Any] = Field(default_factory=dict)
    server_id: str = Field(..., description="MCP server_id from registry")

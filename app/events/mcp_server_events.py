"""
Utilities for building mcp_server-related CloudEvents payloads.
"""

from __future__ import annotations

from uuid import UUID

from app.models.mcp_server import MCPServer as MCPServerModel
from app.schemas.mcp_server import MCPServerRead as MCPServerSchema
from tessera_sdk.infra.events.event import Event, event_source, event_type  # type: ignore[import-untyped]

# MCP server events
MCP_SERVER_CREATED = "mcp_server.created"
MCP_SERVER_UPDATED = "mcp_server.updated"
MCP_SERVER_DELETED = "mcp_server.deleted"


def build_mcp_server_created_event(
    mcp_server: MCPServerModel,
    created_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for MCP server creation."""
    server_schema = MCPServerSchema.model_validate(mcp_server)
    event_data: dict[str, object] = {
        "mcp_server": server_schema.model_dump(mode="json"),
    }
    if created_by_id is not None:
        event_data["created_by_id"] = str(created_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(MCP_SERVER_CREATED),
        event_data=event_data,
        subject=f"/mcp-servers/{mcp_server.id}",
        user_id=str(created_by_id) if created_by_id else "",
        labels={"mcp_server_id": str(mcp_server.id)},
        tags=[f"mcp_server_id:{mcp_server.id}"],
    )


def build_mcp_server_updated_event(
    mcp_server: MCPServerModel,
    updated_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for MCP server update."""
    server_schema = MCPServerSchema.model_validate(mcp_server)
    event_data: dict[str, object] = {
        "mcp_server": server_schema.model_dump(mode="json"),
    }
    if updated_by_id is not None:
        event_data["updated_by_id"] = str(updated_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(MCP_SERVER_UPDATED),
        event_data=event_data,
        subject=f"/mcp-servers/{mcp_server.id}",
        user_id=str(updated_by_id) if updated_by_id else "",
        labels={"mcp_server_id": str(mcp_server.id)},
        tags=[f"mcp_server_id:{mcp_server.id}"],
    )


def build_mcp_server_deleted_event(
    mcp_server: MCPServerModel,
    deleted_by_id: UUID | None = None,
) -> Event:
    """Build a CloudEvent for MCP server deletion."""
    server_schema = MCPServerSchema.model_validate(mcp_server)
    event_data: dict[str, object] = {
        "mcp_server": server_schema.model_dump(mode="json"),
    }
    if deleted_by_id is not None:
        event_data["deleted_by_id"] = str(deleted_by_id)

    return Event(
        source=event_source(),
        event_type=event_type(MCP_SERVER_DELETED),
        event_data=event_data,
        subject=f"/mcp-servers/{mcp_server.id}",
        user_id=str(deleted_by_id) if deleted_by_id else "",
        labels={"mcp_server_id": str(mcp_server.id)},
        tags=[f"mcp_server_id:{mcp_server.id}"],
    )

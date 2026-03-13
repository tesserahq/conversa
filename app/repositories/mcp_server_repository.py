"""Service for MCP server CRUD."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Query, Session

from app.models.mcp_server import MCPServer
from app.schemas.mcp_server import MCPServerCreate, MCPServerUpdate
from app.repositories.soft_delete_repository import SoftDeleteRepository
from app.utils.db.filtering import apply_filters


class MCPServerRepository(SoftDeleteRepository[MCPServer]):
    """Manages MCP servers for the MCP registry."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, MCPServer)

    def get_mcp_server(self, mcp_server_id: UUID) -> Optional[MCPServer]:
        """Fetch an MCP server by ID."""
        return self.db.query(MCPServer).filter(MCPServer.id == mcp_server_id).first()

    def get_mcp_server_by_server_id(self, server_id: str) -> Optional[MCPServer]:
        """Fetch an MCP server by unique server_id."""
        return self.db.query(MCPServer).filter(MCPServer.server_id == server_id).first()

    def get_mcp_servers(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[MCPServer]:
        """List MCP servers with pagination."""
        return (
            self.db.query(MCPServer)
            .order_by(MCPServer.server_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_mcp_servers_query(self) -> Query[MCPServer]:
        """Get a query for MCP servers (for pagination)."""
        return self.db.query(MCPServer).order_by(MCPServer.server_id)

    def get_enabled_servers(self) -> List[MCPServer]:
        """Return enabled MCP servers, ordered by server_id."""
        return (
            self.db.query(MCPServer)
            .filter(MCPServer.enabled.is_(True))
            .order_by(MCPServer.server_id)
            .all()
        )

    def create_mcp_server(self, data: MCPServerCreate) -> MCPServer:
        """Create an MCP server. Raises ValueError if server_id exists."""
        if self.get_mcp_server_by_server_id(data.server_id) is not None:
            raise ValueError(
                f"MCP server with server_id {data.server_id!r} already exists"
            )

        mcp_server = MCPServer(
            server_id=data.server_id,
            name=data.name,
            url=data.url,
            credential_id=data.credential_id,
            tool_prefix=data.tool_prefix,
            tool_cache_ttl_seconds=data.tool_cache_ttl_seconds,
            enabled=data.enabled,
            extended_info=data.extended_info,
        )
        self.db.add(mcp_server)
        self.db.commit()
        self.db.refresh(mcp_server)
        return mcp_server

    def update_mcp_server(
        self,
        mcp_server_id: UUID,
        data: MCPServerUpdate,
    ) -> Optional[MCPServer]:
        """Update an MCP server. Raises ValueError if new server_id exists."""
        mcp_server = self.get_mcp_server(mcp_server_id)
        if not mcp_server:
            return None

        if data.server_id is not None and data.server_id != mcp_server.server_id:
            if self.get_mcp_server_by_server_id(data.server_id) is not None:
                raise ValueError(
                    f"MCP server with server_id {data.server_id!r} already exists"
                )
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(mcp_server, key, value)

        self.db.commit()
        self.db.refresh(mcp_server)
        return mcp_server

    def delete_mcp_server(self, mcp_server_id: UUID) -> bool:
        """Soft delete an MCP server."""
        return self.delete_record(mcp_server_id)

    def search(self, filters: Dict[str, Any]) -> List[MCPServer]:
        """Search MCP servers by filters."""
        query = self.db.query(MCPServer)
        query = apply_filters(query, MCPServer, filters)
        return query.all()

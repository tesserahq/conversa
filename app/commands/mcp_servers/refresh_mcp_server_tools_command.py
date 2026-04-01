"""Command to force-refresh the tool catalog for an MCP server."""

from __future__ import annotations

from typing import Optional, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.mcp.catalog import ToolCatalog
from app.models.mcp_server import MCPServer
from app.schemas.mcp_server import MCPToolsRefreshResponse
from app.repositories.credential_applier import CredentialApplier


class RefreshMcpServerToolsCommand:
    """
    Command to force-refresh tools from an MCP server.
    Uses CredentialRepository for headers and ToolCatalog for fetching.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    async def execute(
        self,
        mcp_server: MCPServer,
        user_id: Optional[UUID] = None,
    ) -> MCPToolsRefreshResponse:
        """
        Force-refresh tools from the MCP server and return the response.

        Args:
            mcp_server: The MCP server to refresh tools for.
            user_id: Optional user ID for credential context.

        Returns:
            MCPToolsRefreshResponse with server_id and tools_count.

        Raises:
            Exception: When tools cannot be fetched from the MCP server.
        """
        credential_svc = CredentialApplier(self.db)
        headers = credential_svc.apply_for_user(
            cast(Optional[UUID], mcp_server.credential_id),
            user_id=user_id,
        )
        catalog = ToolCatalog.new()
        tools = await catalog.get_tools(mcp_server, headers, force_refresh=True)
        return MCPToolsRefreshResponse(
            server_id=cast(str, mcp_server.server_id),
            tools_count=len(tools),
        )

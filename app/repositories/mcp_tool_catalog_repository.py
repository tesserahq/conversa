"""Orchestrates loading tools across enabled MCP servers for a request context."""

from __future__ import annotations

from typing import Optional, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.logging_config import get_logger
from app.mcp.catalog import ToolCatalog
from app.schemas.mcp_tool import MCPCatalogTool
from app.repositories.credential_repository import CredentialRepository
from app.repositories.mcp_server_repository import MCPServerRepository

logger = get_logger(__name__)


class MCPToolCatalogRepository:
    """
    Loads tools from all enabled MCP servers for a given request.

    Uses MCPServerRepository.get_enabled_servers(), CredentialRepository for auth headers,
    and ToolCatalog for cached tool fetching per server.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    async def get_tools_for_request(
        self,
        *,
        user_id: Optional[UUID] = None,
    ) -> list[MCPCatalogTool]:
        """
        Return tools from all enabled MCP servers.

        Resolves auth headers per server (credential-driven) and fetches tools
        via ToolCatalog (cached). Per-server failures are logged and skipped.
        """
        mcp_svc = MCPServerRepository(self._db)
        cred_svc = CredentialRepository(self._db)
        catalog = ToolCatalog.new()

        servers = mcp_svc.get_enabled_servers()
        all_tools: list[MCPCatalogTool] = []

        for server in servers:
            try:
                headers = cred_svc.apply_credentials_with_context(
                    credential_id=cast(Optional[UUID], server.credential_id),
                    user_id=user_id,
                    context=None,
                )
                tools = await catalog.get_tools(server, headers)
                all_tools.extend(tools)
            except Exception as e:
                logger.warning(
                    "Failed to load tools for MCP server %s: %s",
                    server.server_id,
                    e,
                    exc_info=True,
                )
                continue

        return all_tools

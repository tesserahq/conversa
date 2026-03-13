"""Tool catalog: fetch, normalize, and cache MCP tools (no DB; caller passes server + headers)."""

from __future__ import annotations

import logging
from typing import Any

from tessera_sdk.utils.cache import Cache  # type: ignore[import-untyped]

from app.mcp.client_factory import client_context
from app.models.mcp_server import MCPServer
from app.schemas.mcp_tool import MCPCatalogTool, build_qualified_name

logger = logging.getLogger(__name__)

TOOL_CATALOG_NAMESPACE = "mcp_tool_catalog"
CACHE_KEY_PREFIX = "mcp:tools:"


def _tool_to_catalog_tool(
    tool: Any,
    server_id: str,
    prefix: str,
) -> MCPCatalogTool:
    """Map MCP Tool to MCPCatalogTool with qualified name."""
    name = getattr(tool, "name", "") or ""
    description = getattr(tool, "description", None)
    input_schema = getattr(tool, "inputSchema", None)
    if input_schema is None:
        input_schema = {}
    if not isinstance(input_schema, dict):
        input_schema = {}
    qualified = build_qualified_name(prefix, name)
    return MCPCatalogTool(
        qualified_name=qualified,
        original_name=name,
        description=description,
        input_schema=input_schema,
        server_id=server_id,
    )


def _cache_key(server_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}{server_id}"


class ToolCatalog:
    """Fetches and caches MCP tools; normalizes to MCPCatalogTool. No DB dependency."""

    def __init__(self, *, cache: Cache) -> None:
        self._cache = cache

    @classmethod
    def new(cls, *, cache: Cache | None = None) -> ToolCatalog:
        """Create a ToolCatalog instance. Uses default cache if not provided."""
        if cache is None:
            cache = Cache(namespace=TOOL_CATALOG_NAMESPACE)
        return cls(cache=cache)

    def invalidate(self, server_id: str) -> None:
        """Remove cached tools for the given server (e.g. after config change)."""
        self._cache.delete(_cache_key(server_id))

    async def get_tools(
        self,
        mcp_server: MCPServer,
        headers: dict[str, str],
        *,
        force_refresh: bool = False,
    ) -> list[MCPCatalogTool]:
        """
        Return tools for the server. Uses cache unless force_refresh is True.

        Caller must pass MCPServer and pre-resolved headers (e.g. from CredentialRepository).
        """
        server_id = mcp_server.server_id
        prefix = mcp_server.tool_prefix or server_id
        key = _cache_key(server_id)
        ttl = mcp_server.tool_cache_ttl_seconds

        if not force_refresh:
            raw = self._cache.read(key)
            if raw is not None and isinstance(raw, list):
                return [MCPCatalogTool.model_validate(t) for t in raw]

        tools = []
        async with client_context(mcp_server.url, headers) as client:
            try:
                tools = await client.list_tools()
            except Exception as e:
                # Surface MCP server errors (e.g. "Invalid request parameters") with context
                url = getattr(mcp_server, "url", str(mcp_server))
                detail = str(e)
                # MCPError and similar expose .data with server-provided detail
                if getattr(e, "data", None):
                    detail = f"{detail} (server detail: {e.data})"
                logger.warning("MCP get_tools failed for %s: %s", url, detail)
                raise RuntimeError(
                    f"Failed to get tools from MCP server {url}: {detail}"
                ) from e

        catalog_tools = [_tool_to_catalog_tool(t, server_id, prefix) for t in tools]
        payload = [t.model_dump(mode="json") for t in catalog_tools]
        self._cache.write(key, payload, ttl=ttl)
        return catalog_tools

"""Tests for app.mcp.catalog."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp.catalog import ToolCatalog, get_tool_catalog
from app.schemas.mcp_tool import build_qualified_name


def test_build_qualified_name():
    """Qualified name is prefix__original_name."""
    assert build_qualified_name("linden", "get_weather") == "linden__get_weather"
    assert build_qualified_name("my-server", "tool_a") == "my-server__tool_a"


def test_get_tool_catalog_returns_tool_catalog_instance():
    """get_tool_catalog() returns a ToolCatalog with default cache."""
    catalog = get_tool_catalog()
    assert isinstance(catalog, ToolCatalog)


def test_tool_catalog_invalidate_deletes_cache_key():
    """invalidate(server_id) deletes the cache key for that server."""
    cache = MagicMock()
    catalog = ToolCatalog(cache=cache)
    catalog.invalidate("linden")
    cache.delete.assert_called_once_with("mcp:tools:linden")


@pytest.mark.asyncio
async def test_tool_catalog_get_tools_uses_cache_on_hit():
    """get_tools returns cached list when not force_refresh and cache has data."""
    cache = MagicMock()
    cached = [
        {
            "qualified_name": "linden__get_weather",
            "original_name": "get_weather",
            "description": "Get weather",
            "input_schema": {},
            "server_id": "linden",
        }
    ]
    cache.read.return_value = cached
    catalog = ToolCatalog(cache=cache)
    mcp_server = MagicMock()
    mcp_server.server_id = "linden"
    mcp_server.url = "https://api.example.com/mcp"
    mcp_server.tool_prefix = "linden"
    mcp_server.tool_cache_ttl_seconds = 300

    with patch("app.mcp.catalog.client_context"):
        tools = await catalog.get_tools(mcp_server, {})

    assert len(tools) == 1
    assert tools[0].qualified_name == "linden__get_weather"
    assert tools[0].original_name == "get_weather"
    assert tools[0].server_id == "linden"
    cache.read.assert_called_once_with("mcp:tools:linden")
    cache.write.assert_not_called()


@pytest.mark.asyncio
async def test_tool_catalog_get_tools_fetches_and_caches_on_miss():
    """get_tools fetches from client and writes to cache on cache miss."""
    cache = MagicMock()
    cache.read.return_value = None
    catalog = ToolCatalog(cache=cache)
    mcp_server = MagicMock()
    mcp_server.server_id = "linden"
    mcp_server.url = "https://api.example.com/mcp"
    mcp_server.tool_prefix = "linden"
    mcp_server.tool_cache_ttl_seconds = 300

    fake_tool = MagicMock()
    fake_tool.name = "get_weather"
    fake_tool.description = "Get weather"
    fake_tool.inputSchema = {"type": "object"}
    fake_client = MagicMock()
    fake_client.list_tools = AsyncMock(return_value=[fake_tool])

    async def enter_ctx(*args, **kwargs):
        yield fake_client

    with patch("app.mcp.catalog.client_context", new_callable=MagicMock) as ctx_mock:
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_client)
        cm.__aexit__ = AsyncMock(return_value=None)
        ctx_mock.return_value = cm

        tools = await catalog.get_tools(mcp_server, {"Authorization": "Bearer x"})

    assert len(tools) == 1
    assert tools[0].qualified_name == "linden__get_weather"
    assert tools[0].original_name == "get_weather"
    assert tools[0].server_id == "linden"
    cache.write.assert_called_once()
    call_args = cache.write.call_args
    assert call_args[0][0] == "mcp:tools:linden"
    assert isinstance(call_args[0][1], list)
    assert call_args[1]["ttl"] == 300


@pytest.mark.asyncio
async def test_tool_catalog_get_tools_force_refresh_ignores_cache():
    """get_tools with force_refresh=True fetches from client even if cache has data."""
    cache = MagicMock()
    cache.read.return_value = [
        {
            "qualified_name": "old__tool",
            "original_name": "tool",
            "description": "Old",
            "input_schema": {},
            "server_id": "linden",
        }
    ]
    catalog = ToolCatalog(cache=cache)
    mcp_server = MagicMock()
    mcp_server.server_id = "linden"
    mcp_server.url = "https://api.example.com/mcp"
    mcp_server.tool_prefix = "linden"
    mcp_server.tool_cache_ttl_seconds = 300

    fake_tool = MagicMock()
    fake_tool.name = "new_tool"
    fake_tool.description = "New tool"
    fake_tool.inputSchema = {}
    fake_client = MagicMock()
    fake_client.list_tools = AsyncMock(return_value=[fake_tool])

    with patch("app.mcp.catalog.client_context", new_callable=MagicMock) as ctx_mock:
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_client)
        cm.__aexit__ = AsyncMock(return_value=None)
        ctx_mock.return_value = cm

        tools = await catalog.get_tools(mcp_server, {}, force_refresh=True)

    assert len(tools) == 1
    assert tools[0].qualified_name == "linden__new_tool"
    cache.write.assert_called_once()
    cache.read.assert_not_called()

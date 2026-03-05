"""pydantic-ai toolset adapter for MCP catalog tools."""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from pydantic import TypeAdapter
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import ToolsetTool

from app.schemas.mcp_tool import MCPCatalogTool
from app.services.mcp_tool_executor import MCPToolExecutor

# SchemaValidator that accepts any dict; MCP tools validate on the server side.
_ARGS_VALIDATOR = TypeAdapter(dict[str, Any]).validator


class MCPToolset(AbstractToolset[None]):
    """
    Toolset that exposes MCP catalog tools to the LLM.

    Converts MCPCatalogTool definitions into pydantic-ai tools and routes
    execution to MCPToolExecutor.
    """

    def __init__(
        self,
        tools: list[MCPCatalogTool],
        executor: MCPToolExecutor,
        *,
        user_id: Optional[UUID] = None,
        tool_id: str = "mcp",
    ) -> None:
        self._tools = tools
        self._executor = executor
        self._user_id = user_id
        self._tool_id = tool_id
        self._lookup: dict[str, MCPCatalogTool] = {t.qualified_name: t for t in tools}

    @property
    def id(self) -> str | None:
        return self._tool_id

    async def get_tools(self, ctx: Any) -> dict[str, ToolsetTool]:
        result: dict[str, ToolsetTool] = {}
        for catalog_tool in self._tools:
            tool_def = ToolDefinition(
                name=catalog_tool.qualified_name,
                description=catalog_tool.description
                or f"MCP tool: {catalog_tool.original_name}",
                parameters_json_schema=catalog_tool.input_schema
                or {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
            )
            result[catalog_tool.qualified_name] = ToolsetTool(
                toolset=self,
                tool_def=tool_def,
                max_retries=0,
                args_validator=_ARGS_VALIDATOR,
            )
        return result

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool,
    ) -> Any:
        catalog_tool = self._lookup.get(name)
        if catalog_tool is None:
            return {"error": "Tool not found", "reason": f"Unknown tool: {name}"}

        result = await self._executor.execute(
            server_id=catalog_tool.server_id,
            original_name=catalog_tool.original_name,
            args=tool_args,
            user_id=self._user_id,
        )
        if isinstance(result, str):
            return result
        return json.dumps(result, default=str)

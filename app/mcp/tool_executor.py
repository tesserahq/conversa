"""Executes MCP tool calls with timeout and structured error mapping."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.logging_config import get_logger
from app.mcp.client_factory import client_context
from app.repositories.credential_applier import CredentialApplier
from app.repositories.mcp_server_repository import MCPServerRepository

logger = get_logger(__name__)


def _to_llm_output(value: Any) -> str | dict[str, Any]:
    """Convert tool result to JSON-serializable format for LLM."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, int, float, bool)):
        return {"result": value}
    try:
        serialized = json.loads(json.dumps(value, default=str))
        return serialized if isinstance(serialized, dict) else {"result": serialized}
    except (TypeError, ValueError):
        return {"result": str(value)}


class MCPToolExecutor:
    """
    Executes call_tool(original_name, args) against an MCP server.

    Enforces timeout, resolves auth via CredentialRepository, and maps errors
    to structured responses for the LLM.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    async def execute(
        self,
        *,
        server_id: str,
        original_name: str,
        args: dict[str, Any],
        user_id: Optional[UUID] = None,
        timeout_seconds: float = 20.0,
    ) -> str | dict[str, Any]:
        """
        Execute a tool on the given MCP server.

        Args:
            server_id: MCP server identifier from registry.
            original_name: Tool name as exposed by the MCP server.
            args: Tool arguments (JSON-serializable dict).
            user_id: Optional user ID for delegated auth.
            timeout_seconds: Max execution time.

        Returns:
            JSON-serializable result for the LLM, or error dict on failure.
        """
        mcp_svc = MCPServerRepository(self._db)
        cred_svc = CredentialApplier(self._db)

        server = mcp_svc.get_mcp_server_by_server_id(server_id)
        if server is None:
            return {
                "error": "Tool execution failed",
                "reason": f"Server {server_id!r} not found",
            }

        headers = cred_svc.apply_for_user(
            server.credential_id,
            user_id=user_id,
        )

        try:
            async with client_context(server.url, headers) as client:
                result = await asyncio.wait_for(
                    client.call_tool(
                        original_name, arguments=args or {}, raise_on_error=False
                    ),
                    timeout=timeout_seconds,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "MCP tool %s timed out after %ss", original_name, timeout_seconds
            )
            return {
                "error": "Tool execution failed",
                "reason": "Request timed out",
            }
        except Exception as e:
            logger.warning("MCP tool %s failed: %s", original_name, e, exc_info=True)
            return {
                "error": "Tool execution failed",
                "reason": str(e),
            }

        if result.is_error:
            reason = (
                str(getattr(result, "data", result)) if result.data else "Unknown error"
            )
            return {"error": "Tool execution failed", "reason": reason}

        return _to_llm_output(result.data)

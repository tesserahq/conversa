"""Command to delete an MCP server."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.mcp_server_events import build_mcp_server_deleted_event
from app.mcp.catalog import ToolCatalog
from app.models.mcp_server import MCPServer
from app.services.mcp_server_service import MCPServerService
from tessera_sdk.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class DeleteMcpServerCommand:
    """
    Command to soft-delete an MCP server and publish mcp_server.deleted event.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.mcp_server_service = MCPServerService(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        mcp_server_id: UUID,
        deleted_by_id: Optional[UUID] = None,
    ) -> bool:
        """
        Execute the command to soft-delete an MCP server and publish the event.

        Args:
            mcp_server_id: The MCP server ID to delete.
            deleted_by_id: Optional user ID of the deleter.

        Returns:
            True if the server was deleted, False if not found.
        """
        mcp_server = self.mcp_server_service.get_mcp_server(mcp_server_id)
        if mcp_server is None:
            return False

        ok = self.mcp_server_service.delete_mcp_server(mcp_server_id)
        if ok:
            self._publish_mcp_server_deleted_event(mcp_server, deleted_by_id)
            ToolCatalog.new().invalidate(mcp_server.server_id)
        return ok

    def _publish_mcp_server_deleted_event(
        self,
        mcp_server: MCPServer,
        deleted_by_id: Optional[UUID],
    ) -> None:
        """Publish an mcp_server.deleted event to NATS."""
        event = build_mcp_server_deleted_event(mcp_server, deleted_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing mcp-server-deleted event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish mcp-server-deleted event to NATS"
                )

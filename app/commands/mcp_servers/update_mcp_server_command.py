"""Command to update an MCP server."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.mcp_server_events import build_mcp_server_updated_event
from app.models.mcp_server import MCPServer
from app.schemas.mcp_server import MCPServerUpdate
from app.services.mcp_server_service import MCPServerService
from tessera_sdk.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class UpdateMcpServerCommand:
    """
    Command to update an MCP server and publish mcp_server.updated event.
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
        data: MCPServerUpdate,
        updated_by_id: Optional[UUID] = None,
    ) -> Optional[MCPServer]:
        """
        Execute the command to update an MCP server and publish the event.

        Args:
            mcp_server_id: The MCP server ID to update.
            data: The update data.
            updated_by_id: Optional user ID of the updater.

        Returns:
            The updated MCP server, or None if not found.

        Raises:
            ValueError: If new server_id already exists.
        """
        mcp_server = self.mcp_server_service.update_mcp_server(mcp_server_id, data)
        if mcp_server is not None:
            self._publish_mcp_server_updated_event(mcp_server, updated_by_id)
        return mcp_server

    def _publish_mcp_server_updated_event(
        self,
        mcp_server: MCPServer,
        updated_by_id: Optional[UUID],
    ) -> None:
        """Publish an mcp_server.updated event to NATS."""
        event = build_mcp_server_updated_event(mcp_server, updated_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing mcp-server-updated event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish mcp-server-updated event to NATS"
                )

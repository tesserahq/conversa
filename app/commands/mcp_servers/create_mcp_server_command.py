"""Command to create an MCP server."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.mcp_server_events import build_mcp_server_created_event
from app.models.mcp_server import MCPServer
from app.schemas.mcp_server import MCPServerCreate
from app.repositories.mcp_server_repository import MCPServerRepository
from tessera_sdk.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class CreateMcpServerCommand:
    """
    Command to create an MCP server and publish mcp_server.created event.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.mcp_server_service = MCPServerRepository(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        data: MCPServerCreate,
        created_by_id: Optional[UUID] = None,
    ) -> MCPServer:
        """
        Execute the command to create an MCP server and publish the event.

        Args:
            data: The MCP server creation data.
            created_by_id: Optional user ID of the creator.

        Returns:
            The created MCP server.

        Raises:
            ValueError: If server_id already exists.
        """
        mcp_server = self.mcp_server_service.create_mcp_server(data)
        self._publish_mcp_server_created_event(mcp_server, created_by_id)
        return mcp_server

    def _publish_mcp_server_created_event(
        self,
        mcp_server: MCPServer,
        created_by_id: Optional[UUID],
    ) -> None:
        """Publish an mcp_server.created event to NATS."""
        event = build_mcp_server_created_event(mcp_server, created_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing mcp-server-created event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish mcp-server-created event to NATS"
                )

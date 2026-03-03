"""Command to create a context source."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.context_source_events import build_context_source_created_event
from app.models.context_source import ContextSource
from app.schemas.context_source import ContextSourceCreate
from app.services.context_source_service import ContextSourceService
from tessera_sdk.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class CreateContextSourceCommand:
    """
    Command to create a context source and publish context_source.created event.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.context_source_service = ContextSourceService(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        data: ContextSourceCreate,
        created_by_id: Optional[UUID] = None,
    ) -> ContextSource:
        """
        Execute the command to create a context source and publish the event.

        Args:
            data: The context source creation data.
            created_by_id: Optional user ID of the creator.

        Returns:
            The created context source.

        Raises:
            ValueError: If source_id already exists.
        """
        source = self.context_source_service.create_context_source(data)
        self._publish_context_source_created_event(source, created_by_id)
        return source

    def _publish_context_source_created_event(
        self,
        source: ContextSource,
        created_by_id: Optional[UUID],
    ) -> None:
        """Publish a context_source.created event to NATS."""
        event = build_context_source_created_event(source, created_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing context-source-created event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish context-source-created event to NATS"
                )

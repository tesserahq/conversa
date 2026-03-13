"""Command to update a context source."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.context_source_events import build_context_source_updated_event
from app.models.context_source import ContextSource
from app.schemas.context_source import ContextSourceUpdate
from app.repositories.context_source_repository import ContextSourceRepository
from tessera_sdk.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class UpdateContextSourceCommand:
    """
    Command to update a context source and publish context_source.updated event.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.context_source_service = ContextSourceRepository(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        source_id: UUID,
        data: ContextSourceUpdate,
        updated_by_id: Optional[UUID] = None,
    ) -> Optional[ContextSource]:
        """
        Execute the command to update a context source and publish the event.

        Args:
            source_id: The context source ID to update.
            data: The update data.
            updated_by_id: Optional user ID of the updater.

        Returns:
            The updated context source, or None if not found.

        Raises:
            ValueError: If new source_id already exists.
        """
        source = self.context_source_service.update_context_source(source_id, data)
        if source is not None:
            self._publish_context_source_updated_event(source, updated_by_id)
        return source

    def _publish_context_source_updated_event(
        self,
        source: ContextSource,
        updated_by_id: Optional[UUID],
    ) -> None:
        """Publish a context_source.updated event to NATS."""
        event = build_context_source_updated_event(source, updated_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing context-source-updated event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish context-source-updated event to NATS"
                )

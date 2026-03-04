"""Command to delete a context source."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.context_source_events import build_context_source_deleted_event
from app.models.context_source import ContextSource
from app.services.context_source_service import ContextSourceService
from tessera_sdk.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class DeleteContextSourceCommand:
    """
    Command to soft-delete a context source and publish context_source.deleted event.
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
        source_id: UUID,
        deleted_by_id: Optional[UUID] = None,
    ) -> bool:
        """
        Execute the command to soft-delete a context source and publish the event.

        Args:
            source_id: The context source ID to delete.
            deleted_by_id: Optional user ID of the deleter.

        Returns:
            True if the source was deleted, False if not found.
        """
        source = self.context_source_service.get_context_source(source_id)
        if source is None:
            return False

        ok = self.context_source_service.delete_context_source(source_id)
        if ok:
            self._publish_context_source_deleted_event(source, deleted_by_id)
        return ok

    def _publish_context_source_deleted_event(
        self,
        source: ContextSource,
        deleted_by_id: Optional[UUID],
    ) -> None:
        """Publish a context_source.deleted event to NATS."""
        event = build_context_source_deleted_event(source, deleted_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing context-source-deleted event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish context-source-deleted event to NATS"
                )

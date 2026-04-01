"""Command to create a system prompt."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.system_prompt_events import build_system_prompt_created_event
from app.models.system_prompt import SystemPrompt
from app.schemas.system_prompt import SystemPromptCreate
from app.repositories.system_prompt_repository import SystemPromptRepository
from tessera_sdk.infra.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class CreateSystemPromptCommand:
    """
    Command to create a system prompt and publish system_prompt.created event.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.system_prompt_service = SystemPromptRepository(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        data: SystemPromptCreate,
        created_by_id: Optional[UUID] = None,
    ) -> SystemPrompt:
        """
        Execute the command to create a system prompt and publish the event.

        Args:
            data: The system prompt creation data.
            created_by_id: Optional user ID of the creator.

        Returns:
            The created system prompt.

        Raises:
            ValueError: If name already exists.
        """
        prompt = self.system_prompt_service.create_prompt(
            name=data.name,
            initial_content=data.content,
            note=data.note,
        )
        self._publish_system_prompt_created_event(prompt, created_by_id)
        return prompt

    def _publish_system_prompt_created_event(
        self,
        prompt: SystemPrompt,
        created_by_id: Optional[UUID],
    ) -> None:
        """Publish a system_prompt.created event to NATS."""
        event = build_system_prompt_created_event(prompt, created_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing system-prompt-created event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish system-prompt-created event to NATS"
                )

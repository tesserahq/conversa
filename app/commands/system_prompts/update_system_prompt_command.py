"""Command to update a system prompt (rename)."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.events.system_prompt_events import build_system_prompt_updated_event
from app.models.system_prompt import SystemPrompt
from app.schemas.system_prompt import SystemPromptUpdate
from app.services.system_prompt_service import SystemPromptService
from tessera_sdk.events.nats_router import NatsEventPublisher  # type: ignore[import-untyped]


class UpdateSystemPromptCommand:
    """
    Command to update a system prompt (e.g. rename) and publish system_prompt.updated event.
    """

    def __init__(
        self,
        db: Session,
        nats_publisher: Optional[NatsEventPublisher] = None,
    ):
        self.db = db
        self.system_prompt_service = SystemPromptService(db)
        self.nats_publisher = (
            nats_publisher if nats_publisher is not None else NatsEventPublisher()
        )
        self.logger = logging.getLogger(__name__)

    def execute(
        self,
        name: str,
        data: SystemPromptUpdate,
        updated_by_id: Optional[UUID] = None,
    ) -> Optional[SystemPrompt]:
        """
        Execute the command to update a system prompt and publish the event.

        Args:
            name: Current name of the system prompt.
            data: The update data (e.g. new name).
            updated_by_id: Optional user ID of the updater.

        Returns:
            The updated system prompt, or None if not found.

        Raises:
            ValueError: If new name already exists.
        """
        prompt = self.system_prompt_service.update_prompt_name(name, new_name=data.name)
        if prompt is not None:
            self._publish_system_prompt_updated_event(prompt, updated_by_id)
        return prompt

    def _publish_system_prompt_updated_event(
        self,
        prompt: SystemPrompt,
        updated_by_id: Optional[UUID],
    ) -> None:
        """Publish a system_prompt.updated event to NATS."""
        event = build_system_prompt_updated_event(prompt, updated_by_id)
        if self.nats_publisher is not None:
            self.logger.info(
                "Publishing system-prompt-updated event to NATS: %s",
                event.model_dump_json(),
            )
            try:
                self.nats_publisher.publish_sync(event, event.event_type)
            except Exception:  # pragma: no cover - defensive logging
                self.logger.exception(
                    "Failed to publish system-prompt-updated event to NATS"
                )
